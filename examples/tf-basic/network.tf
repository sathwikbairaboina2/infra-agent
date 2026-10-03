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
