#!/bin/bash

# Development status script
echo "🔍 Development Environment Status"
echo "================================="

# Check if containers are running
echo "📦 Container Status:"
docker-compose ps

echo ""
echo "🌐 Application Endpoints:"
echo "  - Main App: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Health Check: http://localhost:8000/health"

echo ""
echo "🗄️  Database Connection:"
if docker-compose exec -T db pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "  ✅ Database is ready"
else
    echo "  ❌ Database is not ready"
fi

echo ""
echo "🔍 Quick Health Check:"
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "  ✅ Application is responding"
else
    echo "  ❌ Application is not responding"
fi