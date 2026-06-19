#!/bin/bash
# Auto stop/start script to save costs when not using the cluster. Also shows status and cost estimates.

set -e

MASTER_ID=$(terraform output -raw master_instance_id 2>/dev/null || echo "")
WORKER_ID=$(terraform output -raw worker_spot_id 2>/dev/null || echo "")

if [ -z "$MASTER_ID" ] || [ -z "$WORKER_ID" ]; then
    echo "Error: Instance IDs not found. Run terraform apply first."
    exit 1
fi

case "$1" in
    start)
        echo "Starting K-WATCH cluster..."
        aws ec2 start-instances --instance-ids $MASTER_ID $WORKER_ID
        echo "Waiting for instances to start..."
        aws ec2 wait instance-running --instance-ids $MASTER_ID $WORKER_ID
        echo "Cluster started!"
        
        # Get new IPs
        MASTER_IP=$(aws ec2 describe-instances \
            --instance-ids $MASTER_ID \
            --query 'Reservations[0].Instances[0].PublicIpAddress' \
            --output text)
        echo "Master IP: $MASTER_IP"
        ;;
        
    stop)
        echo "Stopping K-WATCH cluster..."
        aws ec2 stop-instances --instance-ids $MASTER_ID $WORKER_ID
        echo "Waiting for instances to stop..."
        aws ec2 wait instance-stopped --instance-ids $MASTER_ID $WORKER_ID
        echo "✓ Cluster stopped!"
        ;;
        
    status)
        echo "Checking cluster status..."
        aws ec2 describe-instances \
            --instance-ids $MASTER_ID $WORKER_ID \
            --query 'Reservations[*].Instances[*].[Tags[?Key==`Name`].Value|[0],InstanceId,State.Name,PublicIpAddress]' \
            --output table
        ;;
        
    cost)
        echo "Estimating current month cost..."
        START_DATE=$(date -u +%Y-%m-01)
        END_DATE=$(date -u +%Y-%m-%d)
        
        aws ce get-cost-and-usage \
            --time-period Start=$START_DATE,End=$END_DATE \
            --granularity MONTHLY \
            --metrics BlendedCost \
            --filter file://<(cat <<EOF
{
  "Tags": {
    "Key": "Project",
    "Values": ["K-WATCH"]
  }
}
EOF
) \
            --query 'ResultsByTime[*].[TimePeriod.Start,Total.BlendedCost.Amount]' \
            --output table
        ;;
        
    *)
        echo "Usage: $0 {start|stop|status|cost}"
        echo ""
        echo "Commands:"
        echo "  start   - Start both instances"
        echo "  stop    - Stop both instances (save money!)"
        echo "  status  - Check current status"
        echo "  cost    - Show current month cost"
        exit 1
        ;;
esac
