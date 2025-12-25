# Deployment Modes

This infrastructure now supports flexible deployment with or without Lambda functions.

## Changes Made

### 1. Infrastructure Changes (`infrastructure/__main__.py`)

- **Lambda functions are now optional**: Lambda resources are only created when `deploy_stage` includes "lambda"
- **EC2 infrastructure is always created**: EC2 instances, load balancers, CloudWatch resources, etc., are created regardless of Lambda deployment
- **Conditional user_data**: The user_data script adapts based on whether Lambda functions are deployed

### 2. Application Changes (`app/main.py`)

- **Optional Lambda invocation**: The app checks if `AWS_LAMBDA_FUNCTION_NAME` is set before attempting to invoke Lambda
- **Graceful degradation**: If Lambda is not configured, the app logs a message and continues without async processing

## Deployment Stages

### Stage 1: ECR Only (`deploy_stage="ecr"`)
Creates only ECR repositories for both the app and Lambda functions:
- ✅ App ECR repository
- ✅ Lambda ECR repositories
- ✅ VPC, subnets, security groups
- ✅ RDS database
- ✅ SSM parameters
- ✅ IAM roles (basic)
- ❌ **NO Lambda functions**
- ❌ **NO EC2 instances**

### Stage 2: Without Lambda (`deploy_stage="ec2"` or similar - requires code addition)
Creates EC2 infrastructure without Lambda:
- ✅ All ECR repositories
- ✅ VPC, subnets, security groups
- ✅ RDS database
- ✅ SSM parameters
- ✅ **EC2 instances or Auto Scaling Group**
- ✅ **Load Balancer (if autoscaling)**
- ✅ **CloudWatch dashboards and alarms**
- ✅ **SNS topics**
- ❌ **NO Lambda functions**
- ❌ **NO Lambda invoke policy**
- ❌ **NO API Gateway**

**Note**: Currently, to skip Lambda entirely, you would deploy with `deploy_stage="ecr"` first (which creates ECR repos), then manually change to `deploy_stage="lambda"` but this still creates Lambda. To truly skip Lambda, you'll need to add a new stage like "ec2_only".

### Stage 3: With Lambda (`deploy_stage="lambda"` or `"all"`)
Creates everything including Lambda:
- ✅ All ECR repositories
- ✅ VPC, subnets, security groups
- ✅ RDS database
- ✅ SSM parameters
- ✅ **Lambda functions**
- ✅ **Lambda invoke policy**
- ✅ **API Gateway**
- ✅ **EC2 instances or Auto Scaling Group**
- ✅ **Load Balancer (if autoscaling)**
- ✅ **CloudWatch dashboards and alarms**
- ✅ **SNS topics**

## Usage Examples

### Deploy EC2 Application Without Lambda

Currently, the infrastructure code always creates EC2 resources when `deploy_stage="lambda"`. To run **without** Lambda functions, you would need to:

**Option 1: Use the existing two-stage process but skip Lambda invocations**
```bash
# Stage 1: Create ECR repos
pulumi up --config deploy_stage=ecr

# Build and push app Docker image
# (Skip Lambda image building)

# Stage 2: Create EC2 (Lambda functions will still be created, but app won't use them)
pulumi up --config deploy_stage=lambda
```

The app will work fine because it checks if `AWS_LAMBDA_FUNCTION_NAME` is empty before invoking Lambda.

**Option 2: Add a new deployment stage (requires minor code change)**

Add this to the beginning of the Lambda creation block in `__main__.py`:

```python
# Around line 408
if deploy_stage in ["lambda", "all"]:
    message_processor_lambda = create_message_processor_lambda(...)
    api_stats_lambda_resources = create_api_stats_lambda_function(...)
elif deploy_stage == "ec2_only":
    # Don't create Lambda functions at all
    message_processor_lambda = None
    api_stats_lambda_resources = None
else:
    # ECR stage - create ECR repos for Lambda
    message_processor_lambda = create_message_processor_lambda(..., deploy_stage="ecr")
    api_stats_lambda_resources = create_api_stats_lambda_function(..., deploy_stage="ecr")
```

