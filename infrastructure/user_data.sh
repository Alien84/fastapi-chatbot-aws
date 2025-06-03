#!/bin/bash

# Configure AWS CLI to use IMDSv2
mkdir -p ~/.aws
cat << EOF > ~/.aws/config
[default]
imds_version = v2
EOF

# Extensive logging
exec > >(tee /var/log/user-data-script.log 2>&1)

# Exit immediately if a command exits with a non-zero status
set -e

# Run as root (not needed if this script is run by EC2 as user_data)
#yum update -y is enough, no need for sudo in user_data
yum update -y

# Enable and install NGINX from amazon-linux-extras
amazon-linux-extras enable nginx1
yum clean metadata
yum install -y nginx

# Install Docker
yum install -y docker
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Install AWS CLI and other dependencies
yum install -y awscli amazon-cloudwatch-agent

# Install Docker Compose Plugin (V2)
mkdir -p /usr/local/lib/docker/cli-plugins
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-linux-x86_64" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Verify Docker Compose installation
docker compose version

# Create application directory
mkdir -p /opt/${name}-${stack_name}
mkdir -p /opt/${name}-${stack_name}/logs

# Create environment file for the container
cat << EOF > /opt/${name}-${stack_name}/.env
DB_SSM_PREFIX=${DB_SSM_PREFIX}
AWS_REGION=${AWS_REGION}
EOF

# Create Docker Compose file for production
cat << EOF > /opt/${name}-${stack_name}/docker-compose.yml
version: '3.8'

services:
  ${name}-${stack_name}:
    image: ${ECR_REPOSITORY_URL}:latest
    ports:
      - "8000:8000"
    environment:
      - DB_SSM_PREFIX=${DB_SSM_PREFIX}
      - AWS_REGION=${AWS_REGION}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "awslogs"
      options:
        awslogs-group: "/aws/ec2/${name}-${stack_name}"
        awslogs-region: "${AWS_REGION}"
        awslogs-stream-prefix: "${name}-${stack_name}-app"
EOF

# Create a script to pull and run the latest container
cat << 'EOF' > /opt/${name}-${stack_name}/deploy.sh
#!/bin/bash
set -e  # Exit on any error

echo "Starting deployment at $(date)"

# Get ECR login token
echo "Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REPOSITORY_URL}

# Pull the latest image
echo "Pulling latest image..."
docker compose -f /opt/${name}-${stack_name}/docker-compose.yml pull

# Stop and remove old containers
echo "Stopping old containers..."
docker compose -f /opt/${name}-${stack_name}/docker-compose.yml down

# Start new containers
echo "Starting new containers..."
docker compose -f /opt/${name}-${stack_name}/docker-compose.yml up -d

# Verify containers are running
echo "Verifying containers..."
sleep 10
docker compose -f /opt/${name}-${stack_name}/docker-compose.yml ps

# Clean up unused images
echo "Cleaning up unused images..."
docker image prune -f

echo "Deployment completed successfully at $(date)"
EOF

chmod +x /opt/${name}-${stack_name}/deploy.sh

# Run the initial deployment
cd /opt/${name}-${stack_name}
./deploy.sh

# Setup CloudWatch agent configuration
cat << EOF > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
{
    "agent": {
        "metrics_collection_interval": 60,
        "run_as_user": "root"
    },
    "logs": {
        "logs_collected": {
            "files": {
                "collect_list": [
                    {
                        "file_path": "/var/log/messages",
                        "log_group_name": "/aws/ec2/${name}-${stack_name}",
                        "log_stream_name": "{instance_id}/syslog",
                        "retention_in_days": 30
                    },
                    {
                        "file_path": "/var/log/nginx/access.log",
                        "log_group_name": "/aws/ec2/${name}-${stack_name}",
                        "log_stream_name": "{instance_id}/nginx-access",
                        "retention_in_days": 30
                    },
                    {
                        "file_path": "/var/log/nginx/error.log",
                        "log_group_name": "/aws/ec2/${name}-${stack_name}",
                        "log_stream_name": "{instance_id}/nginx-error",
                        "retention_in_days": 30
                    }
                ]
            }
        }
    },
    "metrics": {
        "metrics_collected": {
            "cpu": {
                "measurement": [
                    "cpu_usage_idle",
                    "cpu_usage_iowait",
                    "cpu_usage_user",
                    "cpu_usage_system"
                ],
                "metrics_collection_interval": 60,
                "totalcpu": false
            },
            "mem": {
                "measurement": [
                    "mem_used_percent"
                ],
                "metrics_collection_interval": 60
            },
            "disk": {
                "measurement": [
                    "used_percent"
                ],
                "metrics_collection_interval": 60,
                "resources": [
                    "/"
                ]
            },
            "diskio": {
                "measurement": [
                    "io_time",
                    "write_bytes",
                    "read_bytes",
                    "writes",
                    "reads"
                ],
                "metrics_collection_interval": 60,
                "resources": [
                    "*"
                ]
            },
            "swap": {
                "measurement": [
                    "swap_used_percent"
                ],
                "metrics_collection_interval": 60
            },
            "netstat": {
                "measurement": [
                    "tcp_established",
                    "tcp_time_wait"
                ],
                "metrics_collection_interval": 60
            },
            "processes": {
                "measurement": [
                    "running",
                    "sleeping",
                    "dead"
                ],
                "metrics_collection_interval": 60
            }
        }
    }
}
EOF

systemctl daemon-reload

# Start the CloudWatch agent
systemctl enable amazon-cloudwatch-agent
systemctl start amazon-cloudwatch-agent

# Configure Nginx
cat <<EOF > /etc/nginx/conf.d/${name}-${stack_name}.conf
upstream ${name}-${stack_name}_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://${name}-${stack_name}_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Health check timeout
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    location /health {
        proxy_pass http://${name}-${stack_name}_backend/health;
        access_log off;
    }
}
EOF

# Start Nginx
systemctl enable nginx
systemctl start nginx