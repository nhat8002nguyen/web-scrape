#!/bin/bash

# Deployment script for Instance 1 (Data Services + Discovery Workers)

set -e

INSTANCE_IP="${INSTANCE1_IP:-$1}"
KEY_FILE="${KEY_FILE:-$2}"

if [ -z "$INSTANCE_IP" ] || [ -z "$KEY_FILE" ]; then
    echo "Usage: $0 <instance-ip> <key-file>"
    echo "Or set INSTANCE1_IP and KEY_FILE environment variables"
    exit 1
fi

echo "========================================="
echo "Deploying to Instance 1"
echo "Instance: $INSTANCE_IP"
echo "========================================="

# Copy project files to instance
echo "Copying project files..."
rsync -avz -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=no" \
    --exclude '.git' \
    --exclude 'bin' \
    --exclude '*.log' \
    ../../../ ec2-user@$INSTANCE_IP:/opt/form-submission/

# SSH into instance and deploy
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ec2-user@$INSTANCE_IP << 'EOF'
cd /opt/form-submission

echo "Starting data services and discovery workers..."

# Build and start services
docker-compose -f deployments/docker/docker-compose.instance1.yml build
docker-compose -f deployments/docker/docker-compose.instance1.yml up -d

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
sleep 30

# Check service status
docker-compose -f deployments/docker/docker-compose.instance1.yml ps

echo ""
echo "Instance 1 deployment complete!"
echo ""
echo "Services running:"
echo "- Kafka (port 9092)"
echo "- Redis (port 6379)"
echo "- PostgreSQL (port 5432)"
echo "- 5 Discovery Workers"
echo ""
echo "Logs: docker-compose -f deployments/docker/docker-compose.instance1.yml logs -f"
EOF

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
