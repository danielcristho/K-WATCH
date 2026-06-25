#!/bin/bash
# Auto stop/start script to save costs when not using the cluster.

set -e

MASTER_ID=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=k8s-master" "Name=instance-state-name,Values=running,stopped" \
    --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || echo "")
WORKER_ID=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=k8s-worker" "Name=instance-state-name,Values=running,stopped" \
    --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || echo "")
WORKER2_ID=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=k8s-worker-2" "Name=instance-state-name,Values=running,stopped" \
    --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || echo "")
SIEM_ID=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=k8s-siem" "Name=instance-state-name,Values=running,stopped" \
    --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || echo "")

ALL_IDS="$MASTER_ID $WORKER_ID $WORKER2_ID $SIEM_ID"

if [ -z "$MASTER_ID" ]; then
    echo "Error: Instance IDs not found. Run terraform apply first."
    exit 1
fi

case "$1" in
    start)
        echo "Starting K-WATCH cluster..."
        aws ec2 start-instances --instance-ids $ALL_IDS
        echo "Waiting for instances to start..."
        aws ec2 wait instance-running --instance-ids $ALL_IDS
        echo "✓ Cluster started!"
        echo ""
        echo "Run after ~2 minutes:"
        echo "  cd .. && ./generate-inventory.sh"
        echo "  just ansible"
        ;;

    stop)
        echo "Stopping K-WATCH cluster..."
        aws ec2 stop-instances --instance-ids $ALL_IDS
        echo "Waiting for instances to stop..."
        aws ec2 wait instance-stopped --instance-ids $ALL_IDS
        echo "✓ Cluster stopped!"
        ;;

    status)
        echo "Checking cluster status..."
        aws ec2 describe-instances \
            --instance-ids $ALL_IDS \
            --query 'Reservations[*].Instances[*].[Tags[?Key==`Name`].Value|[0],InstanceId,State.Name,PublicIpAddress]' \
            --output table
        ;;

    *)
        echo "Usage: $0 {start|stop|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Start all instances"
        echo "  stop    - Stop all instances (save money!)"
        echo "  status  - Check current status"
        exit 1
        ;;
esac
