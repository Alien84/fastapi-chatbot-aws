import pulumi
import pulumi_aws as aws
import json
import subprocess
import os

def create_message_processor_lambda(
        name,
        stack_name,
        db_ssm_prefix, 
        vpc_id, 
        subnet_ids, 
        security_group_id,
        region
        ):

    lambda_ecr_repo = aws.ecr.Repository(
        f"{name}-{stack_name}-lambda-message-processor",
        name= f"{name}-{stack_name}-lambda-message-processor",
        image_tag_mutability="MUTABLE",
        image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
            scan_on_push=True,
        ),
        force_delete=True,  # Allow deletion even if images exist
        tags={"Name": f"{name}-{stack_name}-lambda-message-processor"}
    )
    # Export the ECR repository URL
    pulumi.export("lambda_ecr_repo_url", lambda_ecr_repo.repository_url)
    pulumi.export("lambda_ecr_repo_name", lambda_ecr_repo.name)

    # Build and push Docker image
    docker_image = aws.ecr.get_authorization_token_output()
    image_tag = "latest"

    # Build the Docker image locally and push to ECR
    docker_build_script = f"""
        #!/bin/bash
        set -e

        # Get repository URI
        REPO_URI={lambda_ecr_repo.repository_url}

        # Build the Docker image
        echo "Building Docker image..."
        cd ../lambda_functions/message_processor
        # docker build -t {lambda_ecr_repo.name}:{image_tag} .
        docker buildx build --platform linux/amd64 -t lambda-psycopg2-test {lambda_ecr_repo.name}:{image_tag} . --load

        # Login to ECR
        echo "Logging in to ECR..."
        aws ecr get-login-password --region {region.name} | docker login --username AWS --password-stdin $REPO_URI


        # Tag and push the image
        echo "Tagging and pushing image..."
        docker tag {lambda_ecr_repo}:{image_tag} $REPO_URI:{image_tag}
        docker push $REPO_URI:{image_tag}

        echo "Docker image pushed successfully!"
        """
    
    # Execute the build script
    build_result = subprocess.run(
        docker_build_script,
        shell=True,
        capture_output=True,
        text=True
    )


    # result = subprocess.run([package_script], cwd="../lambda_functions/message_processor", 
    #                           capture_output=True, text=True)

    # if build_result.returncode != 0:
    #     print(f"Docker build failed: {build_result.stderr}")
    #     raise Exception("Docker build failed")
    # else:
    #     print("Docker image built and pushed successfully")
    
    # # Construct the image URI
    # image_uri = pulumi.Output.concat(
    #     current.account_id,
    #     ".dkr.ecr.",
    #     region.name,
    #     ".amazonaws.com/",
    #     ecr_repo.name,
    #     ":",
    #     image_tag
    # )








    # # Create IAM role for Lambda
    # lambda_role = aws.iam.Role(
    #     "message-processor-lambda-role",
    #     assume_role_policy=json.dumps({
    #         "Version": "2012-10-17",
    #         "Statement": [{
    #             "Action": "sts:AssumeRole",
    #             "Effect": "Allow",
    #             "Principal": {
    #                 "Service": "lambda.amazonaws.com",
    #             },
    #         }],
    #     }),
    # )

    # # Create custom policy for SSM and Comprehend
    # lambda_policy = aws.iam.Policy(
    #     "message-processor-lambda-policy",
    #     policy=json.dumps({
    #         "Version": "2012-10-17",
    #         "Statement": [
    #             {
    #                 "Effect": "Allow",
    #                 "Action": [
    #                     "ssm:GetParameter",
    #                     "ssm:GetParameters",
    #                     "ssm:GetParametersByPath"
    #                 ],
    #                 "Resource": f"arn:aws:ssm:*:*:parameter{db_ssm_prefix}/*"
    #             },
    #             {
    #                 "Effect": "Allow",
    #                 "Action": [
    #                     "comprehend:DetectSentiment"
    #                 ],
    #                 "Resource": "*"
    #             }
    #         ],
    #     }),
    # )

    # aws.iam.RolePolicyAttachment(
    #     "lambda-custom-policy-attachment",
    #     role=lambda_role.name,
    #     policy_arn=lambda_policy.arn,
    # )

    # # Attach VPC execution policy
    # aws.iam.RolePolicyAttachment(
    #     "lambda-vpc-execution",
    #     role=lambda_role.name,
    #     policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
    # )



    # # Create the Lambda function with container image
    # lambda_function = aws.lambda_.Function(
    #     "message-processor-lambda",
    #     role=lambda_role.arn,
    #     package_type="Image",  # Use container image instead of Zip
    #     code=aws.lambda_.FunctionCodeArgs(
    #         image_uri=image_uri,
    #     ),
    #     timeout=30,
    #     memory_size=512,  # Increased for container overhead
    #     environment=aws.lambda_.FunctionEnvironmentArgs(
    #         variables={
    #             "DB_SSM_PREFIX": db_ssm_prefix,
    #         },
    #     ),
    #     vpc_config=aws.lambda_.FunctionVpcConfigArgs(
    #         subnet_ids=subnet_ids,
    #         security_group_ids=[security_group_id],
    #     ),
    #     # Container-specific configurations
    #     architectures=["x86_64"],
    #     opts=pulumi.ResourceOptions(
    #         depends_on=[lambda_ecr_repo]  # Ensure ECR repo exists before creating function
    #     ),
    # )

    return 


