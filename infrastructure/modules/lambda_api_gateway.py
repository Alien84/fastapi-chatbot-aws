import json
import pulumi
import pulumi_aws as aws

def create_api_stats_lambda_function(
        name,
        stack_name,
        db_ssm_prefix, 
        vpc_id, 
        subnet_ids, 
        security_group_id,
        region,
        image_uri=None,
        image_tag="latest",
        deploy_stage='ecr'
        ):
    """
    Creates an API Gateway Lambda function using a Docker container for statistics.
    
    Prerequisites:
    - Docker image must already be built and pushed to ECR via CI/CD pipeline
    - ECR repository should exist or be created separately
    
    Args:
        name: Base name for resources
        stack_name: Stack name for resource naming
        db_ssm_prefix: SSM parameter prefix for database config
        vpc_id: VPC ID for Lambda function
        subnet_ids: Subnet IDs for Lambda function
        security_group_id: Security group ID for Lambda function
        region: AWS region
        image_uri: Full ECR image URI for the Lambda function
        image_tag: Docker image tag (default: "latest")
        deploy_stage: Deployment stage ('ecr', 'lambda', or 'all')
    """
    # Get current AWS account ID
    current = aws.get_caller_identity()
    account_id = current.account_id

    # Create ECR repository for API stats Lambda (CI/CD pipeline will push to this)
    api_stats_ecr_repo = aws.ecr.Repository(
        f"{name}-{stack_name}-lambda-api-stats",
        name=f"{name}-{stack_name}-lambda-api-stats",
        image_tag_mutability="MUTABLE",
        image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
            scan_on_push=True,
        ),
        force_delete=True,  # Allow deletion even if images exist
        tags={"Name": f"{name}-{stack_name}-lambda-api-stats"}
    )
    
    # Create IAM role for Lambda
    lambda_role = aws.iam.Role(
        f"{name}-{stack_name}-api-stats-lambda-role",
        assume_role_policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {
                    "Service": "lambda.amazonaws.com",
                },
            }],
        }),
        tags={"Name": f"{name}-{stack_name}-api-stats-lambda-role"}
    )

    # Create custom policy for SSM and ECR access
    lambda_policy = aws.iam.Policy(
        f"{name}-{stack_name}-api-stats-lambda-policy",
        policy=pulumi.Output.all(api_stats_ecr_repo.arn, account_id).apply(
            lambda args: json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ssm:GetParameter",
                            "ssm:GetParameters",
                            "ssm:GetParametersByPath",
                            "ssm:DescribeParameters"
                        ],
                        "Resource": [
                            f"arn:aws:ssm:{region}:{account_id}:parameter/{name}/{stack_name}/db",
                            f"arn:aws:ssm:{region}:{account_id}:parameter/{name}/{stack_name}/db/*"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchGetImage",
                            "ecr:DescribeRepositories",
                            "ecr:DescribeImages",
                            "ecr:ListImages",
                            "ecr:DescribeImageScanFindings",
                            "ecr:GetRepositoryPolicy"
                        ],
                        "Resource": [
                            args[0],  # ECR repository ARN
                            f"arn:aws:ecr:{region}:{args[1]}:repository/*"  # Allow access to any ECR repo in account
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ecr:GetAuthorizationToken"
                        ],
                        "Resource": "*"
                    }
                ]
            })
        ),
        tags={"Name": f"{name}-{stack_name}-api-stats-lambda-policy"}
    )

    # Create ECR repository policy to allow Lambda service to pull images
    ecr_policy = aws.ecr.RepositoryPolicy(
        f"{name}-{stack_name}-api-stats-ecr-policy",
        repository=api_stats_ecr_repo.name,
        policy=pulumi.Output.all(lambda_role.arn, account_id).apply(
            lambda args: json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "lambda.amazonaws.com"
                        },
                        "Action": [
                            "ecr:BatchGetImage",
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchCheckLayerAvailability"
                        ],
                        "Condition": {
                            "StringEquals": {
                                "aws:SourceAccount": args[1]
                            }
                        }
                    },
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "AWS": args[0]  # Lambda execution role ARN
                        },
                        "Action": [
                            "ecr:BatchGetImage",
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchCheckLayerAvailability"
                        ]
                    }
                ]
            })
        )
    )

    # Create a lifecycle policy to manage image retention
    ecr_lifecycle_policy = aws.ecr.LifecyclePolicy(
        f"{name}-{stack_name}-api-stats-ecr-lifecycle",
        repository=api_stats_ecr_repo.name,
        # policy=json.dumps({
        #     "rules": [
        #         {
        #             "rulePriority": 1,
        #             "description": "Keep last 10 images",
        #             "selection": {
        #                 "tagStatus": "tagged",
        #                 "tagPrefixList": ["latest"],
        #                 "countType": "imageCountMoreThan",
        #                 "countNumber": 10
        #             },
        #             "action": {
        #                 "type": "expire"
        #             }
        #         }
        #     ]
        # }),
        # # Add lifecycle policy to auto-delete old images
        policy="""{  
            "rules": [
            {
                "rulePriority": 1,
                "description": "Keep last 10 images",
                "selection": {
                    "tagStatus": "tagged",
                    "tagPrefixList": ["latest"],
                    "countType": "imageCountMoreThan",
                    "countNumber": 10
                },
                "action": {
                    "type": "expire"
                }
            },
            {
                "rulePriority": 2,
                "description": "Delete untagged images after 1 day",
                "selection": {
                    "tagStatus": "any",
                    "countType": "sinceImagePushed",
                    "countUnit": "days",
                    "countNumber": 1
                },
                "action": {"type": "expire"}
            }
            ]
        }""",
        opts=pulumi.ResourceOptions(depends_on=[api_stats_ecr_repo])
    )

    # Attach AWS managed policies
    basic_execution_attachment = aws.iam.RolePolicyAttachment(
        f"{name}-{stack_name}-api-stats-basic-execution",
        role=lambda_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    )
    
    vpc_execution_attachment = aws.iam.RolePolicyAttachment(
        f"{name}-{stack_name}-api-stats-vpc-execution",
        role=lambda_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
    )
    
    # Attach custom policy
    custom_policy_attachment = aws.iam.RolePolicyAttachment(
        f"{name}-{stack_name}-api-stats-custom-policy",
        role=lambda_role.name,
        policy_arn=lambda_policy.arn
    )

    # Export the ECR repository information for CI/CD pipeline
    pulumi.export("api_stats_ecr_repo_url", api_stats_ecr_repo.repository_url)
    pulumi.export("api_stats_ecr_repo_name", api_stats_ecr_repo.name)
    pulumi.export("api_stats_ecr_repo_arn", api_stats_ecr_repo.arn)
    
    # Construct image URI - CI/CD pipeline should push image with this URI
    # image_uri =  "555576841436.dkr.ecr.eu-west-2.amazonaws.com/chatbot-dev-lambda-api-stats:latest"
    pulumi.export("api_stats_image_uri", image_uri)

    if deploy_stage in ["lambda", "all"]:
        # Create Lambda function
        lambda_function = aws.lambda_.Function(
            f"{name}-{stack_name}-api-stats",
            # Container image configuration
            package_type="Image",
            image_uri=image_uri,
            role=lambda_role.arn,
            
            # Function configuration
            timeout=300,                   # 5 minutes
            memory_size=512,              # Memory in MB
            architectures=["x86_64"],
            
            # VPC configuration (commented out like your original)
            # vpc_config=aws.lambda_.FunctionVpcConfigArgs(
            #     subnet_ids=subnet_ids,
            #     security_group_ids=[security_group_id]
            # ),
            
            # Environment variables
            environment=aws.lambda_.FunctionEnvironmentArgs(
                variables={
                    "DB_SSM_PREFIX": db_ssm_prefix
                }
            ),

            # Resource dependencies - include ECR policy
            opts=pulumi.ResourceOptions(
                depends_on=[
                    api_stats_ecr_repo,
                    ecr_policy,
                    basic_execution_attachment,
                    vpc_execution_attachment,
                    custom_policy_attachment
                ]
            ),
            
            # Tags
            tags={
                "Name": f"{name}-{stack_name}-api-stats",
                "Environment": stack_name
            }
        )

        # Export useful outputs
        pulumi.export("api_stats_function_name", lambda_function.name)
        pulumi.export("api_stats_function_arn", lambda_function.arn)
        pulumi.export("api_stats_function_invoke_arn", lambda_function.invoke_arn)

        return {
            "lambda_function": lambda_function,
            "lambda_role": lambda_role,
            "ecr_repository": api_stats_ecr_repo,
            "ecr_policy": ecr_policy,
            "image_uri": image_uri
        }
    return {
        "lambda_role": lambda_role,
        "ecr_repository": api_stats_ecr_repo,
        "ecr_policy": ecr_policy,
        "image_uri": image_uri
    }

