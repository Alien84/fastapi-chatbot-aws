# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

FastAPI chatbot application deployed on AWS using Pulumi IaC and GitHub Actions CI/CD. The system uses EC2 instances (with optional autoscaling), RDS PostgreSQL database, Lambda functions for async processing, and ECR for container registry.

## Architecture

### Infrastructure (Pulumi)
- **Entry Point**: `infrastructure/__main__.py` - Main Pulumi program defining all AWS resources
- **Modules**: `infrastructure/modules/` contains modular resource definitions:
  - `vpc.py` - VPC with public/private subnets, NAT gateways, route tables
  - `ec2.py` - EC2 instance configuration utilities
  - `rds.py` - PostgreSQL RDS instance with subnet groups
  - `secrets.py` - AWS SSM Parameter Store (preferred) and Secrets Manager helpers
  - `lambda_functions.py` - Message processor Lambda function
  - `lambda_api_gateway.py` - API stats Lambda with API Gateway integration
- **Deployment Stages**: Controlled by `deploy_stage` config (ecr, lambda, all)
- **Stacks**: dev, staging, prod (configured via `Pulumi.<stack>.yaml`)

### Application (FastAPI)
- **Entry Point**: `app/main.py` - FastAPI application with chat endpoints
- **Database Config**: Uses SSM Parameter Store in production (`get_ssm_parameters()`) or env vars for local development
- **Lambda Integration**: Triggers message processor Lambda asynchronously via `trigger_message_processing()`
- **Containerized**: Dockerfile for production, Dockerfile.dev for debugging

### Lambda Functions
- `lambda_functions/message_processor/` - Processes chat messages asynchronously (e.g., sentiment analysis)
- `lambda_functions/api_gateway/` - Stats API Lambda with API Gateway integration
- Both use Docker containers stored in ECR

### Database
- RDS PostgreSQL instance created in public subnets (can be moved to private)
- Credentials stored in SSM Parameter Store at `/{name}/{stack_name}/db/*`
- Security group restricts access to web server security group only

## Common Development Commands

### Infrastructure Deployment

```bash
# From infrastructure/ directory
cd infrastructure

# Activate virtual environment
source infra-venv/bin/activate  # or venv/bin/activate

# Install Pulumi dependencies
pip install -r requirements.txt

# Select stack
pulumi stack select dev

# Preview changes
pulumi preview

# Deploy infrastructure (ECR only)
pulumi up --config deploy_stage=ecr

# Deploy with Lambda functions
pulumi up --config deploy_stage=lambda

# Deploy everything
pulumi up --config deploy_stage=all

# Destroy infrastructure
pulumi destroy

# View outputs
pulumi stack output
pulumi stack output ecr_repository_url
pulumi stack output application_url
```

### Local Application Development

```bash
# Option 1: Docker Compose (recommended)
./scripts/dev_setup.sh              # Initial setup
./scripts/dev_rebuild.sh            # Normal rebuild
./scripts/dev_rebuild.sh deps       # Rebuild with dependency changes
./scripts/dev_rebuild.sh reset      # Complete reset
./scripts/dev_status.sh             # Check container status
./scripts/dev_logs.sh               # View logs

# Option 2: VS Code Debug Mode
./scripts/debug_start.sh            # Start debug environment
# Then use "Debug FastAPI in Docker" launch config
./scripts/debug_stop.sh             # Stop debug environment

# Development tools
./scripts/dev_tools.sh format       # Format code
./scripts/dev_tools.sh test         # Run tests
./scripts/dev_tools.sh all          # Run all quality checks
```

### Docker Operations

```bash
# Build and push to ECR (from root directory)
aws ecr get-login-password --region eu-west-2 | docker login --username AWS --password-stdin <ecr-url>
docker build -t chatbot-dev-app app/
docker tag chatbot-dev-app:latest <ecr-url>:latest
docker push <ecr-url>:latest

# Build Lambda Docker images
cd lambda_functions/message_processor
docker build -t message-processor:latest .
docker tag message-processor:latest <lambda-ecr-url>:latest
docker push <lambda-ecr-url>:latest
```

### Testing

```bash
# Run all tests
python tests/run_all_tests.py

# Run specific test categories
pytest tests/database/ -v           # Database tests
pytest tests/api/ -v                # API tests
pytest tests/lambda/ -v             # Lambda tests
pytest tests/infrastructure/ -v     # Infrastructure tests
pytest tests/e2e/ -v                # End-to-end tests

# Test Lambda locally
cd tests/unit
pytest test_message_processor_unit.py -v
pytest test_message_processor_integration.py -v

# Test deployed Lambda
cd tests/lambda
python test_lambda_aws_direct.py
python test_e2e_workflow.py
```

## Configuration Management

### Pulumi Stack Configuration
Each stack has its own config file (`Pulumi.<stack>.yaml`):
- `aws:region` - AWS region (e.g., eu-west-2)
- `infrastructure:keyName` - EC2 key pair name
- `infrastructure:instanceType` - EC2 instance type (t2.micro, t2.small, etc.)
- `infrastructure:architecture` - "single" or "autoscaling"
- `infrastructure:name` - Resource name prefix (e.g., "chatbot")
- `fastapi-chatbot-infrastructure:deploy_stage` - "ecr", "lambda", or "all"

### Environment Variables
- **Production (EC2)**: Reads from SSM Parameter Store via `DB_SSM_PREFIX`
- **Local Dev**: Uses `.env` file with DB_HOST, DB_USERNAME, DB_PASSWORD, DB_NAME, DB_PORT
- **Lambda**: Gets database config from SSM Parameter Store

## Critical Architecture Details

