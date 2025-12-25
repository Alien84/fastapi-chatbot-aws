# fastapi-chatbot-aws

FastAPI chatbot application deployed on AWS using Pulumi and GitHub Actions CI/CD

**Create the Directory Structure**

```
# Create the main application directory
mkdir -p app/{api,core,models,services}

# Create infrastructure directory for Pulumi code
mkdir -p infrastructure

# Create scripts directory for utility scripts
mkdir -p scripts

# Create comprehensive test directory structure
mkdir -p tests/{api,infrastructure,integration,unit}

# Create GitHub Actions workflow directory
mkdir -p .github/workflows

# Create documentation directory
mkdir -p docs

# Create configuration directory
mkdir -p config
```

**`app/` - Application Code Directory**

```
app/
├── __init__.py              # Makes app a Python package
├── main.py                  # FastAPI application entry point
├── api/                     # API route handlers
│   ├── __init__.py
│   ├── deps.py              # Dependencies (database sessions, etc.)
│   ├── endpoints/           # API endpoint modules
│   │   ├── __init__.py
│   │   ├── chat.py          # Chat-related endpoints
│   │   ├── health.py        # Health check endpoints
│   │   └── history.py       # Chat history endpoints
│   └── api.py               # Main API router
├── core/                    # Core application logic
│   ├── __init__.py
│   ├── config.py            # Application configuration
│   ├── security.py          # Authentication/authorization
│   └── database.py          # Database connection setup
├── models/                  # Data models
│   ├── __init__.py
│   ├── chat.py              # Chat-related Pydantic models
│   └── database.py          # SQLAlchemy database models
└── services/                # Business logic services
    ├── __init__.py
    ├── chat_service.py      # Chat processing logic
    └── database_service.py  # Database operations
```

```
#!/bin/bash

# Create the complete directory structure
mkdir -p app/{api/endpoints,core,models,services}
mkdir -p infrastructure/{modules,config}
mkdir -p scripts
mkdir -p tests/{api,infrastructure,integration,unit}
mkdir -p .github/workflows
mkdir -p docs
mkdir -p config

# Create __init__.py files for Python packages
find app tests infrastructure -type d -exec touch {}/__init__.py \;

# Create placeholder files
touch app/main.py
touch app/core/{config.py,database.py,security.py}
touch app/api/{deps.py,api.py}
touch app/api/endpoints/{chat.py,health.py,history.py}
touch app/models/{chat.py,database.py}
touch app/services/{chat_service.py,database_service.py}

touch infrastructure/__main__.py
touch infrastructure/modules/{vpc.py,ec2.py,rds.py,secrets.py,monitoring.py}

touch scripts/{user_data.sh,deploy.sh,setup_db.py,health_check.py}

touch tests/conftest.py
touch tests/api/{test_chat.py,test_health.py,test_history.py}
touch tests/infrastructure/{test_vpc.py,test_ec2.py,test_rds.py}
touch tests/integration/{test_database.py,test_full_flow.py}
touch tests/unit/{test_models.py,test_services.py}

touch .github/workflows/{ci.yml,cd.yml,security.yml,cleanup.yml}

touch docs/{deployment.md,api.md,architecture.md,troubleshooting.md}

touch config/{dev.env,staging.env,prod.env,logging.yaml}

# Create essential root files
touch requirements.txt requirements-dev.txt .env.example

echo "Repository structure created successfully!"
echo "Don't forget to:"
echo "1. Add content to the created files"
echo "2. Initialize git and make your first commit"
echo "3. Set up your virtual environment"
echo "4. Install dependencies"
```

**`tests/` - Test Code**

