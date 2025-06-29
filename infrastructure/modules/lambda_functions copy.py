import pulumi
import pulumi_aws as aws
import json
import subprocess
import os

def create_message_processor_lambda(db_ssm_prefix, vpc_id, subnet_ids, security_group_id):

    # Build the Lambda package
    package_script = "../lambda_functions/message_processor/package.sh"
    if os.path.exists(package_script):
        print("Building Lambda package...")
        result = subprocess.run([package_script], cwd="../lambda_functions/message_processor", 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Package build failed: {result.stderr}")
        else:
            print("Package built successfully")

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

    # Create the Lambda function with the packaged code
    lambda_function = aws.lambda_.Function(
        "message-processor-lambda",
        role=lambda_role.arn,
        runtime="python3.10",
        handler="lambda_function.lambda_handler",
        code=pulumi.FileArchive("../lambda_functions/message_processor/lambda-package.zip"),
        timeout=30,
        memory_size=256,
        environment=aws.lambda_.FunctionEnvironmentArgs(
            variables={
                "DB_SSM_PREFIX": db_ssm_prefix,
            },
        ),
        vpc_config=aws.lambda_.FunctionVpcConfigArgs(
            subnet_ids=subnet_ids,
            security_group_ids=[security_group_id],
        ),
    )

    return lambda_function