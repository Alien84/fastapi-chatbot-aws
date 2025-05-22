import pulumi
import pulumi_aws as aws
import base64

def create_ec2_instance(name, instance_type, key_name=None, user_data=None):
    # Get the latest Amazon Linux 2 AMI
    ami = aws.ec2.get_ami(
        most_recent=True,
        owners=["amazon"],
        filters=[
            aws.ec2.GetAmiFilterArgs(
                name="name",
                values=["amzn2-ami-hvm-*-x86_64-gp2"],
            ),
        ],
    )

    # Create a security group
    security_group = aws.ec2.SecurityGroup(
        f"{name}-security-group",
        description=f"Security group for {name}",
        ingress=[
            # SSH access
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=22,
                to_port=22,
                cidr_blocks=["0.0.0.0/0"],  # In production, restrict this
            ),
            # HTTP access
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=80,
                to_port=80,
                cidr_blocks=["0.0.0.0/0"],
            ),
        ],
        egress=[
            aws.ec2.SecurityGroupEgressArgs(
                protocol="-1",  # All protocols
                from_port=0,
                to_port=0,
                cidr_blocks=["0.0.0.0/0"],
            ),
        ],
    )

    # Create an EC2 instance
    instance = aws.ec2.Instance(
        name,
        instance_type=instance_type,
        ami=ami.id,
        key_name=key_name,
        vpc_security_group_ids=[security_group.id],
        user_data=user_data,
        tags={
            "Name": name,
            "Environment": "development",
        },
    )

    return instance, security_group