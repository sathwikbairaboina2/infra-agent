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

resource "aws_security_group" "web" {
  name = "${var.name_prefix}-web"

  tags = {
    owner       = "platform"
    cost-center = "1234"
  }
}

resource "aws_vpc_security_group_ingress_rule" "rdp" {
  security_group_id = aws_security_group.web.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 3389
  to_port           = 3389
  ip_protocol       = "tcp"

  tags = {
    owner       = "platform"
    cost-center = "1234"
  }
}
