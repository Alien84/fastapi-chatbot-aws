#!/bin/bash
set -e

# Get repository URI
REPO_URI={lambda_ecr_repo.repository_url}

# Build the Docker image
echo "Building Docker image..."
cd ../lambda_functions/message_processor
docker build -t {lambda_ecr_repo.name}:{image_tag} .

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region {region.name} | docker login --username AWS --password-stdin $REPO_URI

# Tag and push the image
echo "Tagging and pushing image..."
docker tag {repo_name}:{image_tag} $REPO_URI:{image_tag}
docker push $REPO_URI:{image_tag}

echo "Docker image pushed successfully!"