import pulumi
import pulumi_aws as aws
import json
import subprocess
import os

class DockerImageProvider(pulumi.dynamic.ResourceProvider):
    """
    Custom provider that ensures Docker build completes before returning
    """
    
    def create(self, inputs):
        repo_url = inputs["repo_url"]
        repo_name = inputs["repo_name"] 
        region = inputs["region"]
        image_tag = inputs["image_tag"]
        lambda_dir = inputs["lambda_dir"]
        
        print(f"Starting Docker build for {repo_name}...")
        
        # Find the Lambda function directory
        current_dir = os.getcwd()
        possible_paths = [
            os.path.join(current_dir, "lambda_functions", "message_processor"),
            os.path.join(current_dir, "..", "lambda_functions", "message_processor"),
            os.path.join(current_dir, "message_processor"),
        ]
        
        actual_lambda_dir = None
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path) and os.path.isfile(os.path.join(abs_path, "Dockerfile")):
                actual_lambda_dir = abs_path
                break
        
        if actual_lambda_dir is None:
            raise Exception(f"Could not find Lambda function directory with Dockerfile. Tried: {possible_paths}")
        
        print(f"Found Lambda function directory: {actual_lambda_dir}")
        
        # Build and push commands
        commands = [
            f"cd '{actual_lambda_dir}' && docker buildx build --platform linux/amd64 -t {repo_name}:{image_tag} . --load",
            f"aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin {repo_url}",
            f"docker tag {repo_name}:{image_tag} {repo_url}:{image_tag}",
            f"docker push {repo_url}:{image_tag}"
        ]
        
        for i, cmd in enumerate(commands):
            print(f"Executing step {i+1}: {cmd}")
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
                print(f"✅ Step {i+1} completed successfully")
                if result.stdout:
                    print(f"Output: {result.stdout}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Step {i+1} failed: {e}")
                print(f"Error: {e.stderr}")
                raise Exception(f"Docker command failed: {cmd}")
        
        # Return the image URI - this ensures the resource is "created" only after push completes
        image_uri = f"{repo_url}:{image_tag}"
        print(f"✅ Docker image successfully pushed: {image_uri}")
        
        return pulumi.dynamic.CreateResult(
            id_=f"{repo_name}-{image_tag}",
            outs={
                "image_uri": image_uri,
                "repo_url": repo_url,
                "image_tag": image_tag
            }
        )
    
    def update(self, id, old_inputs, new_inputs):
        # For updates, just rebuild and push
        return self.create(new_inputs)
    
    def delete(self, id, props):
        # Optionally delete the image from ECR
        print(f"Docker image resource {id} deleted (image remains in ECR)")
        return

class DockerImage(pulumi.dynamic.Resource):
    """
    Custom resource that wraps the DockerImageProvider
    """
    
    def __init__(self, name, repo_url, repo_name, region, image_tag, lambda_dir, opts=None):
        self.image_uri = None
        
        super().__init__(
            DockerImageProvider(),
            name,
            {
                "repo_url": repo_url,
                "repo_name": repo_name,
                "region": region,
                "image_tag": image_tag,
                "lambda_dir": lambda_dir
            },
            opts
        )

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
    - Docker image must already be built and pushed to ECR
    - Use the build_and_push_image() helper function or manual CLI commands
    
    Args:
        db_ssm_prefix: SSM parameter prefix for database config
        vpc_id: VPC ID for Lambda function
        subnet_ids: Subnet IDs for Lambda function
        security_group_id: Security group ID for Lambda function
        image_tag: Docker image tag (default: "latest")
    """

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

    # Build and push Docker image using custom resource
    # This will BLOCK until the Docker push is complete
    docker_image = DockerImage(
        f"{name}-{stack_name}-docker-image",
        repo_url=lambda_ecr_repo.repository_url,
        repo_name=f"{name}-{stack_name}-lambda-message-processor",
        region=region,
        image_tag=image_tag,
        lambda_dir="../lambda_functions/message_processor",
        opts=pulumi.ResourceOptions(depends_on=[lambda_ecr_repo])
    )
    pulumi.export("image_uri", docker_image.image_uri)



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

    # Create custom policy for SSM and Comprehend
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
                        "Resource": f"arn:aws:ssm:*:*:parameter{db_ssm_prefix}/*"
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
        )
    )

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
    
    # 4. Attach custom policy
    custom_policy_attachment = aws.iam.RolePolicyAttachment(
        f"{name}-{stack_name}-custom-policy",
        role=lambda_role.name,
        policy_arn=lambda_policy.arn
    )


    lambda_function = aws.lambda_.Function(
        f"{name}-{stack_name}-message-processor",
        # For container images, these are the required parameters:
        package_type="Image",           # This tells Lambda it's a container
        image_uri=docker_image.image_uri,           # The ECR image URI
        role=lambda_role.arn,          # IAM role ARN
        
        # Optional parameters:
        timeout=300,                   # 5 minutes
        memory_size=512,              # Memory in MB
        
        # VPC configuration (if needed)
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
        # Container-specific configurations
        architectures=["x86_64"],
        opts=pulumi.ResourceOptions(
            depends_on=[
                docker_image,
                basic_execution_attachment,
                vpc_execution_attachment,
                custom_policy_attachment
                ]  # Ensure ECR repo exists before creating function
        ),
        
        # Tags
        tags={
            "Name": f"{name}-{stack_name}-message-processor",
            "Environment": stack_name
        }
    )

    # Export useful outputs
    pulumi.export("lambda_function_name", lambda_function.name)
    pulumi.export("ecr_repository_url", lambda_ecr_repo.repository_url)
    pulumi.export("image_uri", docker_image.image_uri)

    return lambda_function


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
