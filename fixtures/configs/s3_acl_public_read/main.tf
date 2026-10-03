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

resource "aws_s3_bucket" "assets" {
  bucket = "${var.name_prefix}-assets"

  tags = {
    owner       = "platform"
    cost-center = "1234"
  }
}

resource "aws_s3_bucket_acl" "assets" {
  bucket = aws_s3_bucket.assets.id
  acl    = "public-read"
}
