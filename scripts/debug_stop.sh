#!/bin/bash

echo "🛑 Stopping debug environment..."
docker compose -f docker-compose.debug.yml down

echo "✅ Debug environment stopped"
echo "Your main development environment (docker-compose.yml) is unaffected"