#!/bin/bash
# K-Watch: Complete Infrastructure Setup
# Provisions EC2 instances and installs Kubernetes (kubeadm) using Ansible.

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[✓]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
log_error() { echo -e "${RED}[✗]${NC} $*"; }
log_step()  { echo -e "${CYAN}[→]${NC} ${BOLD}$*${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_KEY_FILE="${SSH_KEY_FILE:-}"

if [ -z "$SSH_KEY_FILE" ]; then
    shopt -s nullglob
    for candidate in \
        "$SCRIPT_DIR/terraform"/*.pem \
        "$HOME/.ssh"/*.pem \
        "$HOME/.ssh/id_rsa" \
        "$HOME/.ssh/id_rsa_rsa"; do
        if [ -f "$candidate" ]; then
            SSH_KEY_FILE="$candidate"
            break
        fi
    done
    shopt -u nullglob
fi

if [ -z "$SSH_KEY_FILE" ] || [ ! -f "$SSH_KEY_FILE" ]; then
    log_error "SSH private key not found."
    echo -e "  Place your ${BOLD}.pem${NC} file in the ${BOLD}terraform/${NC} directory, or set SSH_KEY_FILE:"
    echo -e "  ${YELLOW}SSH_KEY_FILE=/path/to/your-key.pem ./setup-all.sh${NC}"
    exit 1
fi

export SSH_KEY_FILE
log_info "Using SSH key: ${BOLD}$SSH_KEY_FILE${NC}"

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}  ${BOLD}K-Watch${NC} Infra Setup                      ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}  Terraform + Ansible + Kubernetes            ${BLUE}║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Deploy infrastructure
log_step "Step 1/6: Deploying AWS infrastructure..."
cd "$SCRIPT_DIR/terraform"
./quick-start.sh

# Step 2: Wait for instances to boot
echo ""
log_step "Step 2/6: Waiting for instances to fully boot (60s)..."
sleep 60
log_info "Boot wait complete"

# Step 3: Generate Ansible inventory
echo ""
log_step "Step 3/6: Generating Ansible inventory..."
./generate-inventory.sh
log_info "Inventory generated"

# Step 4: Test SSH connectivity
echo ""
log_step "Step 4/6: Testing SSH connectivity..."
cd ../ansible

MASTER_IP=$(grep "k8s-master ansible_host" hosts | awk '{print $2}' | cut -d'=' -f2)
WORKER_IP=$(grep "k8s-worker-1 ansible_host" hosts | awk '{print $2}' | cut -d'=' -f2)

echo -e "  Testing master (${BOLD}$MASTER_IP${NC})..."
ssh -i "$SSH_KEY_FILE" -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@$MASTER_IP "echo 'OK'" > /dev/null 2>&1 || {
    log_warn "Master not ready, retrying in 30s..."
    sleep 30
    ssh -i "$SSH_KEY_FILE" -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@$MASTER_IP "echo 'OK'" > /dev/null 2>&1 || {
        log_error "Master is still unreachable via SSH"
        exit 1
    }
}
log_info "Master SSH OK"

echo -e "  Testing worker (${BOLD}$WORKER_IP${NC})..."
ssh -i "$SSH_KEY_FILE" -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@$WORKER_IP "echo 'OK'" > /dev/null 2>&1 || {
    log_warn "Worker not ready, retrying in 30s..."
    sleep 30
    ssh -i "$SSH_KEY_FILE" -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@$WORKER_IP "echo 'OK'" > /dev/null 2>&1 || {
        log_error "Worker is still unreachable via SSH"
        exit 1
    }
}
log_info "Worker SSH OK"

# Step 5: Run Ansible playbook
echo ""
log_step "Step 5/6: Installing Kubernetes with Ansible..."
log_warn "This will take 10-15 minutes..."
echo ""

ansible-playbook -i hosts playbook.yml

log_info "Kubernetes installed successfully"

# Step 6: Get kubeconfig
echo ""
log_step "Step 6/6: Fetching kubeconfig..."
scp -i "$SSH_KEY_FILE" -o StrictHostKeyChecking=no ubuntu@$MASTER_IP:/home/ubuntu/.kube/config ./kubeconfig > /dev/null 2>&1
log_info "Kubeconfig saved to $(pwd)/kubeconfig"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}  ${BOLD}Setup Complete!${NC}                              ${GREEN}║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Cluster Info:${NC}"
echo -e "    Master: ${CYAN}$MASTER_IP${NC}"
echo -e "    Worker: ${CYAN}$WORKER_IP${NC}"
echo ""
echo -e "  ${BOLD}Access cluster:${NC}"
echo -e "    ${YELLOW}export KUBECONFIG=$(pwd)/kubeconfig${NC}"
echo -e "    ${YELLOW}kubectl get nodes${NC}"
echo ""
echo -e "  ${BOLD}SSH to master:${NC}"
echo -e "    ${YELLOW}ssh -i $SSH_KEY_FILE ubuntu@$MASTER_IP${NC}"
echo ""
echo -e "  ${BOLD}Cost management:${NC}"
echo -e "    ${YELLOW}cd ../terraform${NC}"
echo -e "    ${YELLOW}./manage-cluster.sh stop${NC}   # Stop when not using"
echo -e "    ${YELLOW}./manage-cluster.sh start${NC}  # Start when needed"
echo ""
echo -e "  ${RED}⚠  Remember to stop the cluster when not in use to save costs!:)${NC}"
echo ""
