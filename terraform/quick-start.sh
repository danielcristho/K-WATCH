#!/bin/bash
# Quick Terraform deploy for K-IDS infrastructure

set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f terraform.tfvars ]; then
    echo "Error: terraform.tfvars not found."
    echo "Copy terraform.tfvars.example to terraform.tfvars and fill in your values first."
    exit 1
fi

echo "Initializing Terraform..."
terraform init

echo "Checking Terraform formatting..."
terraform fmt -check

echo "Validating Terraform configuration..."
terraform validate

echo "Creating Terraform plan..."
terraform plan -out=tfplan

echo "Applying Terraform plan..."
terraform apply -auto-approve tfplan

echo ""
echo "Infrastructure ready. Terraform outputs:"
terraform output
