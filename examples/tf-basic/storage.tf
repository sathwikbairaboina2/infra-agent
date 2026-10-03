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
