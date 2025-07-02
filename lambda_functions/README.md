## How it works?

**Lambda functions are called AUTOMATICALLY** by the AWS services - you don't need to write code to call them!

### 1. **You Configure the Trigger** (One-time setup)

You tell AWS: "When X happens, run my Lambda function"

Examples:

* "When a file is uploaded to S3 bucket → run my function"
* "When someone hits my API endpoint → run my function"
* "Every day at 9 AM → run my function"

### 2. **AWS Handles Everything Automatically**

* AWS monitors for the event
* When event occurs → AWS automatically invokes your Lambda
* Your function runs
* AWS manages scaling, servers, etc.

### 3. Exception: Manual Testing

The **only time you manually call** Lambda is:

* Testing in AWS Console (what you did)
* Calling from your own applications using AWS SDK
* One Lambda calling another Lambda

### 4. Real Examples

**S3 Trigger Setup:**

1. Go to S3 bucket → Properties → Event Notifications
2. Add notification: "Object created" → Target: Your Lambda function
3. **Done!** Now every file upload automatically triggers your Lambda

**API Gateway Setup:**

1. Create API Gateway → Create resource/method
2. Set integration target to your Lambda function
3. **Done!** Now HTTP requests automatically trigger your Lambda

**CloudWatch Schedule:**

1. Create EventBridge rule with schedule expression
2. Set target to your Lambda function
3. **Done!** Now runs automatically on schedule

### 5. What is an Event?

An **event** is the data that triggers your Lambda function and gets passed to it as input. Think of it as the "message" or "request" your function receives.

The `event` parameter is a Python dictionary (JSON object) that contains:

* Data sent to your function
* Information about what triggered the function
* Any parameters or payload

### 6. Real-World Event Sources

Here are the main **sources of events** that can trigger AWS Lambda functions:

### API & Web Services

* **API Gateway** - HTTP requests (REST APIs, WebSocket APIs)
* **Application Load Balancer (ALB)** - HTTP requests through load balancer
* **Lambda Function URLs** - Direct HTTPS endpoints for Lambda

### Storage Services

* **S3** - File uploads, deletions, modifications
* **DynamoDB** - Database changes (inserts, updates, deletes)
* **EFS** - File system changes

### Messaging & Queues

* **SQS** - Messages from queues
* **SNS** - Notifications and pub/sub messages
* **EventBridge** - Custom events and AWS service events
* **Kinesis** - Real-time data streams
* **MSK/Kafka** - Streaming data from Kafka

### Scheduling & Automation

* **CloudWatch Events/EventBridge** - Scheduled triggers (cron jobs)
* **CloudWatch Alarms** - Metric-based triggers
* **AWS Config** - Configuration changes

### User & Authentication

* **Cognito** - User pool triggers (sign-up, sign-in, password reset)
* **Lex** - Chatbot interactions
* **Alexa Skills Kit** - Voice commands

### Infrastructure & Monitoring

* **CloudTrail** - API call logging
* **CloudFormation** - Stack events
* **CodeCommit** - Git repository changes
* **CodePipeline** - CI/CD pipeline events

### IoT & Edge

* **IoT Core** - Device messages
* **IoT Events** - IoT rule engine triggers

### Direct Invocation

* **Manual/Console Testing** - What you did in the console
* **AWS SDK/CLI** - Programmatic calls
* **Other Lambda Functions** - Function-to-function calls

In production, events come from AWS services:

**API Gateway** (web request):

```
{
  "httpMethod": "POST",
  "path": "/users",
  "body": "{\"username\": \"john\"}",
  "headers": {"Content-Type": "application/json"}
}
```

**S3** (file uploaded)

```
{
  "Records": [{
    "s3": {
      "bucket": {"name": "my-bucket"},
      "object": {"key": "photo.jpg"}
    }
  }]
}
```

**CloudWatch** (scheduled trigger):

```
{
  "source": "aws.events",
  "time": "2025-06-12T10:00:00Z"
}
```

**SQS**

{
  "Records": [{
    "body": "Hello from SQS!",
    "messageId": "12345"
  }]
}

## Common Issues with Lambda Function

## **1. Lambda Function Hanging**

The "Loading..." message that keeps running indicates your Lambda function is **hanging** - it's not timing out, not erroring, just stuck somewhere. This is usually caused by a few specific issues.

### Step 1: Check Your Lambda Timeout Setting

1. **Go to your Lambda function in AWS Console**
2. **Configuration tab → General configuration**
3. **Check the Timeout setting**
   * If it's set to 30 seconds or more, that's why it's not timing out
   * **Temporarily set it to 10 seconds** for debugging

