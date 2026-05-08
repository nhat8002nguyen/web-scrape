#!/bin/bash

# AWS EC2 Spot Instance Setup Script for Budget-Optimized Deployment
# This script launches 2 t3.medium spot instances for the distributed form submission system

set -e

echo "========================================="
echo "AWS EC2 Spot Instance Setup"
echo "========================================="

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="t3.medium"
AMI_ID="ami-0c02fb55b2066f50e"  # Amazon Linux 2023 (update for your region)
KEY_NAME="${AWS_KEY_NAME:-form-submission-key}"
SECURITY_GROUP_NAME="form-submission-sg"
SPOT_MAX_PRICE="0.02"  # $0.02/hour (70% discount from on-demand)

echo "Region: $AWS_REGION"
echo "Instance Type: $INSTANCE_TYPE"
echo "Spot Max Price: \$${SPOT_MAX_PRICE}/hour"
echo ""

# Check AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "ERROR: AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "ERROR: AWS credentials not configured. Run 'aws configure' first."
    exit 1
fi

# Create key pair if doesn't exist
echo "Checking SSH key pair..."
if ! aws ec2 describe-key-pairs --key-names "$KEY_NAME" --region "$AWS_REGION" &> /dev/null; then
    echo "Creating new key pair: $KEY_NAME"
    aws ec2 create-key-pair \
        --key-name "$KEY_NAME" \
        --region "$AWS_REGION" \
        --query 'KeyMaterial' \
        --output text > "${KEY_NAME}.pem"
    chmod 400 "${KEY_NAME}.pem"
    echo "Key pair created and saved to ${KEY_NAME}.pem"
else
    echo "Key pair already exists: $KEY_NAME"
fi

# Create security group if doesn't exist
echo "Setting up security group..."
SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" \
    --region "$AWS_REGION" \
    --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || echo "None")

if [ "$SG_ID" == "None" ]; then
    echo "Creating security group: $SECURITY_GROUP_NAME"
    SG_ID=$(aws ec2 create-security-group \
        --group-name "$SECURITY_GROUP_NAME" \
        --description "Security group for form submission system" \
        --region "$AWS_REGION" \
        --query 'GroupId' \
        --output text)
    
    # Allow SSH
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 22 \
        --cidr 0.0.0.0/0 \
        --region "$AWS_REGION"
    
    # Allow Kafka
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 9092 \
        --source-group "$SG_ID" \
        --region "$AWS_REGION"
    
    # Allow Redis
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 6379 \
        --source-group "$SG_ID" \
        --region "$AWS_REGION"
    
    # Allow PostgreSQL
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 5432 \
        --source-group "$SG_ID" \
        --region "$AWS_REGION"
    
    # Allow Prometheus
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 9090 \
        --cidr 0.0.0.0/0 \
        --region "$AWS_REGION"
    
    # Allow Metrics
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 8080 \
        --source-group "$SG_ID" \
        --region "$AWS_REGION"
    
    echo "Security group created: $SG_ID"
else
    echo "Security group already exists: $SG_ID"
fi

# User data script for instance initialization
USER_DATA='#!/bin/bash
yum update -y
yum install -y docker git
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose

# Create working directory
mkdir -p /opt/form-submission
chown ec2-user:ec2-user /opt/form-submission
'

# Launch Instance 1 (Kafka + Redis + PostgreSQL + Discovery)
echo ""
echo "Launching Instance 1 (Data Services + Discovery Workers)..."
INSTANCE1_ID=$(aws ec2 request-spot-instances \
    --spot-price "$SPOT_MAX_PRICE" \
    --instance-count 1 \
    --type "one-time" \
    --launch-specification "{
        \"ImageId\": \"$AMI_ID\",
        \"InstanceType\": \"$INSTANCE_TYPE\",
        \"KeyName\": \"$KEY_NAME\",
        \"SecurityGroupIds\": [\"$SG_ID\"],
        \"UserData\": \"$(echo "$USER_DATA" | base64 -w 0)\",
        \"BlockDeviceMappings\": [{
            \"DeviceName\": \"/dev/xvda\",
            \"Ebs\": {
                \"VolumeSize\": 100,
                \"VolumeType\": \"gp3\",
                \"DeleteOnTermination\": true
            }
        }],
        \"TagSpecifications\": [{
            \"ResourceType\": \"instance\",
            \"Tags\": [{
                \"Key\": \"Name\",
                \"Value\": \"form-submission-instance1\"
            }, {
                \"Key\": \"Role\",
                \"Value\": \"data-discovery\"
            }]
        }]
    }" \
    --region "$AWS_REGION" \
    --query 'SpotInstanceRequests[0].SpotInstanceRequestId' \
    --output text)

