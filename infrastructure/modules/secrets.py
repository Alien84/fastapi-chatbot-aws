import pulumi
import pulumi_aws as aws
import json

def create_secrets_with_kms(name, secrets_dict):
    # Create a KMS key for encrypting secrets
    key = aws.kms.Key(
        f"{name}-key",
        description=f"KMS key for {name} secrets",
        deletion_window_in_days=10,
        enable_key_rotation=True,
        tags={"Name": f"{name}-key"},
    )
    
    # Create a Secrets Manager secret
    secret = aws.secretsmanager.Secret(
        f"{name}-secret",
        name=name,
        kms_key_id=key.id,
        tags={"Name": f"{name}-secret"},
    )
    
    # Create a secret version with the provided secrets
    secret_version = aws.secretsmanager.SecretVersion(
        f"{name}-secret-version",
        secret_id=secret.id,
        secret_string=pulumi.Output.all(**secrets_dict).apply(
            lambda values: json.dumps({k: v for k, v in zip(secrets_dict.keys(), values)})
        ),
    )
    
    return {
        "key": key,
        "secret": secret,
        "secret_version": secret_version,
    }

def create_ssm_secrets(name, secrets_dict):
    # Create parameters in SSM Parameter Store (Standard tier is free)
    parameters = {}
    
    for key, value in secrets_dict.items():
        parameter = aws.ssm.Parameter(
            f"{name}-{key}",
            name=f"/chatbot/{name}/{key}",
            type="SecureString",  # This uses the default AWS managed key (no extra charge)
            value=value,
        )
        parameters[key] = parameter
    
    return parameters