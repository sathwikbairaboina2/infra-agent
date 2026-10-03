resource "aws_security_group" "web" {
  name        = "${var.name_prefix}-web"
  description = "Web tier"

  ingress {
    description = "HTTPS from the private network"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }

  tags = {
    owner       = "platform"
    cost-center = "1234"
  }
}
provider "aws" {
  region = "us-east-1"
}
resource "aws_s3_bucket" "assets" {
  bucket = "${var.name_prefix}-assets"

  tags = {
    owner       = "platform"
    cost-center = "1234"
  }
}

resource "aws_s3_bucket_public_access_block" "assets" {
  bucket                  = aws_s3_bucket.assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
variable "name_prefix" {
  type    = string
  default = "demo"
}
terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.67.0"
    }
  }
}
