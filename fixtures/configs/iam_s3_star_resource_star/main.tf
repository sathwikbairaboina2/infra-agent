terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.67.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

variable "name_prefix" {
  type    = string
  default = "demo"
}

resource "aws_iam_policy" "s3all" {
  name = "${var.name_prefix}-s3all"
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "s3:*", Resource = "*" }]
  })

  tags = {
    owner       = "platform"
    cost-center = "1234"
  }
}
