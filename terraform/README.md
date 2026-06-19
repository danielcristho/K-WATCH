# K-WATCH AWS Infrastructure Setup

Setup 2 server AWS untuk K-WATCH project (2-3 minggu testing).

## Estimasi Biaya

```
Server 1 (Master): t3.medium On-Demand = $0.0416/jam
Server 2 (Worker): t3.large On-Demand  = ~$0.0832/jam
Total: ~$0.125/jam = ~$3.00/hari

Biaya 3 minggu (24/7): ~$63
Biaya 3 minggu (8 jam/hari): ~$21
```

## Prerequisites

1. **AWS Account** dengan IAM user (onomi)
2. **AWS CLI** installed
3. **Terraform** installed
4. **SSH Key Pair** di AWS

## Setup Steps

### 1. Configure AWS CLI dengan IAM onomi

```bash
aws configure
# AWS Access Key ID: [onomi access key]
# AWS Secret Access Key: [onomi secret key]
# Default region: ap-southeast-1
# Default output format: json
```

### 2. Create SSH Key Pair (jika belum ada)

```bash
# Via AWS Console
# EC2 > Key Pairs > Create key pair
# Name: k8s-kids-key
# Download k8s-kids-key.pem

# Set permissions
chmod 400 ~/.ssh/k8s-kids-key.pem
```

### 3. Setup Terraform

```bash
cd terraform

# Copy dan edit variables
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars

# Edit:
# key_name = "k8s-kids-key"
# my_ip = "YOUR_IP/32"  # Get from: curl ifconfig.me
```

### 4. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Deploy
terraform apply

# Output akan menampilkan:
# - master_public_ip
# - ssh_command_master
```

### 5. Connect to Servers

```bash
# SSH ke Master
ssh -i ~/.ssh/k8s-kids-key.pem ubuntu@<master_public_ip>

# Get Worker IP dari AWS Console atau:
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=k8s-worker-1" \
  --query 'Reservations[*].Instances[*].[PublicIpAddress]' \
  --output text
```

## Cost Optimization

### Stop Instances saat tidak dipakai

```bash
# Get instance IDs
MASTER_ID=$(terraform output -raw master_instance_id)
WORKER_ID=$(terraform output -raw worker_spot_id)

# Stop instances
aws ec2 stop-instances --instance-ids $MASTER_ID $WORKER_ID

# Start instances
aws ec2 start-instances --instance-ids $MASTER_ID $WORKER_ID

# Check status
aws ec2 describe-instances \
  --instance-ids $MASTER_ID $WORKER_ID \
  --query 'Reservations[*].Instances[*].[InstanceId,State.Name]' \
  --output table
```

### Auto Stop/Start dengan Lambda (Optional)

```bash
# Stop setiap hari jam 6 sore
# Start setiap hari jam 8 pagi
# Hemat ~16 jam/hari = 67% cost reduction!
```

### Set Budget Alert

```bash
# Via AWS Console
# Billing > Budgets > Create budget
# Set: $50/month alert
```

## Cleanup (Setelah selesai)

```bash
cd terraform

# Destroy all resources
terraform destroy

# Confirm dengan: yes
```

## Next Steps

Setelah infrastructure ready:

1. Install Kubernetes dengan Ansible (dari folder `ansible/`)
2. Deploy Cilium + Tetragon
3. Deploy malicious + benign containers
4. Collect data
5. Train model

## Troubleshooting

### SSH Connection Refused

```bash
# Check security group
aws ec2 describe-security-groups \
  --group-names k8s-kids-sg \
  --query 'SecurityGroups[*].IpPermissions'

# Update my_ip di terraform.tfvars
# Run: terraform apply
```

### Budget Exceeded

```bash
# Check current costs
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost

# Stop semua instances
aws ec2 stop-instances --instance-ids $(aws ec2 describe-instances \
  --filters "Name=tag:Project,Values=K-WATCH" \
  --query 'Reservations[*].Instances[*].InstanceId' \
  --output text)
```

## IAM Permissions Required (untuk onomi)

Minimal permissions:
- EC2: Full access
- VPC: Read access
- EIP: Full access
- SecurityGroups: Full access

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:*",
        "elasticloadbalancing:*",
        "cloudwatch:*",
        "autoscaling:*"
      ],
      "Resource": "*"
    }
  ]
}
```
