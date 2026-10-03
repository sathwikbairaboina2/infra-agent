package infra_test

pab(overrides) := {
	"address": "aws_s3_bucket_public_access_block.b",
	"type": "aws_s3_bucket_public_access_block",
	"actions": ["create"],
	"after": object.union(
		{
			"block_public_acls": true, "block_public_policy": true,
			"ignore_public_acls": true, "restrict_public_buckets": true,
		},
		overrides,
	),
}

acl(v) := {
	"address": "aws_s3_bucket_acl.b",
	"type": "aws_s3_bucket_acl",
	"actions": ["create"],
	"after": {"acl": v},
}

bucket_policy(principal) := {
	"address": "aws_s3_bucket_policy.b",
	"type": "aws_s3_bucket_policy",
	"actions": ["create"],
	"after": {"policy": json.marshal({"Version": "2012-10-17", "Statement": [{
		"Effect": "Allow", "Principal": principal,
		"Action": "s3:GetObject", "Resource": "arn:aws:s3:::b/*",
	}]})},
}

test_no_public_s3_deny_pab_disabled if {
	"no_public_s3" in denied_rules with input as cs([pab({"block_public_policy": false})])
}

test_no_public_s3_deny_acl_public_read if {
	"no_public_s3" in denied_rules with input as cs([acl("public-read")])
}

test_no_public_s3_deny_policy_principal_star if {
	"no_public_s3" in denied_rules with input as cs([bucket_policy("*")])
}

test_no_public_s3_deny_policy_principal_aws_star if {
	"no_public_s3" in denied_rules with input as cs([bucket_policy({"AWS": "*"})])
}

test_no_public_s3_allow_full_pab if {
	not "no_public_s3" in denied_rules with input as cs([pab({})])
}

test_no_public_s3_allow_private_acl if {
	not "no_public_s3" in denied_rules with input as cs([acl("private")])
}

test_no_public_s3_allow_policy_specific_principal if {
	not "no_public_s3" in denied_rules with input as cs([bucket_policy({"AWS": "arn:aws:iam::000000000000:root"})])
}
