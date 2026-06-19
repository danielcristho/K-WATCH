#!/bin/bash
# Generate Ansible inventory from Terraform outputs

set -e

cd "$(dirname "$0")"

echo "Generating Ansible inventory from Terraform..."

MASTER_IP=$(terraform output -raw master_public_ip 2>/dev/null)
MASTER_PRIVATE_IP=$(terraform output -raw master_private_ip 2>/dev/null)
WORKER_IP=$(terraform output -raw worker_public_ip 2>/dev/null)
WORKER_PRIVATE_IP=$(terraform output -raw worker_private_ip 2>/dev/null)
WORKER2_IP=$(terraform output -raw worker2_public_ip 2>/dev/null)
WORKER2_PRIVATE_IP=$(terraform output -raw worker2_private_ip 2>/dev/null)
SIEM_IP=$(terraform output -raw siem_public_ip 2>/dev/null)
SIEM_PRIVATE_IP=$(terraform output -raw siem_private_ip 2>/dev/null)

if [ -z "$MASTER_IP" ]; then
    echo "Error: Terraform outputs not found. Run 'terraform apply' first."
    exit 1
fi

echo "Master  : $MASTER_IP (private: $MASTER_PRIVATE_IP)"
echo "Worker-1: $WORKER_IP (private: $WORKER_PRIVATE_IP)"
echo "Worker-2: $WORKER2_IP (private: $WORKER2_PRIVATE_IP)"
echo "SIEM    : $SIEM_IP (private: $SIEM_PRIVATE_IP)"

ANSIBLE_SSH_KEY_FILE="${SSH_KEY_FILE:-../terraform/daniel_aws.pem}"

cat > ../ansible/hosts <<EOF
[all:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=$ANSIBLE_SSH_KEY_FILE
ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'

[masters]
k8s-master ansible_host=$MASTER_IP private_ip=$MASTER_PRIVATE_IP

[workers]
k8s-worker ansible_host=$WORKER_IP private_ip=$WORKER_PRIVATE_IP
k8s-worker-2 ansible_host=$WORKER2_IP private_ip=$WORKER2_PRIVATE_IP
k8s-siem ansible_host=$SIEM_IP private_ip=$SIEM_PRIVATE_IP

[k8s_cluster:children]
masters
workers
EOF

echo "✓ Ansible inventory generated: ../ansible/hosts"
echo ""
echo "Next: cd ../ansible && ansible-playbook playbook.yml"
