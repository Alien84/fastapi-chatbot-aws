import json
import hashlib
import pulumi
import pulumi_aws as aws
import pulumi_tls as tls
import base64
from modules.ec2 import create_ec2_instance
from modules.vpc import create_vpc
from modules.rds import create_rds_instance
from modules.secrets import create_secrets_with_kms, create_ssm_secrets



# Access configuration objects
aws_config = pulumi.Config("aws")
infra_config = pulumi.Config("infrastructure")

# Get values
region = aws_config.require("region") # "eu-west-2"
instance_type = infra_config.require("instanceType") # "t2.micro"
key_name = infra_config.require("keyName")
architecture = infra_config.require("architecture") #  # "single" or "autoscaling"
name = infra_config.require("name") # "chatbot"

stack_name = pulumi.get_stack()

pulumi.export("architecture", architecture)
pulumi.export("region", region)
pulumi.export("region1", aws.config.region)

# Generate a private key
private_key = tls.PrivateKey(
    f"{name}-{stack_name}-private-key",
    algorithm="RSA",
    rsa_bits=4096
)

key_pair = aws.ec2.KeyPair(
    f"{name}-{stack_name}-keypair", 
    key_name=f"{name}-{stack_name}-keypair",
    public_key=private_key.public_key_openssh,
    tags={
        "Name": f"{name}-{stack_name}-keypair",
        "Environment": stack_name,
        "Project": f"{name}"
        }
)

# Steps after deployment
# 1. Download the private key from AWS console
# 2. Save it to a file named "chatbot-keypair.pem"
# 3. Change permissions: chmod 400 chatbot-keypair.pem
# 4. SSH into the instance: ssh -i chatbot-keypair.pem ec2-user@<instance-public-ip>
# pulumi stack output private_key_pem --show-secrets > chatbot-dev-keypair.pem
# chmod 400 chatbot-keypair.pem

pulumi.export("private_key_id", key_pair.key_pair_id)
pulumi.export("private_key_pem", private_key.private_key_pem)


# Create an ECR repository for the application
ecr_repository = aws.ecr.Repository(
     f"{name}-{stack_name}-app",
    name= f"{name}-{stack_name}-app",
    image_tag_mutability="MUTABLE",
    image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
        scan_on_push=True,
    ),
    force_delete=True,  # This allows deletion with images
    tags={"Name": f"{name}-{stack_name}-app"},
)

