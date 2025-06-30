#!/bin/bash

echo "Creating Lambda deployment package..."

# Remove old package
rm -rf package/
rm -f lambda-package.zip

# Create package directory
mkdir package

# Install dependencies to package directory
pip install -r requirements.txt -t package/

# Copy Lambda function code
cp lambda_function.py package/

# Create zip file
cd package
zip -r ../lambda-package.zip .
cd ..

echo "Package created: lambda-package.zip"