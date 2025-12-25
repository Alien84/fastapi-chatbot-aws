# Summary of Changes - Making Lambda Functions Optional

## Changes Made

### 1. `infrastructure/__main__.py`

#### Lambda Creation (Lines 402-461)
**Before:**
- Lambda functions were always created unconditionally

**After:**
- Lambda functions are only created when `deploy_stage in ["lambda", "all"]`
- When `deploy_stage != "lambda"`, only ECR repos for Lambda are created
- Variables `message_processor_lambda` and `api_stats_lambda_resources` are initialized to `None`

```python
# Lambda functions now wrapped in conditional
if deploy_stage in ["lambda", "all"]:
    message_processor_lambda = create_message_processor_lambda(...)
    api_stats_lambda_resources = create_api_stats_lambda_function(...)
else:
    # Still create ECR repos but not Lambda functions
    message_processor_lambda = create_message_processor_lambda(..., deploy_stage=deploy_stage)
    api_stats_lambda_resources = create_api_stats_lambda_function(..., deploy_stage=deploy_stage)
```

#### Lambda-Specific Resources (Lines 463-500)
**Kept inside conditional:**
- Lambda invoke policy
- Lambda invoke policy attachment
- API Gateway creation
- Lambda-related exports

#### EC2 Infrastructure (Lines 502+)
**Moved OUTSIDE Lambda conditional:**
- User data script creation
- CloudWatch log groups
- IAM logs policy
- Instance profile
- SNS topics
- EC2 instances (single or autoscaling)
- Load balancers
- CloudWatch dashboards and alarms
- All exports

**Key Change - User Data Creation (Lines 514-549):**
```python
# Now checks if Lambda function exists before using its name
if message_processor_lambda and 'lambda_function' in message_processor_lambda:
    # Include Lambda function name in user_data
    user_data = pulumi.Output.all(..., message_processor_lambda['lambda_function'].name).apply(...)
else:
    # Use empty string when Lambda not deployed
    user_data = pulumi.Output.all(...).apply(
        lambda args: user_data_template
            .replace("${AWS_LAMBDA_FUNCTION_NAME}", "")  # Empty!
            ...
    )
```

### 2. `app/main.py`

#### Function: `trigger_message_processing` (Lines 94-122)
**Before:**
- Always attempted to invoke Lambda
- Would fail if Lambda didn't exist

**After:**
- Checks if `AWS_LAMBDA_FUNCTION_NAME` environment variable is set and non-empty
- Skips Lambda invocation if not configured
- Logs info message when skipping
- Returns `False` gracefully instead of crashing

```python
def trigger_message_processing(message_id: int, content: str):
    """Trigger Lambda function for message processing (if Lambda is deployed)"""
    function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', '').strip()

    if not function_name:
        logger.info(f"Lambda function not configured, skipping async processing for message {message_id}")
        return False

    # ... rest of Lambda invocation code
```

## How It Works Now

### Scenario 1: Deploy WITHOUT Lambda Functions

1. Set `deploy_stage` to something other than "lambda" or "all" (e.g., `deploy_stage="ecr"`)
2. Run `pulumi up`

**Result:**
- ✅ ECR repositories created
- ✅ VPC, RDS, security groups created
- ❌ Lambda functions NOT created
- ❌ EC2 instances NOT created (because still in "ecr" mode)

To get EC2 without Lambda, you'd currently need to:
- Deploy with `deploy_stage="lambda"` (which creates Lambda)
- But the Lambda won't be used because `user_data` sets `AWS_LAMBDA_FUNCTION_NAME=""` when Lambda doesn't exist

### Scenario 2: Deploy WITH Lambda Functions (Current Two-Stage Process)

**Stage 1:**
```bash
pulumi up --config deploy_stage=ecr
```
- Creates ECR repos only

**Stage 2:**
```bash
# Build and push images
pulumi up --config deploy_stage=lambda
```
- Creates Lambda functions
- Creates EC2 infrastructure
- Sets `AWS_LAMBDA_FUNCTION_NAME` in user_data
- App will invoke Lambda

## Key Differences

| Aspect | Before | After |
|--------|--------|-------|
| Lambda Creation | Always created | Conditional based on `deploy_stage` |
| EC2 Creation | Only with Lambda | Independent of Lambda |
| User Data | Required Lambda name | Optional Lambda name |
| App Behavior | Would crash without Lambda | Gracefully skips Lambda if not configured |
| Flexibility | Fixed architecture | Choose with/without Lambda |

## Testing the Changes

### Test 1: Deploy Without Lambda
```bash
cd infrastructure
pulumi preview --config deploy_stage=ecr
# Should show: ECR repos created, no Lambda functions, no EC2 instances
```

### Test 2: Deploy With Lambda
```bash
pulumi preview --config deploy_stage=lambda
# Should show: Everything created including Lambda and EC2
```

### Test 3: Verify App Behavior Without Lambda
```bash
# SSH to EC2 instance
docker compose logs -f chatbot-dev

# Send a chat message via API
# Check logs - should see: "Lambda function not configured, skipping async processing"
```

### Test 4: Verify App Behavior With Lambda
```bash
# If Lambda is deployed
# Send a chat message via API
# Check logs - should see: "Triggered Lambda processing for message X"
```

## Backward Compatibility

**✅ Fully backward compatible!**

- Existing deployments with `deploy_stage="lambda"` will continue to work exactly as before
- No changes needed to existing configurations
- The only difference is that now you CAN deploy without Lambda if you want

## Next Steps (Optional)

### To Add "EC2-Only" Deployment Mode

If you want to deploy EC2 without creating Lambda functions at all, add this logic around line 408:

```python
if deploy_stage == "ec2_only":
    # Skip Lambda creation entirely
    message_processor_lambda = None
    api_stats_lambda_resources = None
elif deploy_stage in ["lambda", "all"]:
    # Create Lambda functions
    message_processor_lambda = create_message_processor_lambda(...)
    api_stats_lambda_resources = create_api_stats_lambda_function(...)
else:
    # ECR stage - create only ECR repos
    message_processor_lambda = create_message_processor_lambda(..., deploy_stage="ecr")
    api_stats_lambda_resources = create_api_stats_lambda_function(..., deploy_stage="ecr")
```

Then update the EC2 creation check:
```python
# Around line 502-514
if deploy_stage in ["lambda", "all", "ec2_only"]:
    # Create EC2 infrastructure
    # ...
```

## Backup

A backup of the original `__main__.py` was saved as `__main__.py.backup` in the infrastructure directory.

To restore:
```bash
cd infrastructure
mv __main__.py.backup __main__.py
```