def create_api_gateway_with_lambda(lambda_function, api_name="chatbot-stats-api", stack_name="dev"):
    """Create API Gateway with Lambda integration"""
    
    # Create REST API
    api = aws.apigateway.RestApi(
        f"{api_name}-{stack_name}-gateway",
        name=f"{api_name}-{stack_name}",
        description="Chatbot Statistics API Gateway",
        endpoint_configuration=aws.apigateway.RestApiEndpointConfigurationArgs(
            types="REGIONAL"
        ),
        tags={"Name": f"{api_name}-{stack_name}-gateway"}
    )

    # Create /stats resource
    stats_resource = aws.apigateway.Resource(
        f"{stack_name}-stats-resource",
        rest_api=api.id,
        parent_id=api.root_resource_id,
        path_part="stats",
    )

    # Create GET method for /stats
    stats_method = aws.apigateway.Method(
        f"{stack_name}-stats-get-method",
        rest_api=api.id,
        resource_id=stats_resource.id,
        http_method="GET",
        authorization="NONE",
        request_parameters={
            "method.request.querystring.days": False
        },
    )

    # Create OPTIONS method for CORS
    stats_options_method = aws.apigateway.Method(
        f"{stack_name}-stats-options-method",
        rest_api=api.id,
        resource_id=stats_resource.id,
        http_method="OPTIONS",
        authorization="NONE",
    )

    # Lambda integration for GET method
    stats_integration = aws.apigateway.Integration(
        f"{stack_name}-stats-integration",
        rest_api=api.id,
        resource_id=stats_resource.id,
        http_method=stats_method.http_method,
        integration_http_method="POST",
        type="AWS_PROXY",
        uri=lambda_function.invoke_arn,
    )

    # CORS integration for OPTIONS method
    stats_options_integration = aws.apigateway.Integration(
        f"{stack_name}-stats-options-integration",
        rest_api=api.id,
        resource_id=stats_resource.id,
        http_method=stats_options_method.http_method,
        type="MOCK",
        request_templates={
            "application/json": '{"statusCode": 200}'
        },
    )

    # Method response for OPTIONS (CORS)
    stats_options_method_response = aws.apigateway.MethodResponse(
        f"{stack_name}-stats-options-method-response",
        rest_api=api.id,
        resource_id=stats_resource.id,
        http_method=stats_options_method.http_method,
        status_code="200",
        response_headers={
            "method.response.header.Access-Control-Allow-Origin": True,
            "method.response.header.Access-Control-Allow-Methods": True,
            "method.response.header.Access-Control-Allow-Headers": True,
        },
    )

    # Integration response for OPTIONS (CORS)
    stats_options_integration_response = aws.apigateway.IntegrationResponse(
        f"{stack_name}-stats-options-integration-response",
        rest_api=api.id,
        resource_id=stats_resource.id,
        http_method=stats_options_method.http_method,
        status_code="200",
        response_headers={
            "method.response.header.Access-Control-Allow-Origin": "'*'",
            "method.response.header.Access-Control-Allow-Methods": "'GET,OPTIONS'",
            "method.response.header.Access-Control-Allow-Headers": "'Content-Type'",
        },
        opts=pulumi.ResourceOptions(depends_on=[stats_options_integration]),
    )

    # Grant API Gateway permission to invoke Lambda
    lambda_permission = aws.lambda_.Permission(
        f"{stack_name}-api-gateway-lambda-permission",
        function=lambda_function.name,
        action="lambda:InvokeFunction",
        principal="apigateway.amazonaws.com",
        source_arn=pulumi.Output.concat(api.execution_arn, "/*/*"),
    )

    # Create deployment
    deployment = aws.apigateway.Deployment(
        f"{stack_name}-api-deployment",
        rest_api=api.id,
        stage_name="prod",
        opts=pulumi.ResourceOptions(
            depends_on=[
                stats_integration,
                stats_options_integration_response
            ]
        ),
    )

    # Construct API URL
    api_url = pulumi.Output.concat(
        "https://", api.id, ".execute-api.", aws.config.region, ".amazonaws.com/prod/stats"
    )

    # Export API Gateway information
    pulumi.export("api_gateway_id", api.id)
    pulumi.export("api_gateway_url", api_url)

    return {
        "api": api,
        "deployment": deployment,
        "api_url": api_url
    }