#!/bin/bash

# Teardown script - terminates all resources

set -e

AWS_REGION="${AWS_REGION:-us-east-1}"

echo "========================================="
echo "Tearing down AWS resources"
echo "========================================="

# Get instances by tag
echo "Finding instances..."
INSTANCES=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=form-submission-*" "Name=instance-state-name,Values=running,pending,stopped" \
    --region "$AWS_REGION" \
    --query 'Reservations[*].Instances[*].InstanceId' \
    --output text)

if [ -z "$INSTANCES" ]; then
    echo "No instances found to terminate"
else
    echo "Terminating instances: $INSTANCES"
    aws ec2 terminate-instances --instance-ids $INSTANCES --region "$AWS_REGION"
    echo "Instances terminated"
fi

# Release Elastic IPs
echo ""
echo "Finding Elastic IPs..."
EIPS=$(aws ec2 describe-addresses \
    --region "$AWS_REGION" \
    --query 'Addresses[?AssociationId!=`null`].AllocationId' \
    --output text)

if [ -z "$EIPS" ]; then
    echo "No Elastic IPs found"
else
    for EIP in $EIPS; do
        echo "Releasing Elastic IP: $EIP"
        aws ec2 release-address --allocation-id "$EIP" --region "$AWS_REGION" || true
    done
fi

echo ""
echo "========================================="
echo "Teardown complete!"
echo "========================================="
echo ""
echo "NOTE: Security group and key pair were not deleted."
echo "To delete them manually:"
echo "  aws ec2 delete-security-group --group-name form-submission-sg --region $AWS_REGION"
echo "  aws ec2 delete-key-pair --key-name form-submission-key --region $AWS_REGION"
echo ""
