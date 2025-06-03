#!/bin/bash

echo "🐛 Starting debug environment..."

# Stop any existing debug containers
docker compose -f docker-compose.debug.yml down

# Start debug containers
docker compose -f docker-compose.debug.yml up -d --build

echo "⏳ Waiting for containers to be ready..."
sleep 15

# Check if containers are running
if docker compose -f docker-compose.debug.yml ps | grep -q "Up"; then
    echo "✅ Debug environment is ready!"
    echo ""
    echo "🔌 Debugger is waiting for VS Code to attach on port 5678"
    echo "🗄️  Database is running on port 5433 (to avoid conflict with your main setup)"
    echo "🌐 Application will be available at http://localhost:8000 after debugger attaches"
    echo ""
    echo "📋 Available development tools in container:"
    echo "  - debugpy (VS Code debugging)"
    echo "  - pytest (testing)"
    echo "  - black & isort (code formatting)"
    echo "  - flake8 & mypy (linting/type checking)"
    echo "  - ipython & ipdb (interactive debugging)"
    echo "  - bandit (security analysis)"
    echo ""
    echo "🛠️  Quick commands:"
    echo "  Format code: docker compose -f docker-compose.debug.yml exec app-debug black ."
    echo "  Run tests: docker compose -f docker-compose.debug.yml exec app-debug pytest"
    echo "  Type check: docker compose -f docker-compose.debug.yml exec app-debug mypy ."
    echo "  Security scan: docker compose -f docker-compose.debug.yml exec app-debug bandit -r ."
    echo "  Install pre-commit hooks: docker compose -f docker-compose.debug.yml exec app-debug pre-commit install"
    echo ""
    echo "Next steps:"
    echo "1. Set breakpoints in your Python code (app/ directory)"
    echo "2. In VS Code: Ctrl+Shift+D → Select 'Debug FastAPI in Docker' → Press F5"
    echo "3. Wait for debugger to attach (you'll see it in the terminal)"
    echo "4. Visit http://localhost:8000/docs to test your API"
    echo ""
    echo "To view logs: docker compose -f docker-compose.debug.yml logs -f app-debug"
    echo "To stop: ./scripts/debug_stop.sh"
else
    echo "❌ Failed to start debug environment"
    echo "Showing logs:"
    docker compose -f docker-compose.debug.yml logs
fi