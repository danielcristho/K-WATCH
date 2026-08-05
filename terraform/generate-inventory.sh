#!/bin/bash
# Generate Ansible inventory from Terraform outputs

set -e

cd "$(dirname "$0")"

echo "Generating Ansible inventory from Terraform..."

# Reads the worker outputs as JSON lists so any worker_count works
tf_list() { terraform output -json "$1" 2>/dev/null | python3 -c 'import json,sys; print(*json.load(sys.stdin))' 2>/dev/null; }

MASTER_IP=$(terraform output -raw master_public_ip 2>/dev/null || true)
MASTER_PRIVATE_IP=$(terraform output -raw master_private_ip 2>/dev/null || true)
read -ra WORKER_IPS <<< "$(tf_list worker_public_ips)"
read -ra WORKER_PRIVATE_IPS <<< "$(tf_list worker_private_ips)"
SIEM_IP=$(terraform output -raw siem_public_ip 2>/dev/null || true)
SIEM_PRIVATE_IP=$(terraform output -raw siem_private_ip 2>/dev/null || true)

if [ -z "$MASTER_IP" ] || [ ${#WORKER_IPS[@]} -eq 0 ]; then
    echo "Error: Terraform outputs not found. Run 'terraform apply' first."
    exit 1
fi

echo "Master  : $MASTER_IP (private: $MASTER_PRIVATE_IP)"
for i in "${!WORKER_IPS[@]}"; do
    echo "Worker-$((i + 1)): ${WORKER_IPS[$i]} (private: ${WORKER_PRIVATE_IPS[$i]})"
done
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
EOF

for i in "${!WORKER_IPS[@]}"; do
    echo "k8s-worker-$((i + 1)) ansible_host=${WORKER_IPS[$i]} private_ip=${WORKER_PRIVATE_IPS[$i]}" >> ../ansible/hosts
done

cat >> ../ansible/hosts <<EOF

[siem]
k8s-siem ansible_host=$SIEM_IP private_ip=$SIEM_PRIVATE_IP

[k8s_cluster:children]
masters
workers
siem
EOF

echo "✓ Ansible inventory generated: ../ansible/hosts"
echo ""
echo "Next: cd ../ansible && ansible-playbook playbook.yml"