### Two-Stage Deployment Process
The infrastructure uses a two-stage deployment to handle ECR chicken-and-egg problem:

1. **Stage 1 (deploy_stage=ecr)**: Creates ECR repositories
2. **Build & Push**: Build and push Docker images to ECR
3. **Stage 2 (deploy_stage=lambda or all)**: Creates Lambda functions and EC2 instances using ECR images

This is reflected in GitHub Actions workflows which build/push images between Pulumi steps.

### Security Group Configuration
- `web_sg` - Allows HTTP (80), HTTPS (443), SSH (22) to EC2 instances
- `db_sg` - Allows PostgreSQL (5432) only from `web_sg`
- `lb_sg` - (Autoscaling mode) Allows HTTP/HTTPS to load balancer

### IAM Roles and Policies
EC2 instances require:
- ECR pull permissions (`ecr_policy`)
- SSM parameter read permissions (`secrets_policy`)
- Lambda invoke permissions (`lambda_invoke_policy`)
- CloudWatch Logs permissions (`logs_policy`)
- SSM managed instance core (`AmazonSSMManagedInstanceCore`)

### User Data Script
`infrastructure/user_data.sh` runs on EC2 instance launch:
- Installs Docker, NGINX, CloudWatch agent
- Authenticates with ECR
- Pulls Docker image from ECR
- Creates docker-compose.yml with environment variables
- Starts application container with health checks
- Configures NGINX as reverse proxy
- Sets up CloudWatch agent for system metrics

### Single vs Autoscaling Architecture
Controlled by `infrastructure:architecture` config:

**Single Mode**:
- One EC2 instance in public subnet
- Direct public IP access
- CloudWatch alarms for monitoring only

**Autoscaling Mode**:
- Application Load Balancer (ALB) in public subnets
- Auto Scaling Group (2-4 instances) across availability zones
- Target group with health checks
- CloudWatch alarms trigger scaling policies (CPU > 70% scales up, < 30% scales down)
- Access only via load balancer DNS

## GitHub Actions CI/CD

### Workflows
- `.github/workflows/ci.yml` - Linting and testing on PRs
- `.github/workflows/cd_with_docker.yml` - Main deployment workflow (manual trigger)
- `.github/workflows/cleanup.yml` - Cleanup dev/staging resources
- `.github/workflows/cleanup-dev.yml` - Cleanup specific dev stack

### Deployment Workflow (cd_with_docker.yml)
1. Set environment (dev/staging/prod) based on branch or manual input
2. Production requires typing "DEPLOY" for confirmation
3. Configure AWS credentials via OIDC (no static keys)
4. Build and push application Docker image to ECR
5. Run Pulumi preview
6. Deploy infrastructure with `deploy_stage=lambda`
7. Wait for EC2 instance to be ready (SSM)
8. Execute health check on EC2 instance
9. Run smoke tests

### GitHub Secrets Required
- `AWS_REGION` - AWS region
- `PULUMI_ACCESS_TOKEN` - Pulumi Cloud token

### AWS IAM Setup
Uses OIDC provider (no static credentials):
- GitHub OIDC provider in AWS IAM
- `GitHubActionsRole` with trust policy for repository
- Policy: `GitHubActionsDeploymentPolicy` with required permissions

## Database Schema

Key tables defined in `app/main.py`:
- `messages` - Chat messages with content and timestamps
- `sentiment_analysis` - Async analysis results linked to messages via message_id

## Monitoring and Observability

### CloudWatch
- Log groups: `/aws/ec2/{name}-{stack}` for application logs
- Lambda logs: `/aws/lambda/message-processor-lambda`
- CloudWatch Dashboard with CPU, memory, disk, network metrics
- Alarms for high CPU, memory, disk usage, RDS CPU, 5xx errors

### Health Checks
- Application: `http://localhost:8000/health`
- ALB target group health checks on port 80
- Docker container health checks every 30s

## Development Workflow Best Practices

### Making Infrastructure Changes
1. Modify code in `infrastructure/` directory
2. Test locally with `pulumi preview`
3. Deploy to dev first: `pulumi up --stack dev`
4. Verify changes work correctly
5. Promote to staging, then prod via GitHub Actions

### Making Application Changes
1. Develop locally using `./scripts/dev_setup.sh`
2. Set breakpoints and use VS Code debugger as needed
3. Run tests with `./scripts/dev_tools.sh test`
4. Create PR which triggers CI workflow
5. After merge, manually trigger CD workflow to deploy

### Lambda Function Changes
1. Build locally in `lambda_functions/<function-name>/`
2. Test with local emulator or unit tests
3. Push image to ECR via deployment workflow
4. Pulumi updates Lambda function with new image

## Troubleshooting

### EC2 Instance Not Starting
- Check user data logs: `sudo tail -f /var/log/user-data-script.log`
- Verify SSM parameters exist: `aws ssm get-parameters-by-path --path /chatbot/dev/db`
- Check Docker logs: `docker compose -f /opt/chatbot-dev/docker-compose.yml logs`

### Lambda Function Errors
- Check CloudWatch logs: `aws logs tail /aws/lambda/message-processor-lambda --follow`
- Verify VPC connectivity to RDS (Lambda in private subnet)
- Check IAM permissions for SSM and RDS access

### Database Connection Issues
- Verify security group allows traffic from web or Lambda security group
- Check database credentials in SSM Parameter Store
- Confirm RDS instance is in same VPC as EC2/Lambda

### Docker Image Pull Issues
- Verify ECR policy attached to EC2 IAM role
- Check ECR authentication: `aws ecr get-login-password`
- Confirm image exists: `aws ecr describe-images --repository-name chatbot-dev-app`