```
tests/
├── __init__.py
├── conftest.py              # Pytest configuration and fixtures
├── api/                     # API endpoint tests
│   ├── __init__.py
│   ├── test_chat.py         # Chat endpoint tests
│   ├── test_health.py       # Health endpoint tests
│   └── test_history.py      # History endpoint tests
├── infrastructure/          # Infrastructure tests
│   ├── __init__.py
│   ├── test_vpc.py          # VPC configuration tests
│   ├── test_ec2.py          # EC2 configuration tests
│   └── test_rds.py          # RDS configuration tests
├── integration/             # Integration tests
│   ├── __init__.py
│   ├── test_database.py     # Database integration tests
│   └── test_full_flow.py    # End-to-end tests
└── unit/                    # Unit tests
    ├── __init__.py
    ├── test_models.py       # Model tests
    └── test_services.py     # Service layer tests
```

### 2. Setting Up AWS Authentication for GitHub Actions

Navigate to `.github/workflows/.` Each of these `.yaml` files defines a workflow — they are your CI/CD pipelines.

```
.github/
└── workflows/
    ├── ci.yaml
    ├── cd.yaml
    └── deploy-prod.yaml
```

`ci.yaml` focuses on  **code validation** : linting, testing, building. CI usually runs on every push or PR.

```
on:
  pull_request:
  push:
    branches: [main]

```

`cd.yaml` handles  **deployment** : pushing artifacts, deploying to AWS, etc. CD might only run on merges to `main`, tags, or manual dispatch.

   -- By setting tags, CD only runs when you push a release tag like `v1.0.1`.

```
on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

```

**2.1. Create an IAM User for GitHub Actions:** Using the AWS Management Console or AWS CLI:

```
### Create a deployment user with programmatic access
aws iam create-user --user-name github-actions-deployment

### Attach the necessary policies (use more restrictive policies in production)

# Approach 1: manual
aws iam attach-user-policy \
    --user-name github-actions-deployment \
    --policy-arn arn:aws:iam::aws:policy/PowerUserAccess

aws iam attach-user-policy \
    --user-name github-actions-deployment \
    --policy-arn arn:aws:iam::aws:policy/IAMFullAccess

# You may need to attach following policies, if you get any error.
aws iam attach-user-policy --user-name github-actions-deployment --policy-arn arn:aws:iam::aws:policy/AmazonEC2FullAccess
aws iam attach-user-policy --user-name github-actions-deployment --policy-arn arn:aws:iam::aws:policy/AmazonRDSFullAccess
aws iam attach-user-policy --user-name github-actions-deployment --policy-arn arn:aws:iam::aws:policy/AmazonVPCFullAccess
aws iam attach-user-policy --user-name github-actions-deployment --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite
aws iam attach-user-policy --user-name github-actions-deployment --policy-arn arn:aws:iam::aws:policy/IAMFullAccess
aws iam attach-user-policy --user-name github-actions-deployment --policy-arn arn:aws:iam::aws:policy/AmazonSSMFullAccess
aws iam attach-user-policy --user-name github-actions-deployment --policy-arn arn:aws:iam::aws:policy/AmazonSNSFullAccess


# Approach 2: manual
	-- Create a custom policy file github-actions-policy.json
	-- # If you already have the custom policy, update it
		aws iam create-policy-version \
    			--policy-arn arn:aws:iam::555576841436:policy/GitHubActionsDeploymentPolicy \
    			--policy-document file://policies/github-actions-policy.json \
    			--set-as-default
	-- # OR create a new one if you prefer
	-- aws iam create-policy --policy-name GitHubActionsDeploymentPolicy --policy-document file://policies/github-actions-policy.json
	-- detach the old policies
	-- Attach the new comprehensive policy
		aws iam attach-user-policy \
    			--user-name github-actions-deployment \
    			--policy-arn arn:aws:iam::555576841436:policy/GitHubActionsDeploymentPolicy
		Replace 555576841436 with your actual AWS account ID


### Create access keys
aws iam create-access-key --user-name github-actions-deployment
```

**Consider using IAM Roles instead of users (Most Secure)**

