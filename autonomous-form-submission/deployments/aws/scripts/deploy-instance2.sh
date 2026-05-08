#!/bin/bash

# Deployment script for Instance 2 (Submission Workers + Monitoring)

set -e

INSTANCE_IP="${INSTANCE2_IP:-$1}"
KEY_FILE="${KEY_FILE:-$2}"
KAFKA_HOST="${INSTANCE1_IP:-$3}"

if [ -z "$INSTANCE_IP" ] || [ -z "$KEY_FILE" ] || [ -z "$KAFKA_HOST" ]; then
    echo "Usage: $0 <instance-ip> <key-file> <kafka-host-ip>"
    echo "Or set INSTANCE2_IP, KEY_FILE, and INSTANCE1_IP environment variables"
    exit 1
fi

echo "========================================="
echo "Deploying to Instance 2"
echo "Instance: $INSTANCE_IP"
echo "Kafka Host: $KAFKA_HOST"
echo "========================================="

# Copy project files to instance
echo "Copying project files..."
rsync -avz -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=no" \
    --exclude '.git' \
    --exclude 'bin' \
    --exclude '*.log' \
    ../../../ ec2-user@$INSTANCE_IP:/opt/form-submission/

# Create .env file with cross-instance configuration
cat > /tmp/instance2.env << ENVEOF
KAFKA_BROKERS=$KAFKA_HOST:9092
REDIS_HOST=$KAFKA_HOST:6379
POSTGRES_HOST=$KAFKA_HOST:5432
CAPSOLVER_API_KEY=${CAPSOLVER_API_KEY}
PROXY_API_KEY=${PROXY_API_KEY}
ENVEOF

# Copy .env file
scp -i "$KEY_FILE" -o StrictHostKeyChecking=no /tmp/instance2.env ec2-user@$INSTANCE_IP:/opt/form-submission/.env
rm /tmp/instance2.env

# SSH into instance and deploy
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ec2-user@$INSTANCE_IP << 'EOF'
cd /opt/form-submission

echo "Starting submission workers and monitoring..."

# Build and start services
docker-compose -f deployments/docker/docker-compose.instance2.yml build
docker-compose -f deployments/docker/docker-compose.instance2.yml --env-file .env up -d

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
sleep 30

# Check service status
docker-compose -f deployments/docker/docker-compose.instance2.yml ps

echo ""
echo "Instance 2 deployment complete!"
echo ""
echo "Services running:"
echo "- 10 Submission Workers"
echo "- Prometheus (port 9090)"
echo ""
echo "Logs: docker-compose -f deployments/docker/docker-compose.instance2.yml logs -f"
EOF

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Access Prometheus at: http://$INSTANCE_IP:9090"
echo ""
