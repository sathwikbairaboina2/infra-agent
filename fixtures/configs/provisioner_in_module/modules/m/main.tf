variable "name_prefix" {
  type = string
}

resource "aws_s3_bucket" "b" {
  bucket = "${var.name_prefix}-m"

  tags = {
    owner       = "platform"
    cost-center = "1234"
  }

  provisioner "local-exec" {
    command = "echo hi"
  }
}