```
### Create a GitHub OIDC Identity Provider in AWS: This is the main AWS CLI command that sets up a new OIDC provider in AWS Identity and Access Management (IAM). It allows federated identities (like GitHub Actions) to access AWS resources securely via IAM roles.

aws iam create-open-id-connect-provider \
    --url https://token.actions.githubusercontent.com \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

### Create a role for GitHub Actions

-- Create github-actions-trust-policy.json

# Create a new role
aws iam create-role \
    --role-name GitHubActionsRole \
    --assume-role-policy-document file://policies/github-actions-trust-policy.json

# If the role exists, update the policy
-- # If you already have the custom policy, update it
		aws iam create-policy-version \
    			--policy-arn arn:aws:iam::555576841436:policy/GitHubActionsDeploymentPolicy \
    			--policy-document file://policies/github-actions-policy.json \
    			--set-as-default
-- # OR create a new one if you prefer
-- aws iam create-policy --policy-name GitHubActionsDeploymentPolicy --policy-document file://policies/github-actions-policy.json


# Attach the policy we created earlier
aws iam attach-role-policy \
    --role-name GitHubActionsRole \
    --policy-arn arn:aws:iam::555576841436:policy/GitHubActionsDeploymentPolicy

### Update your GitHub Actions workflow to use the role instead of access keys. Check changes in (CI/CD yaml files).




```

**2.2 Store AWS Credentials as GitHub Secrets:**
Go to your GitHub repository:

* Navigate to Settings > Secrets and variables > Actions
* Click "New repository secret"
* Add the following secrets:

  * `AWS_ACCESS_KEY_ID`: Your IAM user's access key ID
  * `AWS_SECRET_ACCESS_KEY`: Your IAM user's secret access key
  * `AWS_REGION`: Your preferred AWS region (e.g., `us-west-2`)
  * `PULUMI_ACCESS_TOKEN`: Your Pulumi access token (get this from Pulumi)

### **3. Setting Up Pulumi Configuration**