### Step 2: Check Your VPC Configuration

**This is the most likely culprit!**

1. **Go to Configuration tab → VPC**
2. **If you see VPC/Subnet/Security Group configured** , this might be the problem
3. **Temporarily remove VPC configuration:**
   * Click "Edit"
   * Select "No VPC"
   * Save
4. The issue is your VPC networking. You need to either:

* **Option A:** Keep Lambda outside VPC (simpler for now)
* **Option B:** Fix VPC networking (add NAT Gateway, fix security groups)

**Why this matters:** If your Lambda is in a VPC but can't reach the internet (no NAT Gateway or wrong route tables), it will hang when trying to call AWS services like Comprehend.

### Sep 3. Check CloudWatch Logs Manually

Sometimes the Console test interface has issues. Check logs directly:

1. **Go to CloudWatch in AWS Console**
2. **Log groups → Find `/aws/lambda/message-processor-lambda`**
3. **Click on the most recent log stream**
4. **Look for any log entries**

If you see  **no log entries at all** , the function isn't even starting, which suggests a deployment issue.


## Professional Way to Setup a Lambda Function Using Docker

Note that we are going to build an image compatible with amzon linux. **Docker image for Lambda** : Should be `amd64` (x86_64) or `arm64` (if using ARM Lambda)

**Step 1: Verify Docker Platform Support**

```
# Check if Docker supports platform builds
docker buildx version

# Ensure buildx is available and create builder
docker buildx create --name lambda-builder --use 2>/dev/null || docker buildx use lambda-builder
```

**Step 2: Clean and Rebuild with Explicit Platform**

```
# Navigate to your project
cd lambda_function_docker

# Remove the existing image
docker rmi lambda-psycopg2-test 2>/dev/null || true

# Build with explicit platform using buildx
docker buildx build --platform linux/amd64 -t lambda-psycopg2-test . --load

# Verify the architecture
docker inspect lambda-psycopg2-test --format='{{.Architecture}}'
# Should output: amd64

# Test the container locally first
docker run --platform linux/amd64 -p 9000:8080 lambda-psycopg2-test &

# Wait a few seconds for container to start
sleep 5

# Test the function
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"test": "local test"}'

# Stop the local container
docker stop $(docker ps -q --filter ancestor=lambda-psycopg2-test)
```


```
`${LAMBDA_TASK_ROOT}` is an **environment variable** that AWS Lambda provides in its base container images. It points to the directory where your Lambda function code should be placed. Default value is 

`LAMBDA_TASK_ROOT=/var/task`

If you want to see what `${LAMBDA_TASK_ROOT}` actually is:

# Run container interactively
docker run -it --entrypoint /bin/bash lambda-psycopg2-test

# Inside container, check the value
echo $LAMBDA_TASK_ROOT
# Output: /var/task

# See what's in that directory
ls -la $LAMBDA_TASK_ROOT
# Should show: lambda_function.py, requirements.txt, and installed packages
```


**Step 2 (alternative): Clean and Rebuild with Explicit Platform Using Docker Compose**

```
mkdir lambda_function_docker_compose
cd lambda_function_docker_compose

## Create directory structure
mkdir -p src
touch docker-compose.yml
touch src/lambda_function.py
touch src/requirements.txt
touch Dockerfile
touch .env

# Get your AWS Account ID
export ACTUAL_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

## Update the .env file
sed -i.bak "s/123456789012/${ACTUAL_ACCOUNT_ID}/g" .env

echo "Updated .env file:"
cat .env

## see Dockefile and docker-compose.yml

## Build the image
# Make sure you're using buildx for multi-platform builds
docker buildx create --use --name mybuilder 2>/dev/null || docker buildx use mybuilder

# Load environment variables
source .env

# Build the Lambda container image with explicit platform
DOCKER_BUILDKIT=1 docker compose --profile build build --no-cache

# Verify the image was created with correct architecture
docker inspect ${IMAGE_NAME}:latest --format='{{.Architecture}}'
# Should output: amd64

# Alternative verification
docker inspect ${IMAGE_NAME}:latest --format='{{.Os}}/{{.Architecture}}'
# Should output: linux/amd64

echo "Build completed! Image details:"
docker images | grep ${IMAGE_NAME}
```


**Verify Build Success (3 ways)**

