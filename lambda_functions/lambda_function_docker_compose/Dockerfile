# Use AWS Lambda Python 3.10 base image
FROM public.ecr.aws/lambda/python:3.10

# Set working directory, refer to readme file to learn more about LAMBDA_TASK_ROOT
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy requirements first for better caching
COPY src/requirements.txt .

# Install packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy function code
COPY src/lambda_function.py .

# Set the CMD to your handler
CMD ["lambda_function.lambda_handler"]