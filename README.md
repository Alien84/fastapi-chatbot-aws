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

**2.1. Create an IAM User for GitHub Actions:** Using the AWS Management Console or AWS CLI:

```
# Create a deployment user with programmatic access
aws iam create-user --user-name github-actions-deployment

# Attach the necessary policies (use more restrictive policies in production)
aws iam attach-user-policy --user-name github-actions-deployment --policy-arn arn:aws:iam::aws:policy/AmazonEC2FullAccess
aws iam attach-user-policy --user-name github-actions-deployment --policy-arn arn:aws:iam::aws:policy/AmazonRDSFullAccess
aws iam attach-user-policy --user-name github-actions-deployment --policy-arn arn:aws:iam::aws:policy/AmazonVPCFullAccess
aws iam attach-user-policy --user-name github-actions-deployment --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite

# Create access keys
aws iam create-access-key --user-name github-actions-deployment
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
