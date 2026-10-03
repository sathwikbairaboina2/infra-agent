package infra_test

import data.infra

tagged(tags) := {
	"address": "aws_s3_bucket.b",
	"type": "aws_s3_bucket",
	"actions": ["create"],
	"after": {"bucket": "b", "tags": tags},
}

test_tags_required_deny_null_tags if {
	"tags_required" in warn_rules with input as cs([tagged(null)])
}

test_tags_required_deny_missing_cost_center if {
	some v in infra.warn with input as cs([tagged({"owner": "me"})])
	v.rule == "tags_required"
	contains(v.msg, "cost-center")
}

test_tags_required_allow_complete_tags if {
	not "tags_required" in warn_rules with input as cs([tagged({"owner": "me", "cost-center": "1"})])
}

test_tags_required_allow_resource_without_tags_attribute if {
	not "tags_required" in warn_rules with input as cs([{"address": "x.y", "type": "aws_s3_bucket_acl", "actions": ["create"], "after": {"acl": "private"}}])
}
