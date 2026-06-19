terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "us-east-1"
}

variable "key_name" {
  description = "SSH key name"
  type        = string
}

variable "my_ip" {
  description = "Your IP for SSH access"
  type        = string
}

# VPC
resource "aws_vpc" "k8s_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name    = "k8s-kwatch-vpc"
    Project = "K-WATCH"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "k8s_igw" {
  vpc_id = aws_vpc.k8s_vpc.id

  tags = {
    Name    = "k8s-kwatch-igw"
    Project = "K-WATCH"
  }
}

# Subnet
resource "aws_subnet" "k8s_subnet" {
  vpc_id                  = aws_vpc.k8s_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name    = "k8s-kwatch-subnet"
    Project = "K-WATCH"
  }
}

# Route Table
resource "aws_route_table" "k8s_rt" {
  vpc_id = aws_vpc.k8s_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.k8s_igw.id
  }

  tags = {
    Name    = "k8s-kwatch-rt"
    Project = "K-WATCH"
  }
}

# Route Table Association
resource "aws_route_table_association" "k8s_rta" {
  subnet_id      = aws_subnet.k8s_subnet.id
  route_table_id = aws_route_table.k8s_rt.id
}

resource "aws_security_group" "k8s_kids" {
  name        = "k8s-kwatch-sg"
  description = "Security group for K-WATCH cluster"
  vpc_id      = aws_vpc.k8s_vpc.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
  }

  ingress {
    description = "K8s API"
    from_port   = 6443
    to_port     = 6443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Hubble Relay"
    from_port   = 4245
    to_port     = 4245
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Hubble UI"
    from_port   = 12000
    to_port     = 12000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Flask ML API"
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "NodePort"
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "VPC internal"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/16"]
  }

  ingress {
    description = "Internal"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "k8s-kwatch-sg"
    Project = "K-WATCH"
  }
}

# SIEM Security Group
resource "aws_security_group" "siem" {
  name        = "k8s-kwatch-siem-sg"
  description = "Security group for SIEM (Wazuh + ELK)"
  vpc_id      = aws_vpc.k8s_vpc.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
  }

  ingress {
    description = "Wazuh Agent"
    from_port   = 1514
    to_port     = 1515
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  ingress {
    description = "Wazuh API"
    from_port   = 55000
    to_port     = 55000
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
  }

  ingress {
    description = "Wazuh Dashboard"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "NodePort range"
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Elasticsearch"
    from_port   = 9200
    to_port     = 9200
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  ingress {
    description = "Kibana"
    from_port   = 5601
    to_port     = 5601
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Logstash Beats"
    from_port   = 5044
    to_port     = 5044
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  ingress {
    description = "VPC internal"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/16"]
  }

  ingress {
    description = "Internal"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "k8s-kwatch-siem-sg"
    Project = "K-WATCH"
  }
}

resource "aws_instance" "k8s_master" {
  ami           = "ami-0e2c8caa4b6378d8c" # Ubuntu 22.04 LTS us-east-1
  instance_type = "t3.medium"
  key_name      = var.key_name
  subnet_id     = aws_subnet.k8s_subnet.id

  vpc_security_group_ids = [aws_security_group.k8s_kids.id]

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = <<-EOF
              #!/bin/bash
              hostnamectl set-hostname k8s-master
              EOF

  tags = {
    Name    = "k8s-master"
    Role    = "master"
    Project = "K-WATCH"
  }
}

resource "aws_instance" "k8s_worker" {
  ami           = "ami-0e2c8caa4b6378d8c" # Ubuntu 22.04 LTS us-east-1
  instance_type = "t3.medium"             # 2 vCPU, 4GB RAM
  key_name      = var.key_name
  subnet_id     = aws_subnet.k8s_subnet.id

  vpc_security_group_ids = [aws_security_group.k8s_kids.id]

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = <<-EOF
              #!/bin/bash
              hostnamectl set-hostname k8s-worker
              EOF

  tags = {
    Name    = "k8s-worker"
    Role    = "worker"
    Project = "K-WATCH"
  }
}

resource "aws_instance" "k8s_worker2" {
  ami           = "ami-0e2c8caa4b6378d8c" # Ubuntu 22.04 LTS us-east-1
  instance_type = "t3.medium"             # 2 vCPU, 4GB RAM
  key_name      = var.key_name
  subnet_id     = aws_subnet.k8s_subnet.id

  vpc_security_group_ids = [aws_security_group.k8s_kids.id]

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = <<-EOF
              #!/bin/bash
              hostnamectl set-hostname k8s-worker-2
              EOF

  tags = {
    Name    = "k8s-worker-2"
    Role    = "worker"
    Project = "K-WATCH"
  }
}

# SIEM Instance (Wazuh stack)
resource "aws_instance" "siem" {
  ami           = "ami-0e2c8caa4b6378d8c" # Ubuntu 22.04 LTS us-east-1
  instance_type = "t3.large"              # 2 vCPU, 8GB RAM for ELK stack
  key_name      = var.key_name
  subnet_id     = aws_subnet.k8s_subnet.id

  vpc_security_group_ids = [aws_security_group.siem.id]

  root_block_device {
    volume_size = 80
    volume_type = "gp3"
  }

  user_data = <<-EOF
              #!/bin/bash
              hostnamectl set-hostname k8s-siem
              EOF

  tags = {
    Name    = "k8s-siem"
    Role    = "siem"
    Project = "K-WATCH"
  }
}

resource "aws_eip" "master_eip" {
  instance = aws_instance.k8s_master.id
  domain   = "vpc"

  tags = {
    Name    = "k8s-master-eip"
    Project = "K-WATCH"
  }
}

resource "aws_eip" "siem_eip" {
  instance = aws_instance.siem.id
  domain   = "vpc"

  tags = {
    Name    = "k8s-kwatch-siem-eip"
    Project = "K-WATCH"
  }
}

# Outputs
output "master_public_ip" {
  value = aws_eip.master_eip.public_ip
}

output "master_private_ip" {
  value = aws_instance.k8s_master.private_ip
}

output "worker_public_ip" {
  value = aws_instance.k8s_worker.public_ip
}

output "worker_private_ip" {
  value = aws_instance.k8s_worker.private_ip
}

output "worker2_public_ip" {
  value = aws_instance.k8s_worker2.public_ip
}

output "worker2_private_ip" {
  value = aws_instance.k8s_worker2.private_ip
}

output "siem_public_ip" {
  value = aws_eip.siem_eip.public_ip
}

output "siem_private_ip" {
  value = aws_instance.siem.private_ip
}

output "ssh_command_master" {
  value = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${aws_eip.master_eip.public_ip}"
}

output "ssh_command_worker" {
  value = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${aws_instance.k8s_worker.public_ip}"
}

output "ssh_command_worker2" {
  value = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${aws_instance.k8s_worker2.public_ip}"
}

output "ssh_command_siem" {
  value = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${aws_eip.siem_eip.public_ip}"
}

output "wazuh_dashboard_url" {
  value = "https://${aws_eip.siem_eip.public_ip}:443"
}

output "kibana_url" {
  value = "http://${aws_eip.siem_eip.public_ip}:5601"
}