```
# Test by overriding the entrypoint. If you are tesing on mac, deocker compose up does not work. It's due to setting lambda_function.lambda_handler as entrypoint 
docker run --platform linux/amd64 --rm --entrypoint python ${IMAGE_NAME}:latest -c "
import psycopg2
import boto3
print(f'✅ psycopg2 version: {psycopg2.__version__}')
print(f'✅ boto3 available: {bool(boto3)}')
print('✅ All packages imported successfully!')
"

# Get an interactive shell in the container
docker run --platform linux/amd64 --rm -it --entrypoint /bin/bash ${IMAGE_NAME}:latest

# Inside the container, run:
python -c "
import psycopg2
import boto3
print(f'✅ psycopg2 version: {psycopg2.__version__}')
print(f'✅ boto3 available: {bool(boto3)}')
print('✅ All packages imported successfully!')
"

# Exit the container
exit


# Run the container as intended (Lambda runtime)
docker run --platform linux/amd64 -d -p 9000:8080 --name lambda-test ${IMAGE_NAME}:latest

# Wait for it to start
sleep 3

# Test with a Lambda event
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -H "Content-Type: application/json" \
  -d '{
    "test": "verification",
    "action": "check_imports"
  }'

# Clean up
docker stop lambda-test
docker rm lambda-test


# Check what's inside the container
docker run --platform linux/amd64 --rm --entrypoint ls ${IMAGE_NAME}:latest -la

# Check Python packages
docker run --platform linux/amd64 --rm --entrypoint pip ${IMAGE_NAME}:latest list | grep -E "(psycopg2|boto3)"
```


**Step 3: Complete Guide with AWS CLI Lambda Function Creation**

**Set Up Environment Variables**

```
# Set your AWS details (replace with your actual values)
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=eu-west-2  # Change to your preferred region
export REPO_NAME=lambda-psycopg2
export FUNCTION_NAME=psycopg2-container-function
export ROLE_NAME=lambda-psycopg2-role

echo "Account ID: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo "Repository: $REPO_NAME"
```

**Create ECR Repository (if not exists)**

```
# Create ECR repository
aws ecr create-repository \
    --repository-name ${REPO_NAME} \
    --region ${AWS_REGION} \
    --image-scanning-configuration scanOnPush=true \
    || echo "Repository might already exist"

# Get the repository URI
export REPO_URI=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}
echo "Repository URI: $REPO_URI"
```

**Login to ECR and Push Image**

```
# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${REPO_URI}

# Tag the image for ECR
docker tag lambda-psycopg2-test:latest ${REPO_URI}:latest

# Push to ECR
docker push ${REPO_URI}:latest

# Verify the push
aws ecr describe-images --repository-name ${REPO_NAME} --region ${AWS_REGION}
```

**Create IAM Role for Lambda Function**

```
# Create trust policy for Lambda
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create the IAM role
aws iam create-role \
    --role-name ${ROLE_NAME} \
    --assume-role-policy-document file://trust-policy.json \
    || echo "Role might already exist"

# Attach basic execution policy
aws iam attach-role-policy \
    --role-name ${ROLE_NAME} \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Get the role ARN
export ROLE_ARN=$(aws iam get-role --role-name ${ROLE_NAME} --query 'Role.Arn' --output text)
echo "Role ARN: $ROLE_ARN"

# Wait for role to be ready
sleep 10
```


**Create Lambda Function Using AWS CLI**

```
# Create the Lambda function from container image
aws lambda create-function \
    --function-name ${FUNCTION_NAME} \
    --package-type Image \
    --code ImageUri=${REPO_URI}:latest \
    --role ${ROLE_ARN} \
    --timeout 30 \
    --memory-size 512 \
    --region ${AWS_REGION} \
    --architecture x86_64

# Wait for function to be ready
echo "Waiting for function to be active..."
aws lambda wait function-active --function-name ${FUNCTION_NAME} --region ${AWS_REGION}

echo "Function created successfully!"
```

**Test the Lambda Function**

