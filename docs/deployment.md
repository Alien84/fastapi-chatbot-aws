# Deployment Guide

## Prerequisites

- GitHub account with access to this repository
- AWS account with appropriate permissions
- Pulumi account with access token

## Deployment Environments

- **dev**: Development environment for testing new features
- **staging**: Pre-production environment for final testing
- **prod**: Production environment

## Deployment Process

### Automatic Deployments

Deployments are automatically triggered when code is pushed to the following branches:

- `develop` → deploys to `dev` environment
- `staging` → deploys to `staging` environment
- `main` → deploys to `prod` environment

### Manual Deployments

To trigger a manual deployment:

1. Go to the GitHub Actions tab
2. Select the "CD" workflow
3. Click "Run workflow"
4. Select the branch and environment
5. Click "Run workflow"

### Blue-Green Deployments

To toggle between blue and green deployments:

1. Go to the GitHub Actions tab
2. Select the "Toggle Blue-Green Deployment" workflow
3. Click "Run workflow"
4. Select the environment and next version (blue or green)
5. Click "Run workflow"

## Monitoring Deployments

Deployment status can be monitored:

- In GitHub Actions under the "CD" workflow
- In Slack in the #deployments channel
- In AWS CloudWatch dashboards

## Rollback Procedure

Automatic rollbacks occur if the deployment verification fails.

For manual rollbacks:

1. Go to the GitHub Actions tab
2. Select the "CD" workflow
3. Click "Run workflow"
4. Select the branch and environment
5. Enable the "Force rollback" option
6. Click "Run workflow"
