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

resource "aws_s3_bucket" "eu" {
  bucket = "${var.name_prefix}-eu"
  region = "eu-west-1"

  tags = {
    owner       = "platform"
    cost-center = "1234"
  }
}
