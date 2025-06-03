#!/bin/bash

# Development rebuild script
set -e

echo "🔄 Rebuilding development environment..."

# Check what type of rebuild is needed
REBUILD_TYPE=${1:-"normal"}

case $REBUILD_TYPE in
    "quick")
        echo "📝 Quick restart for code changes..."
        docker-compose restart app
        ;;
    "deps")
        echo "📦 Rebuilding due to dependency changes..."
        docker-compose down
        docker-compose build --no-cache app
        docker-compose up -d
        ;;
    "clean")
        echo "🧹 Clean rebuild..."
        docker-compose down
        docker-compose build --no-cache
        docker-compose up -d
        ;;
    "reset")
        echo "💥 Complete reset (WARNING: This will delete all data)..."
        read -p "Are you sure? This will delete all database data. (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose down -v
            docker system prune -f
            docker-compose up --build -d
        else
            echo "Reset cancelled."
            exit 0
        fi
        ;;
    *)
        echo "🔨 Normal rebuild..."
        docker-compose down
        docker-compose up --build -d
        ;;
esac

echo "✅ Rebuild complete!"
echo "🌐 Application available at: http://localhost:8000"
echo "📚 API docs available at: http://localhost:8000/docs"

# Check if the application is responding
echo "🔍 Checking application health..."
sleep 5

if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Application is healthy!"
else
    echo "⚠️  Application may not be ready yet. Check logs with: docker-compose logs app"
fi