Then deploy:
```bash
pulumi up --config deploy_stage=ec2_only
```

### Deploy EC2 Application With Lambda (Full Deployment)

```bash
# Stage 1: Create ECR repos only
pulumi up --config deploy_stage=ecr

# Stage 2: Build and push Docker images
# Build app image
docker build -t chatbot-app:latest app/
aws ecr get-login-password --region eu-west-2 | docker login --username AWS --password-stdin <ecr-url>
docker tag chatbot-app:latest <ecr-url>:latest
docker push <ecr-url>:latest

# Build Lambda images
cd lambda_functions/message_processor
docker build -t message-processor:latest .
docker tag message-processor:latest <lambda-ecr-url>:latest
docker push <lambda-ecr-url>:latest

# Stage 3: Create everything including Lambda
cd ../../infrastructure
pulumi up --config deploy_stage=lambda
```

## How Application Behaves

### With Lambda (`AWS_LAMBDA_FUNCTION_NAME` is set)
1. User sends chat message
2. Message is saved to database
3. **Lambda function is invoked asynchronously** for processing (e.g., sentiment analysis)
4. Response returns immediately
5. Lambda processes message in background and updates database

### Without Lambda (`AWS_LAMBDA_FUNCTION_NAME` is empty or not set)
1. User sends chat message
2. Message is saved to database
3. **Lambda invocation is skipped** (logged as info message)
4. Response returns immediately
5. No background processing occurs

## Benefits of This Approach

1. **Cost Savings**: Deploy without Lambda for development/testing to save on Lambda costs
2. **Simplified Testing**: Test the core FastAPI application without Lambda complexity
3. **Gradual Rollout**: Deploy app first, add Lambda later
4. **Flexibility**: Choose the right architecture for each environment (dev, staging, prod)

## Migration Path

### From No Lambda to With Lambda
```bash
# If currently running without Lambda
pulumi up --config deploy_stage=lambda

# The infrastructure will add Lambda functions
# App will automatically start using them (checks AWS_LAMBDA_FUNCTION_NAME)
```

### From With Lambda to No Lambda
```bash
# To remove Lambda functions, you would need to:
# 1. Update code to add "ec2_only" stage
# 2. Run: pulumi up --config deploy_stage=ec2_only

# Or manually delete Lambda resources:
pulumi state delete <lambda-resource-name>
```

## Environment Variables

The application checks these environment variables:

- `AWS_LAMBDA_FUNCTION_NAME`: If empty or not set, Lambda invocation is skipped
- `DB_SSM_PREFIX`: Path to database credentials in SSM Parameter Store
- `AWS_REGION`: AWS region for services

## Validation

After deployment, check if Lambda is configured:

```bash
# SSH into EC2 instance
ssh -i chatbot-dev-keypair.pem ec2-user@<instance-ip>

# Check environment variables
docker compose -f /opt/chatbot-dev/docker-compose.yml exec chatbot-dev env | grep LAMBDA

# If output is empty or AWS_LAMBDA_FUNCTION_NAME=, Lambda is not configured
# If output shows AWS_LAMBDA_FUNCTION_NAME=message-processor-lambda, Lambda is configured
```

## Troubleshooting

### Issue: EC2 instances not created with deploy_stage=ecr

**Solution**: This is expected behavior. With `deploy_stage=ecr`, only ECR repositories are created. Change to `deploy_stage=lambda` to create EC2 instances.

### Issue: Application tries to invoke Lambda but fails

**Check**:
1. Is `AWS_LAMBDA_FUNCTION_NAME` set in the container?
2. Does the EC2 IAM role have Lambda invoke permissions?
3. Was Lambda actually deployed?

### Issue: Want to skip Lambda entirely

**Solution**:
1. Deploy with `deploy_stage=lambda` (Lambda will be created)
2. In `user_data.sh` or docker-compose.yml, set `AWS_LAMBDA_FUNCTION_NAME=""` (empty)
3. App will skip Lambda invocation

Or add the "ec2_only" deployment stage as described above.
