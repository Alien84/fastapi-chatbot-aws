import json
import pulumi
import pulumi_aws as aws

def create_message_processor_lambda(
        name,
        stack_name,
        db_ssm_prefix, 
        vpc_id, 
        subnet_ids, 
        security_group_id,
        region,
        image_tag="latest"
        ):
    """
    Creates a Lambda function using a Docker container.
    
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
        image_tag: Docker image tag (default: "latest")
    """

    # Create ECR repository (CI/CD pipeline will push to this)
    lambda_ecr_repo = aws.ecr.Repository(
        f"{name}-{stack_name}-lambda-message-processor",
        name=f"{name}-{stack_name}-lambda-message-processor",
        image_tag_mutability="MUTABLE",
        image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
            scan_on_push=True,
        ),
        force_delete=True,  # Allow deletion even if images exist
        tags={"Name": f"{name}-{stack_name}-lambda-message-processor"}
    )
    
    # Export the ECR repository information for CI/CD pipeline
    pulumi.export("lambda_ecr_repo_url", lambda_ecr_repo.repository_url)
    pulumi.export("lambda_ecr_repo_name", lambda_ecr_repo.name)
    pulumi.export("lambda_ecr_repo_arn", lambda_ecr_repo.arn)

    # Construct image URI - CI/CD pipeline should push image with this URI
    image_uri = pulumi.Output.concat(lambda_ecr_repo.repository_url, ":", image_tag)
    pulumi.export("lambda_image_uri", image_uri)

    # Create IAM role for Lambda
    lambda_role = aws.iam.Role(
        f"{name}-{stack_name}-message-processor-lambda-role",
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
        tags={"Name": f"{name}-{stack_name}-message-processor-lambda-role"}
    )

    # Create custom policy for SSM, Comprehend, and ECR access
    lambda_policy = aws.iam.Policy(
        f"{name}-{stack_name}-lambda-policy",
        policy=pulumi.Output.all(lambda_ecr_repo.arn).apply(
            lambda args: json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ssm:GetParameter",
                            "ssm:GetParameters",
                            "ssm:GetParametersByPath"
                        ],
                        "Resource": f"arn:aws:ssm:{region}:*:parameter{db_ssm_prefix}/*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "comprehend:DetectSentiment"
                        ],
                        "Resource": "*"
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
                        "Resource": args[0]  # ECR repository ARN
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
        tags={"Name": f"{name}-{stack_name}-lambda-policy"}
    )

    # Attach AWS managed policies
    basic_execution_attachment = aws.iam.RolePolicyAttachment(
        f"{name}-{stack_name}-basic-execution",
        role=lambda_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    )
    
    vpc_execution_attachment = aws.iam.RolePolicyAttachment(
        f"{name}-{stack_name}-vpc-execution",
        role=lambda_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
    )
    
    # Attach custom policy
    custom_policy_attachment = aws.iam.RolePolicyAttachment(
        f"{name}-{stack_name}-custom-policy",
        role=lambda_role.name,
        policy_arn=lambda_policy.arn
    )

    # Create Lambda function
    lambda_function = aws.lambda_.Function(
        f"{name}-{stack_name}-message-processor",
        # Container image configuration
        package_type="Image",
        image_uri=image_uri,
        role=lambda_role.arn,
        
        # Function configuration
        timeout=300,                   # 5 minutes
        memory_size=512,              # Memory in MB
        architectures=["x86_64"],
        
        # VPC configuration
        vpc_config=aws.lambda_.FunctionVpcConfigArgs(
            subnet_ids=subnet_ids,
            security_group_ids=[security_group_id]
        ),
        
        # Environment variables
        environment=aws.lambda_.FunctionEnvironmentArgs(
            variables={
                "DB_SSM_PREFIX": db_ssm_prefix
            }
        ),

        # Resource dependencies
        opts=pulumi.ResourceOptions(
            depends_on=[
                lambda_ecr_repo,
                basic_execution_attachment,
                vpc_execution_attachment,
                custom_policy_attachment
            ]
        ),
        
        # Tags
        tags={
            "Name": f"{name}-{stack_name}-message-processor",
            "Environment": stack_name
        }
    )

    # Export useful outputs
    pulumi.export("lambda_function_name", lambda_function.name)
    pulumi.export("lambda_function_arn", lambda_function.arn)
    pulumi.export("lambda_function_invoke_arn", lambda_function.invoke_arn)

    return {
        "lambda_function": lambda_function,
        "lambda_role": lambda_role,
        "ecr_repository": lambda_ecr_repo,
        "image_uri": image_uri
    }


def create_ecr_repository_only(name, stack_name):
    """
    Creates only the ECR repository for CI/CD pipeline to push images to.
    Use this if you want to create the repository separately from the Lambda function.
    
    Args:
        name: Base name for resources
        stack_name: Stack name for resource naming
    """
    lambda_ecr_repo = aws.ecr.Repository(
        f"{name}-{stack_name}-lambda-message-processor",
        name=f"{name}-{stack_name}-lambda-message-processor",
        image_tag_mutability="MUTABLE",
        image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
            scan_on_push=True,
        ),
        force_delete=True,
        tags={"Name": f"{name}-{stack_name}-lambda-message-processor"}
    )
    
    # Export repository information for CI/CD pipeline
    pulumi.export("lambda_ecr_repo_url", lambda_ecr_repo.repository_url)
    pulumi.export("lambda_ecr_repo_name", lambda_ecr_repo.name)
    pulumi.export("lambda_ecr_repo_arn", lambda_ecr_repo.arn)
    
    return lambda_ecr_repo