```
# Test with a simple payload
echo '{"test": "CLI test", "name": "AWS CLI User"}' > test-payload.json

# Invoke the function
aws lambda invoke \
    --function-name ${FUNCTION_NAME} \
    --cli-binary-format raw-in-base64-out \
    --payload file://test-payload.json \
    --region ${AWS_REGION} \
    response.json

# Check the response
echo "Response:"
cat response.json | jq '.'

aws lambda invoke \
    --function-name ${FUNCTION_NAME} \
    --payload file://test-empty.json \
    --region ${AWS_REGION} \
    response.json

aws lambda invoke \
    --function-name ${FUNCTION_NAME} \
    --cli-binary-format raw-in-base64-out \
    --payload file://test-db.json \
    --region ${AWS_REGION} \
    response-db.json
echo "Database test response:"
cat response-db.json | jq '.'

# Verify Function Configuration
# Get function configuration
aws lambda get-function-configuration \
    --function-name ${FUNCTION_NAME} \
    --region ${AWS_REGION}
     --query '{State:State,LastUpdateStatus:LastUpdateStatus,StateReason:StateReason}'

# Check if function is in Active state
FUNCTION_STATE=$(aws lambda get-function-configuration \
    --function-name ${FUNCTION_NAME} \
    --region ${AWS_REGION} \
    --query 'State' \
    --output text)

echo "Function state: $FUNCTION_STATE"

if [ "$FUNCTION_STATE" = "Active" ]; then
    echo "Function is active, proceeding with test..."
else
    echo "Function is not active yet. Current state: $FUNCTION_STATE"
    echo "Waiting for function to become active..."
    aws lambda wait function-active --function-name ${FUNCTION_NAME} --region ${AWS_REGION}
fi


# Get function details
aws lambda get-function \
    --function-name ${FUNCTION_NAME} \
    --region ${AWS_REGION} \
    --query 'Configuration.{Name:FunctionName,Runtime:Runtime,Handler:Handler,Timeout:Timeout,Memory:MemorySize,Architecture:Architectures[0]}'
```


**Test Lambda Function with Log Handling**

```
# Test with a simple payload
echo '{"test": "CLI test", "name": "AWS CLI User"}' > test-payload.json

# Invoke the function
aws lambda invoke \
    --function-name ${FUNCTION_NAME} \
    --payload file://test-payload.json \
    --region ${AWS_REGION} \
    response.json

# Check the response
echo "Response:"
cat response.json | jq '.'

# Wait a moment for logs to be available
echo "Waiting for logs to be available..."
sleep 10

# Check if log group exists, if not wait longer
LOG_GROUP="/aws/lambda/${FUNCTION_NAME}"
echo "Checking for log group: $LOG_GROUP"

# Wait for log group to be created
aws logs describe-log-groups \
    --log-group-name-prefix "$LOG_GROUP" \
    --region ${AWS_REGION} \
    --query 'logGroups[0].logGroupName' \
    --output text > /dev/null || {
    echo "Log group not found yet, waiting..."
    sleep 15
}

# Get the most recent log stream
LOG_STREAM=$(aws logs describe-log-streams \
    --log-group-name "$LOG_GROUP" \
    --order-by LastEventTime \
    --descending \
    --max-items 1 \
    --region ${AWS_REGION} \
    --query 'logStreams[0].logStreamName' \
    --output text 2>/dev/null)

if [ "$LOG_STREAM" != "None" ] && [ -n "$LOG_STREAM" ]; then
    echo -e "\nRecent logs from stream: $LOG_STREAM"
    aws logs get-log-events \
        --log-group-name "$LOG_GROUP" \
        --log-stream-name "$LOG_STREAM" \
        --region ${AWS_REGION} \
        --query 'events[*].message' \
        --output text
else
    echo "No log streams found yet. Let's invoke the function again and check..."
  
    # Invoke again to ensure logs are created
    aws lambda invoke \
        --function-name ${FUNCTION_NAME} \
        --payload file://test-payload.json \
        --region ${AWS_REGION} \
        response2.json
  
    echo "Second invocation response:"
    cat response2.json | jq '.'
  
    # Wait and try logs again
    sleep 10
  
    LOG_STREAM=$(aws logs describe-log-streams \
        --log-group-name "$LOG_GROUP" \
        --order-by LastEventTime \
        --descending \
        --max-items 1 \
        --region ${AWS_REGION} \
        --query 'logStreams[0].logStreamName' \
        --output text 2>/dev/null)
  
    if [ "$LOG_STREAM" != "None" ] && [ -n "$LOG_STREAM" ]; then
        echo -e "\nLogs after second invocation:"
        aws logs get-log-events \
            --log-group-name "$LOG_GROUP" \
            --log-stream-name "$LOG_STREAM" \
            --region ${AWS_REGION} \
            --query 'events[*].message' \
            --output text
    else
        echo "Still no logs available. Function might have an issue."
        echo "Let's check the function's last error:"
        aws lambda get-function \
            --function-name ${FUNCTION_NAME} \
            --region ${AWS_REGION} \
            --query 'Configuration.LastUpdateStatus'
    fi
fi
```
