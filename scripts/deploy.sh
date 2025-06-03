#!/bin/bash
set -e

echo "Starting deployment..."

# Check if required environment variables are set
if [ -z "$AWS_REGION" ]; then
    echo "Error: AWS_REGION environment variable is not set"
    exit 1
fi

if [ -z "$PULUMI_ACCESS_TOKEN" ]; then
    echo "Error: PULUMI_ACCESS_TOKEN environment variable is not set"
    exit 1
fi

# Set default stack if not provided
STACK=${STACK:-dev}

echo "Deploying to stack: $STACK"

# Navigate to infrastructure directory
cd infrastructure

# Install dependencies
echo "Installing Pulumi dependencies..."
pip install -r requirements.txt

# Deploy infrastructure
echo "Deploying infrastructure..."
pulumi stack select $STACK
pulumi up --yes

echo "Deployment completed successfully!"