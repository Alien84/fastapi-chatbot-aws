#!/bin/bash

# Development logging script
SERVICE=${1:-"app"}

echo "📋 Showing logs for service: $SERVICE"
echo "Press Ctrl+C to exit"
echo "---"

docker-compose logs -f $SERVICE