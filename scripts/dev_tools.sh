#!/bin/bash

# Development tools script
COMMAND=${1:-help}

case $COMMAND in
    "format")
        echo "🎨 Formatting code with black and isort..."
        docker compose -f docker-compose.debug.yml exec app-debug black .
        docker compose -f docker-compose.debug.yml exec app-debug isort .
        echo "✅ Code formatted!"
        ;;
    "lint")
        echo "🔍 Running linting with flake8..."
        docker compose -f docker-compose.debug.yml exec app-debug flake8 .
        ;;
    "typecheck")
        echo "🏷️  Running type checking with mypy..."
        docker compose -f docker-compose.debug.yml exec app-debug mypy .
        ;;
    "test")
        echo "🧪 Running tests with pytest..."
        docker compose -f docker-compose.debug.yml exec app-debug pytest -v
        ;;
    "test-cov")
        echo "🧪 Running tests with coverage..."
        docker compose -f docker-compose.debug.yml exec app-debug pytest --cov=. --cov-report=html
        echo "📊 Coverage report generated in htmlcov/"
        ;;
    "security")
        echo "🔒 Running security analysis with bandit..."
        docker compose -f docker-compose.debug.yml exec app-debug bandit -r . -f json -o bandit-report.json
        docker compose -f docker-compose.debug.yml exec app-debug bandit -r .
        ;;
    "shell")
        echo "🐚 Starting interactive shell..."
        docker compose -f docker-compose.debug.yml exec app-debug /bin/bash
        ;;
    "ipython")
        echo "🐍 Starting IPython shell..."
        docker compose -f docker-compose.debug.yml exec app-debug ipython
        ;;
    "all")
        echo "🚀 Running all code quality checks..."
        docker compose -f docker-compose.debug.yml exec app-debug black .
        docker compose -f docker-compose.debug.yml exec app-debug isort .
        docker compose -f docker-compose.debug.yml exec app-debug flake8 .
        docker compose -f docker-compose.debug.yml exec app-debug mypy .
        docker compose -f docker-compose.debug.yml exec app-debug pytest
        docker compose -f docker-compose.debug.yml exec app-debug bandit -r .
        echo "✅ All checks completed!"
        ;;
    *)
        echo "🛠️  Development Tools"
        echo "Usage: $0 <command>"
        echo ""
        echo "Available commands:"
        echo "  format     - Format code with black and isort"
        echo "  lint       - Run flake8 linting"
        echo "  typecheck  - Run mypy type checking"
        echo "  test       - Run pytest tests"
        echo "  test-cov   - Run tests with coverage report"
        echo "  security   - Run bandit security analysis"
        echo "  shell      - Start interactive bash shell"
        echo "  ipython    - Start IPython shell"
        echo "  all        - Run all code quality checks"
        echo ""
        echo "Examples:"
        echo "  $0 format"
        echo "  $0 test"
        echo "  $0 all"
        ;;
esac