**3.1 Set Up Pulumi Cloud Backend:**
Create an account at [Pulumi](https://app.pulumi.com/) if you don't have one already. Initialize your Pulumi project with the Pulumi Cloud backend:

```
cd infrastructure
pulumi login
pulumi stack init dev
```

**3.2 Configure Pulumi Settings:** Create a `Pulumi.dev.yaml`

**3.3 Create a GitHub Action for CI:** Create `.github/workflows/ci.yml`

**3.4 Creating the Continuous Deployment Workflow:** Create `.github/workflows/cd.yml`

### 4. Implementing Multi-Environment Support

```
cd infrastructure
pulumi stack init dev
pulumi stack init staging
pulumi stack init prod
```

**Configure Pulumi Settings:** Create a `P, Pulumi.staging.yamlulumi.dev.yaml, Pulumi.prod.yaml`

Some docker concepts

### 5. Containerizing FastAPI Application

**Some Docker commands before going forward:**

```
# Stop and remove existing containers
docker compose down

# Optional: Remove volumes if you want a clean slate
docker compose down -v

# Optional: Clean up unused images
docker image prune -f
```

```
1. Dangling Images
These are:
Intermediate layers or leftover images
Have no name (tag), shown as <none> in docker images
Usually created when you build new images that replace old ones
Example:
$ docker images
REPOSITORY    TAG       IMAGE ID       CREATED        SIZE
<none>        <none>    a1b2c3d4e5f6    3 hours ago    300MB

To delete:
docker image prune -f

2. Unused Tagged Images
These are:
Have names (tags)
Are not currently used by any containers (not even stopped ones)

To delete:
docker image prune -a -f
```

```
# Remove the database volume (WARNING: This deletes all data), When: You modified database models and need to recreate the database
docker-compose down -v
```

```
# Start container
docker-compose up --build
```

```
# Remove the old app image to force rebuild
docker-compose build --no-cache app
```

```
# Force rebuild without cache
docker compose -f docker-compose.yml build --no-cache app
docker compose -f docker-compose.yml up -d --force-recreate app
```

**Best Practices for Development**

1. **Use Volume Mounts:** Your `docker-compose.yml` already has volume mounts, so small code changes don't require rebuilds
2. **Layer Caching:** Put less frequently changed commands (like `pip install`) earlier in your Dockerfile
3. **Development vs Production:** Keep separate Dockerfiles or use multi-stage builds if needed
4. **Environment Variables:** Use `.env` files for local development configuration

**Step 1:** Create Docker Configuration

    -- Create a Dockerfile

    -- Update your application requirements

    -- Create a Docker Compose file for local development

**Step 2:** Update Application Code for Container Environment

**Step 3:** Set Up Container Registry in infra.

    -- Create an ECR Repository

    -- Update IAM permissions for ECR access

**Step 4:** Update User Data for Docker Deployment

**Step 5:** Update GitHub Actions for Docker Build and Push

**For local development and testing the application code**

    -- Option 1. Create a docker container locally.

    Run ./scripts/dev_setup.sh

    -- Option 2. Using VS Code debug mode

The application will be available at [http://localhost:8000](http://localhost:8000).

**Rebuilding Containers for Local Development**

```
chmod +x scripts/dev_rebuild.sh
chmod +x scripts/dev_logs.sh
chmod +x scripts/dev_status.sh

# Quick restart for small code changes
./scripts/dev_rebuild.sh quick

# Normal rebuild for most changes
./scripts/dev_rebuild.sh

# Clean rebuild for dependency changes
./scripts/dev_rebuild.sh deps

# Complete reset when things get messy
./scripts/dev_rebuild.sh reset

# Check status
./scripts/dev_status.sh

# Watch logs
./scripts/dev_logs.sh

# Watch specific service logs
./scripts/dev_logs.sh db
```

**Use development tools `scripts/dev_tools.sh`**

```
# Format code
./scripts/dev_tools.sh format

# Run tests
./scripts/dev_tools.sh test

# Run all quality checks
./scripts/dev_tools.sh all
```

### 6. VS Code's debugging capabilities with Docker

1. Create `app/Dockerfile.dev`
2. Create `app/requirements-dev.txt`
3. Create `docker-compose.debug.yml`
4. Create `.vscode/launch.json`
5. Create `.vscode/tasks.json`
6. Create `scripts/debug_start.sh`
7. Create `scripts/debug_stop.sh`

**How to Use Debug Mode**

Method 1: Using Debug Scripts
 
1. Start debug environment: `./scripts/debug_start.sh`
2. Set breakpoints in your Python code in VS Code
3. Select "Debug FastAPI in Docker" and ply debugging method
4. Stop debug environment: `./scripts/debug_stop.sh`

Method 2: Using VS Code Tasks

1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type "Tasks: Run Task"
3. Select "docker-debug-start"
4. Attach debugger using the launch configuration
5. Stop debugging: Run the "docker-debug-stop" task

In both cases, m**ake a request** to `http://localhost:8000/` and test the `/chat` endpoint.

**If the debugger won't attach**

```
# Check container status
docker compose -f docker-compose.debug.yml ps
docker compose -f docker-compose.debug.yml logs app-debug

# Check if ports are in use
lsof -i :5678
lsof -i :8000

# If ports are in use, kill the processes or change ports in docker-compose.debug.yml
```


**If you change the code and need to rebuild the model:**

```
# Force rebuild without cache
docker compose -f docker-compose.debug.yml build --no-cache app-debug
docker compose -f docker-compose.debug.yml up -d --force-recreate app-debug
```

# Best practices for tesing (Tests)


* **Test Isolation** : Each test is independent and can run alone
* **Test Data Management** : Consistent test data across test suites
* **Resource Cleanup** : Proper cleanup of containers, files, and connections
* **Error Handling** : Comprehensive error scenario testing
* **Performance Benchmarks** : Defined performance expectations
* **Security Validation** : Multi-layered security testing
* **Real Environment Testing** : Tests that mirror production conditions
* **Comprehensive Coverage** : Testing all layers of the application stack

## **General Tests**

**Get all pulumi outputs**

`python tests/infrastructure`

**Test lambda function directly**

`python tests/lambda_functions/test_lambda_direct.py`

**Send a chat message via your API**

```
curl -X POST "http://your-load-balancer-url/chat" \
     -H "Content-Type: application/json" \
     -d '{"content": "I love this chatbot! It is amazing and helpful."}'

curl "http://your-load-balancer-url/message/1/sentiment"


```

**Check CloudWatch Logs**

`aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/message-processor"
aws logs describe-log-streams --log-group-name "/aws/lambda/message-processor-lambda"
aws logs get-log-events --log-group-name "/aws/lambda/message-processor-lambda" --log-stream-name "LATEST_STREAM_NAME"`

## 1. Lambda Function Tesing

#### -- Local Testing Approaches

**A. Unit Testing (Isolated Component Testing)** -- Test individual functions without AWS dependencies.

```
cd tests/unit
python -m pytest test_message_processor_unit.py -v
```

**B. Integration Testing with Local Database** -- Test with a real database but mock AWS services.

```
cd tests/unit
python -m pytest test_message_processor_integration.py -v
```

**C. Local Lambda Runtime Simulation** -- Test Lambda function with AWS Lambda Runtime Interface Emulator.

```
cd tests/unit
python -m pytest test_with_runtime_emulator.py -v
```


#### -- AWS Testing Approaches

**A. Direct Lambda Invocation Testing:** -- Test deployed Lambda function directly in AWS.

```
cd tests/lambda
python test_lambda_aws_direct.py
```

**B. End-to-End Testing Through FastAPI:** -- Test the complete workflow from API to Lambda.

```
cd tests/lambda
python test_e2e_workflow.py
```

**C. CloudWatch Monitoring and Alerting Tests:** -- Test Lambda function monitoring and alerting.

```
cd tests/lambda
python test_lambda_monitoring.py
```


#### -- Load Testing and Stress Testing

```
cd tests/lambda
python load_test_lambdag.py
```


## 2. Database Testing

**A. Database Schema and Migration Testing** --- Ensure database schema is correct and migrations work properly.

`tests/database/test_schema.py`

**B. Database Data Testing**

`tests/database/test_data_operations.py`


## 3. FastAPI Application Testing

**A. API Integration Testing**

`tests/api/test_api_integration.py`

**B. API Performance Testing**

`tests/api/test_api_performance.py`


## 4. Infrastructure Testing

**A. Pulumi Infrastructure Testing**

`tests/infrastructure/test_pulumi_stack.py`

**B. Docker Container Testing**

`tests/infrastructure/test_docker_containers.py`


## 5. End-to-End Workflow Testing

`tests/e2e/test_complete_workflow.py`

## 6. Security Testing

`tests/security/test_security.py`


## 7. Monitoring and Observability Testing

`tests/monitoring/test_observability.py`


## 8. Backup and Recovery Testing

`tests/backup/test_backup_recovery.py`


# Running All Tests

`tests/run_all_tests.py`

```
# Run specific test categories
python -m pytest tests/database/ -v           # Database tests only
python -m pytest tests/api/ -v               # API tests only
python -m pytest tests/lambda/ -v            # Lambda tests only
python -m pytest tests/security/ -v          # Security tests only
python -m pytest tests/e2e/ -v               # E2E tests only

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=html

# Run performance tests only
python -m pytest tests/ -k "performance" -v

# Run tests with specific markers
python -m pytest tests/ -m "slow" -v         # Only slow tests
python -m pytest tests/ -m "not slow" -v     # Skip slow tests

# Parallel test execution
python -m pytest tests/ -n auto              # Auto-detect CPU cores
```



### Continuous Integration Integration:

Add to your `.github/workflows/ci.yml`

```
- name: Run comprehensive test suite
  run: |
    # Install test dependencies
    pip install -r tests/requirements.txt
  
    # Run fast tests first
    python -m pytest tests/database tests/api tests/lambda -v
  
    # Run integration tests
    python -m pytest tests/infrastructure tests/security -v
  
    # Run E2E tests (may be optional for PR builds)
    python -m pytest tests/e2e -v

- name: Generate test report
  run: |
    python scripts/run_all_tests.py > test_results.txt
  
- name: Upload test results
  uses: actions/upload-artifact@v3
  if: always()
  with:
    name: test-results
    path: |
      test_results.txt
      htmlcov/
```