echo "Spot request created for Instance 1: $INSTANCE1_ID"

# Launch Instance 2 (Submission Workers + Prometheus)
echo ""
echo "Launching Instance 2 (Submission Workers + Monitoring)..."
INSTANCE2_ID=$(aws ec2 request-spot-instances \
    --spot-price "$SPOT_MAX_PRICE" \
    --instance-count 1 \
    --type "one-time" \
    --launch-specification "{
        \"ImageId\": \"$AMI_ID\",
        \"InstanceType\": \"$INSTANCE_TYPE\",
        \"KeyName\": \"$KEY_NAME\",
        \"SecurityGroupIds\": [\"$SG_ID\"],
        \"UserData\": \"$(echo "$USER_DATA" | base64 -w 0)\",
        \"BlockDeviceMappings\": [{
            \"DeviceName\": \"/dev/xvda\",
            \"Ebs\": {
                \"VolumeSize\": 100,
                \"VolumeType\": \"gp3\",
                \"DeleteOnTermination\": true
            }
        }],
        \"TagSpecifications\": [{
            \"ResourceType\": \"instance\",
            \"Tags\": [{
                \"Key\": \"Name\",
                \"Value\": \"form-submission-instance2\"
            }, {
                \"Key\": \"Role\",
                \"Value\": \"submission-monitoring\"
            }]
        }]
    }" \
    --region "$AWS_REGION" \
    --query 'SpotInstanceRequests[0].SpotInstanceRequestId' \
    --output text)

echo "Spot request created for Instance 2: $INSTANCE2_ID"

# Wait for spot instances to be fulfilled
echo ""
echo "Waiting for spot instances to be fulfilled (this may take a few minutes)..."
sleep 30

# Get instance IDs
INSTANCE1=$(aws ec2 describe-spot-instance-requests \
    --spot-instance-request-ids "$INSTANCE1_ID" \
    --region "$AWS_REGION" \
    --query 'SpotInstanceRequests[0].InstanceId' \
    --output text)

INSTANCE2=$(aws ec2 describe-spot-instance-requests \
    --spot-instance-request-ids "$INSTANCE2_ID" \
    --region "$AWS_REGION" \
    --query 'SpotInstanceRequests[0].InstanceId' \
    --output text)

echo "Instance 1 ID: $INSTANCE1"
echo "Instance 2 ID: $INSTANCE2"

# Wait for instances to be running
echo ""
echo "Waiting for instances to be running..."
aws ec2 wait instance-running --instance-ids "$INSTANCE1" "$INSTANCE2" --region "$AWS_REGION"

# Get public IPs
INSTANCE1_IP=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE1" \
    --region "$AWS_REGION" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

INSTANCE2_IP=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE2" \
    --region "$AWS_REGION" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

# Allocate and associate Elastic IP for Instance 2 (for Prometheus access)
echo ""
echo "Allocating Elastic IP for Instance 2..."
EIP_ALLOC=$(aws ec2 allocate-address --region "$AWS_REGION" --query 'AllocationId' --output text)
aws ec2 associate-address --instance-id "$INSTANCE2" --allocation-id "$EIP_ALLOC" --region "$AWS_REGION"

EIP=$(aws ec2 describe-addresses --allocation-ids "$EIP_ALLOC" --region "$AWS_REGION" --query 'Addresses[0].PublicIp' --output text)

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Instance 1 (Data + Discovery):"
echo "  Instance ID: $INSTANCE1"
echo "  Public IP: $INSTANCE1_IP"
echo "  SSH: ssh -i ${KEY_NAME}.pem ec2-user@$INSTANCE1_IP"
echo ""
echo "Instance 2 (Submission + Monitoring):"
echo "  Instance ID: $INSTANCE2"
echo "  Elastic IP: $EIP"
echo "  SSH: ssh -i ${KEY_NAME}.pem ec2-user@$EIP"
echo "  Prometheus: http://$EIP:9090"
echo ""
echo "Next steps:"
echo "1. Run ./install-docker.sh on both instances"
echo "2. Deploy services with ./deploy-instance1.sh and ./deploy-instance2.sh"
echo ""
echo "Save these IPs for deployment:"
echo "export INSTANCE1_IP=$INSTANCE1_IP"
echo "export INSTANCE2_IP=$EIP"
echo "export KEY_FILE=${KEY_NAME}.pem"
echo ""
