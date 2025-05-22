#!/bin/bash

# Create the complete directory structure
mkdir -p app/{api/endpoints,core,models,services}
mkdir -p infrastructure/{modules,config}
mkdir -p scripts
mkdir -p tests/{api,infrastructure,integration,unit}
mkdir -p .github/workflows
mkdir -p docs
mkdir -p config

# Create __init__.py files for Python packages
find app tests infrastructure -type d -exec touch {}/__init__.py \;

# Create placeholder files
touch app/main.py
touch app/core/{config.py,database.py,security.py}
touch app/api/{deps.py,api.py}
touch app/api/endpoints/{chat.py,health.py,history.py}
touch app/models/{chat.py,database.py}
touch app/services/{chat_service.py,database_service.py}

touch infrastructure/__main__.py
touch infrastructure/modules/{vpc.py,ec2.py,rds.py,secrets.py,monitoring.py}

touch scripts/{user_data.sh,deploy.sh,setup_db.py,health_check.py}

touch tests/conftest.py
touch tests/api/{test_chat.py,test_health.py,test_history.py}
touch tests/infrastructure/{test_vpc.py,test_ec2.py,test_rds.py}
touch tests/integration/{test_database.py,test_full_flow.py}
touch tests/unit/{test_models.py,test_services.py}

touch .github/workflows/{ci.yml,cd.yml,security.yml,cleanup.yml}

touch docs/{deployment.md,api.md,architecture.md,troubleshooting.md}

touch config/{dev.env,staging.env,prod.env,logging.yaml}

# Create essential root files
touch requirements.txt requirements-dev.txt .env.example

echo "Repository structure created successfully!"
echo "Don't forget to:"
echo "1. Add content to the created files"
echo "2. Initialize git and make your first commit"
echo "3. Set up your virtual environment"
echo "4. Install dependencies"