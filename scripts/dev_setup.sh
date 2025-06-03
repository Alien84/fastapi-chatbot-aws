#!/bin/bash

echo "Setting up local development environment..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker compose &> /dev/null; then
    echo "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Start the development environment
echo "Starting PostgreSQL database..."
docker compose up -d db

# Wait for database to be ready
echo "Waiting for database to be ready..."
sleep 10

# Start the application
echo "Starting FastAPI application..."
docker compose up app