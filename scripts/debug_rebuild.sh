#!/bin/bash

echo "🔄 Rebuilding debug environment..."

# Stop containers
docker compose -f docker-compose.debug.yml down

# Rebuild and start
docker compose -f docker-compose.debug.yml up -d --build --force-recreate

echo "✅ Debug environment rebuilt"
echo "🔌 Debugger is waiting for VS Code to attach on port 5678"