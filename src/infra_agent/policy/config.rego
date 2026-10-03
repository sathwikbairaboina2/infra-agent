package infra.config

admin_ports := {22, 3389, 5432, 3306}

open_cidrs := {"0.0.0.0/0", "::/0"}

allowed_regions := {"us-east-1"}

endpoint_services := ["s3", "ec2", "dynamodb", "iam", "sts", "kms"]

supported_type_prefixes := [
	"aws_s3_",
	"aws_security_group",
	"aws_vpc_security_group_",
	"aws_dynamodb_",
	"aws_iam_",
	"aws_kms_",
]

stateful_types := {"aws_dynamodb_table", "aws_s3_bucket", "aws_db_instance", "aws_rds_cluster", "aws_kms_key"}

blast_radius_max := 10

required_tags := ["owner", "cost-center"]
