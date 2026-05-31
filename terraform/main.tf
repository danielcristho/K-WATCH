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
    Name    = "k8s-kids-vpc"
    Project = "K-IDS"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "k8s_igw" {
  vpc_id = aws_vpc.k8s_vpc.id

  tags = {
    Name    = "k8s-kids-igw"
    Project = "K-IDS"
  }
}

# Subnet
resource "aws_subnet" "k8s_subnet" {
  vpc_id                  = aws_vpc.k8s_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name    = "k8s-kids-subnet"
    Project = "K-IDS"
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
    Name    = "k8s-kids-rt"
    Project = "K-IDS"
  }
}

# Route Table Association
resource "aws_route_table_association" "k8s_rta" {
  subnet_id      = aws_subnet.k8s_subnet.id
  route_table_id = aws_route_table.k8s_rt.id
}

resource "aws_security_group" "k8s_kids" {
  name        = "k8s-kids-sg"
  description = "Security group for K-IDS cluster"
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
    description = "NodePort"
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
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
    Name    = "k8s-kids-sg"
    Project = "K-IDS"
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
    Project = "K-IDS"
  }
}

resource "aws_instance" "k8s_worker" {
  ami           = "ami-0e2c8caa4b6378d8c" # Ubuntu 22.04 LTS us-east-1
  instance_type = "t3.large"
  key_name      = var.key_name
  subnet_id     = aws_subnet.k8s_subnet.id

  vpc_security_group_ids = [aws_security_group.k8s_kids.id]

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = <<-EOF
              #!/bin/bash
              hostnamectl set-hostname k8s-worker-1
              EOF

  tags = {
    Name    = "k8s-worker-1"
    Role    = "worker"
    Project = "K-IDS"
  }
}

resource "aws_eip" "master_eip" {
  instance = aws_instance.k8s_master.id
  domain   = "vpc"

  tags = {
    Name    = "k8s-master-eip"
    Project = "K-IDS"
  }
}

output "master_instance_id" {
  value = aws_instance.k8s_master.id
}

output "master_public_ip" {
  value = aws_eip.master_eip.public_ip
}

output "master_private_ip" {
  value = aws_instance.k8s_master.private_ip
}

output "worker_spot_id" {
  value = aws_instance.k8s_worker.id
}

output "worker_instance_id" {
  value = aws_instance.k8s_worker.id
}

output "ssh_command_master" {
  value = "ssh -i terraform/daniel_aws.pem ubuntu@${aws_eip.master_eip.public_ip}"
}