# Create a lifecycle policy to manage image retention
ecr_lifecycle_policy = aws.ecr.LifecyclePolicy(
     f"{name}-{stack_name}-app-lifecycle",
    repository=ecr_repository.name,
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
        "rules": [{
            "rulePriority": 1,
            "selection": {
                "tagStatus": "any",
                "countType": "sinceImagePushed",
                "countUnit": "days",
                "countNumber": 1
            },
            "action": {"type": "expire"}
        }]
    }""",
    opts=pulumi.ResourceOptions(depends_on=[ecr_repository])
)

# Export the ECR repository URL
pulumi.export("ecr_repository_url", ecr_repository.repository_url)
pulumi.export("ecr_repository_name", ecr_repository.name)

# Read the user data script
with open("user_data.sh", "r") as f:
    user_data_template = f.read()

# Create VPC and networking components
network = create_vpc(name=name, stack_name=stack_name)

# Create a security group for app server within the VPC
web_sg = aws.ec2.SecurityGroup(
    f"{name}-{stack_name}-web-sg",
    vpc_id=network["vpc"].id,
    description="Allow web traffic",
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=80,
            to_port=80,
            cidr_blocks=["0.0.0.0/0"],
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=443,
            to_port=443,
            cidr_blocks=["0.0.0.0/0"],
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=22,
            to_port=22,
            cidr_blocks=["0.0.0.0/0"],  # In production, restrict this
        ),
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
        ),
    ],
)

# Create a security group for db within the VPC
db_sg = aws.ec2.SecurityGroup(
    f"{name}-{stack_name}-db-sg",
    vpc_id=network["vpc"].id,
    description="Allow database traffic",
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=5432,  # PostgreSQL port
            to_port=5432,
            security_groups=[web_sg.id],  # Only allow access from web servers
        ),
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
        ),
    ],
    tags={
        "Name": f"{name}-{stack_name}-db-sg",
        "Environment": stack_name,
        "Project": f"{name}"
        },
)


# Create the RDS instance
database = create_rds_instance(
    name,
    network["vpc"].id,
    # [subnet.id for subnet in network["private_subnets"]],
    [subnet.id for subnet in network["public_subnets"]],
    [db_sg.id],
    stack_name=stack_name
)

# Create secrets for database credentials
# NOTE -- Method #1: Apply the user data script with database credentials directly
# user_data = pulumi.Output.all(
#     database["instance"].endpoint,
#     database["username"],
#     database["password"],
#     database["database"]
# ).apply(
#     lambda args: user_data_template.replace("DB_HOST_PLACEHOLDER", args[0].split(':')[0])
#                           .replace("DB_PORT_PLACEHOLDER", args[0].split(':')[1])
#                           .replace("DB_NAME_PLACEHOLDER", args[3])
#                           .replace("DB_USER_PLACEHOLDER", args[1])
#                           .replace("DB_PASS_PLACEHOLDER", args[2])
# )


# NOTE -- Method #2: Using AWS Secrets Manager (NOTE this is not free)
# db_secrets = create_secrets_with_kms(
#     f"{name}-{stack_name}-db-credentials",
#     {
#         "username": database["username"],
#         "password": database["password"],
#         "host": database["instance"].address,
#         "port": database["instance"].port,
#         "dbname": database["database"],
#     },
#     stack_name=stack_name,
# )
# # Export the secret name for reference
# pulumi.export("db_secret_name", db_secrets["secret"].name)

# Process the user data script with environment variables
# user_data = pulumi.Output.all(db_secrets["secret"].name).apply(
#     lambda args: user_data_template.replace("${DB_SECRET_NAME}", args[0])
# )

# Create secrets for database credentials using ssm
# NOTE -- Method #3: Using AWS SSM Parameter Store (Standard tier is free)
db_secrets = create_ssm_secrets(
    "db",
    {
        "username": database["username"],
        "password": database["password"],
        "host": database["instance"].address,
        "port": database["instance"].port.apply(lambda p: str(p)),
        "dbname": database["database"],
    },
    stack_name=stack_name,
)

# Export the secret name for reference
pulumi.export("db_param_path", f"/{name}/{stack_name}/db")


# Process the user data script with SSM parameter path

# If you're using aws.ec2.Instance, you do not need to Base64 encode user_data manually. Pulumi does it for you.
# If You ARE Using a Launch Template (e.g., for Auto Scaling), AWS expects Base64, but you need to manually wrap it into an Output



# user_data = pulumi.Output.secret(
#     user_data_template.replace("${DB_PARAM_PATH}", f"/{name}/{stack_name}/db")
# )
# Create the SSM parameter prefix
ssm_prefix = pulumi.Output.concat("/", name, "/", stack_name, "/db")

# Process the user data script with environment variables
# Process the user data script with environment variables
user_data = pulumi.Output.all(
    ssm_prefix,
    ecr_repository.repository_url,
    ecr_repository.name,
    aws.config.region
).apply(
    lambda args: user_data_template
    .replace("${DB_SSM_PREFIX}", args[0])
    .replace("${ECR_REPOSITORY_URL}", args[1])
    .replace("${ECR_REPOSITORY_NAME}", args[2])
    .replace("${AWS_REGION}", args[3])
    .replace("${name}", name)  # Make sure to replace these as well
    .replace("${stack_name}", stack_name)
)
user_data_base64 = user_data.apply(
    lambda data: base64.b64encode(data.encode("utf-8")).decode("utf-8")
)

# Generate a hash of the user_data to trigger changes
user_data_hash = user_data.apply(
    lambda data: hashlib.sha256(data.encode('utf-8')).hexdigest()
)
# user_data_hash = pulumi.Output.apply(
#     lambda data: hashlib.md5(data.encode("utf-8")).hexdigest(),
#     user_data
# )


# Create an IAM role for EC2 instances
ec2_role = aws.iam.Role(
    f"{name}-{stack_name}-ec2-role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
                "Service": "ec2.amazonaws.com",
            },
        }],
    }),
)

# NOTE Create a policy for Secrets Manager access
# secrets_policy = aws.iam.Policy(
#     f"{name}-{stack_name}-secrets-policy",
#     policy=pulumi.Output.all(db_secrets["secret"].arn).apply(
#         lambda args: json.dumps({
#             "Version": "2012-10-17",
#             "Statement": [{
#                 "Effect": "Allow",
#                 "Action": [
#                     "secretsmanager:GetSecretValue",
#                     "secretsmanager:DescribeSecret",
#                 ],
#                 "Resource": args[0],
#             }],
#         })
#     ),
# )


# NOTE Create a policy for SSM Parameter Store access instead of Secrets Manager
secrets_policy = aws.iam.Policy(
    f"{name}-{stack_name}-ssm-policy",
    policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:GetParametersByPath",
                "ssm:DescribeParameters"
            ],
            "Resource": [
                f"arn:aws:ssm:eu-west-2:555576841436:parameter/{name}/{stack_name}/db",
                f"arn:aws:ssm:eu-west-2:555576841436:parameter/{name}/{stack_name}/db/*",
            ],
        }],
    }),
)
# Other code for ssm-policy
# ssm_policy = aws.iam.Policy(
#     f"{name}-{stack_name}-ssm-policy",
#     policy=pulumi.Output.all(stack_name).apply(
#         lambda args: json.dumps({
#             "Version": "2012-10-17",
#             "Statement": [
#                 {
#                     "Effect": "Allow",
#                     "Action": [
#                         "ssm:GetParameter",
#                         "ssm:GetParameters",
#                         "ssm:GetParametersByPath",
#                         "ssm:DescribeParameters"
#                     ],
#                     "Resource": [
#                         f"arn:aws:ssm:{aws.config.region}:*:parameter/{args[0]}/db/*"
#                     ]
#                 }
#             ],
#         })
#     ),
# )

# Attach the policy to the role
role_policy_attachment = aws.iam.RolePolicyAttachment(
    f"{name}-{stack_name}-role-policy-attachment",
    role=ec2_role.name,
    policy_arn=secrets_policy.arn,
)

# Create a CloudWatch log group
log_group = aws.cloudwatch.LogGroup(
    f"{name}-{stack_name}-logs",
    name=f"/aws/ec2/{name}-{stack_name}",
    retention_in_days=30,
)

# Update IAM policy to allow CloudWatch Logs access
logs_policy = aws.iam.Policy(
    f"{name}-{stack_name}-logs-policy",
    policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogStreams",
            ],
            "Resource": "*",
        }],
    }),
)

# Attach the logs policy to the role
logs_policy_attachment = aws.iam.RolePolicyAttachment(
    f"{name}-{stack_name}logs-policy-attachment",
    role=ec2_role.name,
    policy_arn=logs_policy.arn,
)

# Create a comprehensive ECR policy
ecr_policy = aws.iam.Policy(
    "ecr-policy",
    policy=pulumi.Output.all(ecr_repository.arn).apply(
        lambda args: json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ecr:GetAuthorizationToken"
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
                    "Resource": args[0]
                }
            ],
        })
    ),
)

# Attach the ECR policy to the EC2 role
ecr_policy_attachment = aws.iam.RolePolicyAttachment(
    f"{name}-{stack_name}-ecr-policy-attachment",
    role=ec2_role.name,
    policy_arn=ecr_policy.arn,
)

"""
to ensure SSM commands work properly through GitHub Actions, you need to make sure your instance has the correct IAM permissions. You'll need to add the SSM managed policy to your IAM role.
You should also verify that your instance appears in SSM by checking the Systems Manager console or running this AWS CLI command
aws ssm describe-instance-information --query "InstanceInformationList[?InstanceId=='YOUR_INSTANCE_ID']"
"""
# Add SSM permissions to your EC2 IAM role
ssm_managed_policy_attachment = aws.iam.RolePolicyAttachment(
    "ssm-managed-policy-attachment",
    role=ec2_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
)

# Create an instance profile
instance_profile = aws.iam.InstanceProfile(
    f"{name}-{stack_name}-instance-profile",
    role=ec2_role.name,
)


# Create an EC2 instance using default vpc
# instance, security_group = create_ec2_instance(
#     f"{name}-{stack_name}-server",
#     instance_type=instance_type,
#     key_name=key_pair.key_name,
#     user_data=user_data,
# )


# Create an SNS topic for notifications
notification_topic = aws.sns.Topic(
    f"{name}-{stack_name}-notification-topic",
    name=f"{name}-{stack_name}-notifications",
)

# Create an email subscription
email_subscription = aws.sns.TopicSubscription(
    "email-subscription",
    topic=notification_topic.arn,
    protocol="email",
    endpoint="aknari.ali.com@gmail.com",  # Replace with your email
)


if architecture == "single":
    # Single instance creation:  Uncomment out if you comment out auto-scaling part

    # Create an EC2 instance in a public subnet
    instance = aws.ec2.Instance(
        f"{name}-{stack_name}-server",
        instance_type=instance_type,
        ami=aws.ec2.get_ami(
            most_recent=True,
            owners=["amazon"],
            filters=[
                aws.ec2.GetAmiFilterArgs(
                    name="name",
                    values=["amzn2-ami-hvm-*-x86_64-gp2"],
                ),
            ],
        ).id,
        key_name=key_pair.key_name,
        subnet_id=network["public_subnets"][0].id,
        vpc_security_group_ids=[web_sg.id],
        iam_instance_profile=instance_profile.name,
        user_data=user_data,
        opts=pulumi.ResourceOptions(
            depends_on=list(db_secrets.values()) + [ecr_repository], # NOTE Pulumi will correctly wait for all the SSM parameters to be created before launching the EC2 instance and running user_data.
            delete_before_replace=True  # Ensures Pulumi destroys and recreates the instance
        ),
        # Enable detailed monitoring (1-minute intervals instead of 5)
        monitoring=True,
        tags={
            "Name": f"{name}-{stack_name}-server",
            "Environment": stack_name,
            "Project": f"{name}",
            "UserDataHash": user_data_hash  # This tag forces instance replacement when user_data changes,
            },
    )

    # Create a CloudWatch dashboard
    dashboard = aws.cloudwatch.Dashboard(
        f"{name}-{stack_name}-dashboard",
        dashboard_name=f"{name}-{stack_name}-Dashboard",
        dashboard_body=pulumi.Output.all(instance.id, database["instance"].id).apply(
            lambda args: json.dumps({
                "widgets": [
                    {
                        "type": "metric",
                        "x": 0,
                        "y": 0,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "metrics": [
                                ["AWS/EC2", "CPUUtilization", "InstanceId", args[0]]
                            ],
                            "period": 300,
                            "stat": "Average",
                            "region": aws.config.region,
                            "title": "EC2 Instance CPU",
                        },
                    },
                    {
                        "type": "metric",
                        "x": 12,
                        "y": 0,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "metrics": [
                                ["AWS/EC2", "NetworkIn", "InstanceId", args[0]],
                                ["AWS/EC2", "NetworkOut", "InstanceId", args[0]]
                            ],
                            "period": 300,
                            "stat": "Average",
                            "region": aws.config.region,
                            "title": "Network Traffic",
                        },
                    },
                    {
                        "type": "metric",
                        "x": 0,
                        "y": 6,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "metrics": [
                                ["CWAgent", "mem_used_percent", "InstanceId", args[0]]
                            ],
                            "period": 300,
                            "stat": "Average",
                            "region": aws.config.region,
                            "title": "Memory Usage",
                        },
                    },
                    {
                        "type": "metric",
                        "x": 12,
                        "y": 6,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "metrics": [
                                ["CWAgent", "disk_used_percent", "InstanceId", args[0], "path", "/"]
                            ],
                            "period": 300,
                            "stat": "Average",
                            "region": aws.config.region,
                            "title": "Disk Usage",
                        },
                    },
                    {
                        "type": "log",
                        "x": 0,
                        "y": 12,
                        "width": 24,
                        "height": 6,
                        "properties": {
                            "query": f"SOURCE '/aws/ec2/{name}-{stack_name}' | fields @timestamp, @message\n| sort @timestamp desc\n| limit 100",
                            "region": aws.config.region,
                            "title": "Recent Logs",
                            "view": "table"
                        }
                    }
                ],
            })
        ),
    )

    # Create CloudWatch alarms for for the single EC2 instance
    high_cpu_alarm = aws.cloudwatch.MetricAlarm(
        f"{name}-{stack_name}-high-cpu-alarm",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=2,
        metric_name="CPUUtilization",
        namespace="AWS/EC2",
        period=300,
        statistic="Average",
        threshold=70,
        alarm_description="Alarm when CPU exceeds 70%",
        dimensions={"InstanceId": instance.id},
        # alarm_actions=["notification_topic.arn"],  # Replace with your SNS topic ARN
    )

    low_cpu_alarm = aws.cloudwatch.MetricAlarm(
        f"{name}-{stack_name}-low-cpu-alarm",
        comparison_operator="LessThanThreshold",
        evaluation_periods=2,
        metric_name="CPUUtilization",
        namespace="AWS/EC2",
        period=300,
        statistic="Average",
        threshold=30,
        alarm_description="Scale down when CPU < 30%",
        dimensions={"InstanceId": instance.id},
        # alarm_actions=["notification_topic.arn"],
    )

    # Create a CloudWatch alarm for RDS high CPU
    rds_cpu_alarm = aws.cloudwatch.MetricAlarm(
        f"{name}-{stack_name}-rds-cpu-alarm",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=2,
        metric_name="CPUUtilization",
        namespace="AWS/RDS",
        period=300,
        statistic="Average",
        threshold=80,
        alarm_description="Alarm when RDS CPU exceeds 80%",
        dimensions={"DBInstanceIdentifier": database["instance"].id},
        # alarm_actions=["notification_topic.arn"],
    )

    memory_alarm = aws.cloudwatch.MetricAlarm(
        f"{name}-{stack_name}-memory-alarm",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=2,
        metric_name="mem_used_percent",
        namespace="CWAgent",
        period=300,
        statistic="Average",
        threshold=85,
        alarm_description="Alarm when memory usage exceeds 85%",
        dimensions={"InstanceId": instance.id},
        # alarm_actions=["notification_topic.arn"],  # Replace with your SNS topic ARN
    )

    disk_alarm = aws.cloudwatch.MetricAlarm(
        f"{name}-{stack_name}-disk-alarm",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=2,
        metric_name="disk_used_percent",
        namespace="CWAgent",
        period=300,
        statistic="Average",
        threshold=85,
        alarm_description="Alarm when disk usage exceeds 85%",
        dimensions={"InstanceId": instance.id, "path": "/"},
        # alarm_actions=["notification_topic.arn"],  # Replace with your SNS topic ARN
    )
    


    # Export the instance's public IP and DNS
    pulumi.export("instance_id", instance.id)
    pulumi.export("public_ip", instance.public_ip)
    pulumi.export("public_dns", instance.public_dns)
    pulumi.export("application_url", pulumi.Output.concat("http://", instance.public_dns))
    pulumi.export("db_endpoint", database["instance"].endpoint)
    pulumi.export("db_username", database["username"])
    pulumi.export("db_password", database["password"])
    pulumi.export("db_name", database["database"])
    pulumi.export("db_ssm_prefix", pulumi.Output.concat("/", stack_name, "/db"))

else:

    # Create a launch template for auto scaling
    # This defines how EC2 instances should be launched
    launch_template = aws.ec2.LaunchTemplate(
        f"{name}-{stack_name}-launch-template",
        image_id=aws.ec2.get_ami(
            most_recent=True,
            owners=["amazon"],
            filters=[
                aws.ec2.GetAmiFilterArgs(
                    name="name",
                    values=["amzn2-ami-hvm-*-x86_64-gp2"],
                ),
            ],
        ).id,
        instance_type=instance_type,
        key_name=key_pair.key_name,
        vpc_security_group_ids=[web_sg.id],
        user_data=user_data_base64,
        iam_instance_profile=aws.ec2.LaunchTemplateIamInstanceProfileArgs(
            name=instance_profile.name,
        ),
        monitoring=aws.ec2.LaunchTemplateMonitoringArgs(
            enabled=True,  # Enable detailed monitoring
        ),
        opts=pulumi.ResourceOptions(
            depends_on=list(db_secrets.values()) + [ecr_repository],
            delete_before_replace=True  # Ensures Pulumi destroys and recreates the template
        ),
        tag_specifications=[
            aws.ec2.LaunchTemplateTagSpecificationArgs(
                resource_type="instance",
                tags={
                    "Name": f"{name}-{stack_name}-server",
                    "Environment": stack_name,
                    "Project": f"{name}",
                    "UserDataHash": user_data_hash,
                },
            ),
        ],
    )


    # Create a load balancer security group
    # Allows public HTTP (80) and HTTPS (443) traffic to reach the load balancer
    lb_sg = aws.ec2.SecurityGroup(
        f"{name}-{stack_name}-lb-sg",
        vpc_id=network["vpc"].id,
        description="Allow web traffic to load balancer",
        ingress=[
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=80,
                to_port=80,
                cidr_blocks=["0.0.0.0/0"],
            ),
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=443,
                to_port=443,
                cidr_blocks=["0.0.0.0/0"],
            ),
        ],
        egress=[
            aws.ec2.SecurityGroupEgressArgs(
                protocol="-1",
                from_port=0,
                to_port=0,
                cidr_blocks=["0.0.0.0/0"],
            ),
        ],
    )

    # Allow web servers to receive traffic from the load balancer
    # Allow Load Balancer to Talk to EC2s: This rule allows the web server security group (web_sg) to accept traffic from the load balancer on port 80.
    web_sg_rule = aws.ec2.SecurityGroupRule(
        f"{name}-{stack_name}-web-sg-rule-from-lb",
        type="ingress",
        from_port=80,
        to_port=80,
        protocol="tcp",
        security_group_id=web_sg.id,
        source_security_group_id=lb_sg.id,
    )

    # Create an application load balancer (ALB)
    # Creates an Application Load Balancer:
        # Public-facing (not internal)
        # Spread across multiple public subnets
    load_balancer = aws.lb.LoadBalancer(
        f"{name}-{stack_name}-lb",
        internal=False,
        load_balancer_type="application",
        security_groups=[lb_sg.id],
        subnets=[subnet.id for subnet in network["public_subnets"]],
        enable_deletion_protection=False,
        tags={
            "Name": f"{name}-{stack_name}-lb",
            "Environment": stack_name,
            "Project": f"{name}",
            },
    )

    # Create a target group for the ALB
    # Targets are EC2 instances listening on port 80.
    target_group = aws.lb.TargetGroup(
        f"{name}-{stack_name}-tg",
        port=80,
        protocol="HTTP",
        vpc_id=network["vpc"].id,
        target_type="instance",
        health_check=aws.lb.TargetGroupHealthCheckArgs(
            enabled=True,
            path="/",
            port="80",
            protocol="HTTP",
            healthy_threshold=3,
            unhealthy_threshold=3,
            timeout=5,
            interval=30,
        ),
    )

    # Create a listener: 1- Listens on port 80 of the ALB. 2- Forwards traffic to the target group.
    listener = aws.lb.Listener(
        f"{name}-{stack_name}-listener",
        load_balancer_arn=load_balancer.arn,
        port=80,
        default_actions=[
            aws.lb.ListenerDefaultActionArgs(
                type="forward",
                target_group_arn=target_group.arn,
            ),
        ],
    )

    # Create an auto scaling group
        # Launches 2–4 EC2 instances based on load.
        # Uses the launch_template.
        # Spreads instances across the public subnets.
        # Attaches to the target group, so traffic can be load-balanced.
    auto_scaling_group = aws.autoscaling.Group(
        f"{name}-{stack_name}-asg",
        max_size=4,
        min_size=2,
        desired_capacity=2,
        vpc_zone_identifiers=[subnet.id for subnet in network["public_subnets"]],
        target_group_arns=[target_group.arn],
        health_check_type="ELB",
        health_check_grace_period=300,
        launch_template=aws.autoscaling.GroupLaunchTemplateArgs(
            id=launch_template.id,
            version="$Latest",
        ),
        opts=pulumi.ResourceOptions(
            depends_on=[launch_template] + list(db_secrets.values()) + [ecr_repository],
        ),
        tags=[
            aws.autoscaling.GroupTagArgs(
                key="Name",
                value=f"{name}-server",
                propagate_at_launch=True,
            ),
        ],
    )

    # Create scaling policies
    # Define how many instances to add or remove when scaling is triggered:
        # Scale up: Add 1 instance.
        # Scale down: Remove 1 instance.
        # Both have a cooldown of 5 minutes (300 seconds).
    scale_up_policy = aws.autoscaling.Policy(
        f"{name}-{stack_name}-scale-up-policy",
        autoscaling_group_name=auto_scaling_group.name,
        adjustment_type="ChangeInCapacity",
        scaling_adjustment=1,
        cooldown=300,
    )

    scale_down_policy = aws.autoscaling.Policy(
        f"{name}-{stack_name}-scale-down-policy",
        autoscaling_group_name=auto_scaling_group.name,
        adjustment_type="ChangeInCapacity",
        scaling_adjustment=-1,
        cooldown=300,
    )

    # Create CloudWatch alarms for scaling
    # Set up CloudWatch alarms to trigger scaling:
        # High CPU (>70%) for 2 intervals → scale up.
        # Low CPU (<30%) for 2 intervals → scale down.
        # Based on average EC2 CPU usage over 5-minute periods.
    high_cpu_alarm = aws.cloudwatch.MetricAlarm(
        f"{name}-{stack_name}-high-cpu-alarm",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=2,
        metric_name="CPUUtilization",
        namespace="AWS/EC2",
        period=300,
        statistic="Average",
        threshold=70,
        alarm_description="Scale up when CPU > 70%",
        alarm_actions=[scale_up_policy.arn],
        dimensions={"AutoScalingGroupName": auto_scaling_group.name},
    )

    low_cpu_alarm = aws.cloudwatch.MetricAlarm(
        f"{name}-{stack_name}-low-cpu-alarm",
        comparison_operator="LessThanThreshold",
        evaluation_periods=2,
        metric_name="CPUUtilization",
        namespace="AWS/EC2",
        period=300,
        statistic="Average",
        threshold=30,
        alarm_description="Scale down when CPU < 30%",
        alarm_actions=[scale_down_policy.arn],
        dimensions={"AutoScalingGroupName": auto_scaling_group.name},
    )

    # Create a CloudWatch alarm for RDS high CPU
    rds_cpu_alarm = aws.cloudwatch.MetricAlarm(
        f"{name}-{stack_name}-rds-cpu-alarm",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=2,
        metric_name="CPUUtilization",
        namespace="AWS/RDS",
        period=300,
        statistic="Average",
        threshold=80,
        alarm_description="Alarm when RDS CPU exceeds 80%",
        dimensions={"DBInstanceIdentifier": database["instance"].id},
    )

    # Create a CloudWatch alarm for high 5xx errors
    error_alarm = aws.cloudwatch.MetricAlarm(
        f"{name}-{stack_name}-error-alarm",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=1,
        metric_name="HTTPCode_ELB_5XX_Count",
        namespace="AWS/ApplicationELB",
        period=300,
        statistic="Sum",
        threshold=10,
        alarm_description="Alarm when 5XX errors exceed 10 in 5 minutes",
        dimensions={"LoadBalancer": load_balancer.arn_suffix},
    )


    # Create a CloudWatch dashboard
    dashboard = aws.cloudwatch.Dashboard(
        f"{name}-{stack_name}-dashboard",
        dashboard_name=f"{name}-{stack_name}-Dashboard",
        dashboard_body=pulumi.Output.all(
            auto_scaling_group.name, 
            database["instance"].id,
            load_balancer.arn_suffix
            ).apply(lambda args: json.dumps({
                "widgets": [
                    {
                        "type": "metric",
                        "x": 0,
                        "y": 0,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "metrics": [
                                ["AWS/EC2", "CPUUtilization", "AutoScalingGroupName", args[0]]
                            ],
                            "period": 300,
                            "stat": "Average",
                            "region": aws.config.region,
                            "title": "EC2 Instance CPU",
                        },
                    },
                    {
                        "type": "metric",
                        "x": 12,
                        "y": 0,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "metrics": [
                                ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", args[1]]
                            ],
                            "period": 300,
                            "stat": "Average",
                            "region": aws.config.region,
                            "title": "RDS Instance CPU",
                        },
                    },
                    {
                        "type": "metric",
                        "x": 0,
                        "y": 6,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "metrics": [
                                ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", args[2]]
                            ],
                            "period": 300,
                            "stat": "Sum",
                            "region": aws.config.region,
                            "title": "Load Balancer Request Count",
                        },
                    },
                    {
                        "type": "metric",
                        "x": 12,
                        "y": 6,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "metrics": [
                                ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", args[2]]
                            ],
                            "period": 300,
                            "stat": "Average",
                            "region": aws.config.region,
                            "title": "Load Balancer Response Time",
                        },
                    },
                    {
                        "type": "log",
                        "x": 0,
                        "y": 12,
                        "width": 24,
                        "height": 6,
                        "properties": {
                            "query": f"SOURCE '/aws/ec2/{name}-{stack_name}' | fields @timestamp, @message\n| sort @timestamp desc\n| limit 100",
                            "region": aws.config.region,
                            "title": "Recent Logs",
                            "view": "table"
                        }
                    }
                ],
            })
        ),
    )

    # Update exports
    pulumi.export("load_balancer_dns", load_balancer.dns_name)
    pulumi.export("application_url", pulumi.Output.concat("http://", load_balancer.dns_name))
    pulumi.export("db_ssm_prefix", pulumi.Output.concat("/", stack_name, "/db"))