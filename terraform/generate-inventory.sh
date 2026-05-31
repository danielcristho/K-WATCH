#!/bin/bash
# Generate Ansible inventory from Terraform outputs

set -e

cd "$(dirname "$0")"

echo "Generating Ansible inventory from Terraform..."

# Get Terraform outputs
MASTER_IP=$(terraform output -raw master_public_ip 2>/dev/null)
MASTER_PRIVATE_IP=$(terraform output -raw master_private_ip 2>/dev/null)
WORKER_SPOT_ID=$(terraform output -raw worker_spot_id 2>/dev/null)

if [ -z "$MASTER_IP" ]; then
    echo "Error: Terraform outputs not found. Run 'terraform apply' first."
    exit 1
fi

# Get worker public IP
WORKER_IP=$(aws ec2 describe-instances \
    --instance-ids $WORKER_SPOT_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

WORKER_PRIVATE_IP=$(aws ec2 describe-instances \
    --instance-ids $WORKER_SPOT_ID \
    --query 'Reservations[0].Instances[0].PrivateIpAddress' \
    --output text)

echo "Master IP: $MASTER_IP (Private: $MASTER_PRIVATE_IP)"
echo "Worker IP: $WORKER_IP (Private: $WORKER_PRIVATE_IP)"

ANSIBLE_SSH_KEY_FILE="${SSH_KEY_FILE:-../terraform/daniel_aws.pem}"

# Generate Ansible inventory
cat > ../ansible/hosts <<EOF
[all:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=$ANSIBLE_SSH_KEY_FILE
ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'

[masters]
k8s-master ansible_host=$MASTER_IP private_ip=$MASTER_PRIVATE_IP

[workers]
k8s-worker-1 ansible_host=$WORKER_IP private_ip=$WORKER_PRIVATE_IP

[k8s_cluster:children]
masters
workers
EOF

echo "✓ Ansible inventory generated: ../ansible/hosts"
echo ""
echo "Next steps:"
echo "1. Wait 2-3 minutes for instances to fully boot"
echo "2. cd ../ansible"
echo "3. ansible-playbook playbook.yml"
