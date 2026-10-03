package infra_test

test_region_allowlist_deny_provider_region if {
	p := {"key": "aws.eu", "name": "aws", "alias": "eu", "region": "eu-west-1", "endpoints": full_endpoints}
	"region_allowlist" in denied_rules with input as with_providers([p])
}

test_region_allowlist_deny_resource_region if {
	"region_allowlist" in denied_rules with input as cs([{"address": "aws_s3_bucket.b", "type": "aws_s3_bucket", "actions": ["create"], "after": {"region": "eu-west-1"}}])
}

test_region_allowlist_allow_us_east_1 if {
	not "region_allowlist" in denied_rules with input as object.union(
		cs([{"address": "aws_s3_bucket.b", "type": "aws_s3_bucket", "actions": ["create"], "after": {"region": "us-east-1"}}]),
		{"changeset": {"providers": [aws_provider]}},
	)
}

test_region_allowlist_allow_unknown_region_value if {
	not "region_allowlist" in denied_rules with input as cs([{"address": "aws_s3_bucket.b", "type": "aws_s3_bucket", "actions": ["create"], "after": {"region": null}}])
}
