#!/bin/bash

# Docker Installation Script for EC2 instances
# Run this on both instances after they're launched

set -e

echo "========================================="
echo "Installing Docker and Dependencies"
echo "========================================="

# Update system
echo "Updating system packages..."
sudo yum update -y

# Install Docker
echo "Installing Docker..."
sudo yum install -y docker

# Start Docker service
echo "Starting Docker service..."
sudo systemctl start docker
sudo systemctl enable docker

# Add ec2-user to docker group
sudo usermod -a -G docker ec2-user

# Install Docker Compose
echo "Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

# Install Git
echo "Installing Git..."
sudo yum install -y git

# Verify installations
echo ""
echo "Verifying installations..."
docker --version
docker-compose --version
git --version

echo ""
echo "========================================="
echo "Docker installation complete!"
echo "========================================="
echo ""
echo "IMPORTANT: Log out and log back in for group changes to take effect"
echo "Or run: newgrp docker"
echo ""