def create_message_processor_lambda_v2(db_ssm_prefix, vpc_id, subnet_ids, security_group_id):
    """And here's an alternative version that uses Pulumi's docker.Image resource for a more integrated approach
       To use the integrated Docker approach, you'll need to install the Docker provider: pip install pulumi-docker
    """

    import pulumi_docker as docker
    # Calculate hash of source directory for versioning
    def calculate_source_hash(directory):
        import hashlib
        """Calculate hash of all files in source directory"""
        hash_obj = hashlib.md5()
        
        for root, dirs, files in os.walk(directory):
            for file in sorted(files):
                if not file.startswith('.'):  # Skip hidden files
                    file_path = os.path.join(root, file)
                    with open(file_path, 'rb') as f:
                        hash_obj.update(f.read())
        
        return hash_obj.hexdigest()[:8]  # Use first 8 characters
    source_hash = calculate_source_hash(lambda_source_path)

    # Configuration
    repo_name = "lambda-message-processor"
    
    # Build and tag image with version
    image_tags = ["latest", source_hash]
    
    # Get current AWS account ID and region
    current = aws.get_caller_identity()
    region = aws.get_region()
    
    # Create ECR repository
    lambda_ecr_repo = aws.ecr.Repository(
        "message-processor-ecr-repo",
        name=repo_name,
        image_tag_mutability="MUTABLE",
        image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
            scan_on_push=True,
        ),
        force_delete=True, # Allow deletion even if images exist (for dev)
        tags={"Name": "message-processor-lambda-repository"}
    )

    # Create lifecycle policy to manage image retention
    ecr_lifecycle_policy = aws.ecr.LifecyclePolicy(
        "lambda-ecr-lifecycle-policy",
        repository=lambda_ecr_repo.name,
        policy=json.dumps({
            "rules": [
                {
                    "rulePriority": 1,
                    "description": "Keep last 5 images",
                    "selection": {
                        "tagStatus": "any",
                        "countType": "sinceImagePushed",
                        "countUnit": "days",
                        "countNumber": 1
                    },
                    "action": {
                        "type": "expire"
                    }
                }
            ]
        }),
        opts=pulumi.ResourceOptions(depends_on=[lambda_ecr_repo])
    )
    
    # Get ECR authorization token
    ecr_token = aws.ecr.get_authorization_token_output()
    
    # Configure Docker provider to use ECR
    ecr_provider = docker.Provider(
        "ecr-provider",
        registry_auth=[docker.ProviderRegistryAuthArgs(
            address=lambda_ecr_repo.repository_url,
            username=ecr_token.user_name,
            password=ecr_token.password,
        )],
    )
    
    # Build and push Docker image using Pulumi Docker provider
    docker_image = docker.Image(
        "message-processor-image",
        build=docker.DockerBuildArgs(
            context="../lambda_functions/message_processor", # Path to your Dockerfile directory
            dockerfile="../lambda_functions/message_processor/Dockerfile",
            platform="linux/amd64",  # Ensure x86_64 architecture
            # Add labels for tracking
            labels={
                "version": source_hash,
                "created": pulumi.Output.concat("$(date -u +%Y-%m-%dT%H:%M:%SZ)"),
                "source": "pulumi-build",
            },
            args={
                # You can pass build args here if needed
                # "ARG_NAME": "value"
            },
            # Disable cache for development (remove in production)
            no_cache=False,
            # Build target for multi-stage builds
            # target="production",
        ),
        image_name=pulumi.Output.concat(
            lambda_ecr_repo.repository_url, ":", image_tags
        ),
        registry=docker.ImageRegistryArgs(
            server=lambda_ecr_repo.repository_url,
            username=ecr_token.user_name,
            password=ecr_token.password,
        ),
        opts=pulumi.ResourceOptions(
            provider=ecr_provider,
            depends_on=[lambda_ecr_repo],
        ),
    )

    # Also tag as latest
    latest_image = docker.Tag(
        "lambda-latest-tag",
        source_image=docker_image.image_name,
        target_image=pulumi.Output.concat(
            lambda_ecr_repo.repository_url, ":latest"
        ),
        opts=pulumi.ResourceOptions(provider=ecr_provider),
    )
    
    # Create IAM role for Lambda
    lambda_role = aws.iam.Role(
        "message-processor-lambda-role",
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
    )
    
    # Attach VPC execution policy
    aws.iam.RolePolicyAttachment(
        "lambda-vpc-execution",
        role=lambda_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
    )
    
    # Create custom policy for SSM and Comprehend
    lambda_policy = aws.iam.Policy(
        "message-processor-lambda-policy",
        policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ssm:GetParameter",
                        "ssm:GetParameters",
                        "ssm:GetParametersByPath"
                    ],
                    "Resource": f"arn:aws:ssm:*:*:parameter{db_ssm_prefix}/*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "comprehend:DetectSentiment"
                    ],
                    "Resource": "*"
                }
            ],
        }),
    )
    
    aws.iam.RolePolicyAttachment(
        "lambda-custom-policy-attachment",
        role=lambda_role.name,
        policy_arn=lambda_policy.arn,
    )
    
    # Create the Lambda function using the built container image
    lambda_function = aws.lambda_.Function(
        "message-processor-docker-lambda",
        role=lambda_role.arn,
        package_type="Image",
        image_uri=docker_image.image_name,
        timeout=30,
        memory_size=256,
        environment=aws.lambda_.FunctionEnvironmentArgs(
            variables={
                "DB_SSM_PREFIX": db_ssm_prefix,
                "IMAGE_VERSION": source_hash,
            },
        ),
        vpc_config=aws.lambda_.FunctionVpcConfigArgs(
            subnet_ids=subnet_ids,
            security_group_ids=[security_group_id],
        ),
        # Wait for the image to be pushed before creating the function
        opts=pulumi.ResourceOptions(depends_on=[docker_image]),
    )
    
    return {
        "function": lambda_function,
        "repository": lambda_ecr_repo,
        "image": docker_image,
        "latest_tag": latest_image,
        "source_hash": source_hash
    }
