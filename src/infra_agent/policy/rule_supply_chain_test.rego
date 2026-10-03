package infra_test

import data.infra

ls := "http://localstack:4566"

full_endpoints := {
	"s3": ls, "ec2": ls, "dynamodb": ls,
	"iam": ls, "sts": ls, "kms": ls,
}

aws_provider := {
	"key": "aws", "name": "aws", "alias": null,
	"region": "us-east-1", "endpoints": full_endpoints,
}

with_providers(providers) := object.union(cs([]), {"changeset": {"providers": providers}})

with_provisioners(ps) := object.union(cs([]), {"changeset": {"provisioners": ps}})

with_modules(ms) := object.union(cs([]), {"changeset": {"module_calls": ms}})

test_no_provisioners_deny_local_exec if {
	"no_provisioners" in denied_rules with input as with_provisioners([{"address": "module.m.aws_s3_bucket.b", "type": "local-exec"}])
}

test_no_provisioners_allow_none if {
	not "no_provisioners" in denied_rules with input as with_provisioners([])
}

test_localstack_endpoints_only_deny_aliased_real_aws if {
	real := {"key": "aws.real", "name": "aws", "alias": "real", "region": "us-west-2", "endpoints": {}}
	"localstack_endpoints_only" in denied_rules with input as with_providers([aws_provider, real])
}

test_localstack_endpoints_only_deny_one_service_missing if {
	partial := object.remove(full_endpoints, ["kms"])
	p := {"key": "aws", "name": "aws", "alias": null, "region": "us-east-1", "endpoints": partial}
	some v in infra.deny with input as with_providers([p])
	v.rule == "localstack_endpoints_only"
	contains(v.msg, "kms")
}

test_localstack_endpoints_only_allow_full_set if {
	not "localstack_endpoints_only" in denied_rules with input as with_providers([aws_provider])
}

test_localstack_endpoints_only_allow_non_aws_provider if {
	other := {"key": "null", "name": "null", "alias": null, "region": null, "endpoints": {}}
	not "localstack_endpoints_only" in denied_rules with input as with_providers([other])
}

test_local_modules_only_deny_registry_source if {
	"local_modules_only" in denied_rules with input as with_modules([{"address": "module.vpc", "source": "terraform-aws-modules/vpc/aws"}])
}

test_local_modules_only_deny_git_source if {
	"local_modules_only" in denied_rules with input as with_modules([{"address": "module.x", "source": "git::https://example.com/x.git"}])
}

test_local_modules_only_allow_relative if {
	not "local_modules_only" in denied_rules with input as with_modules([
		{"address": "module.a", "source": "./modules/a"},
		{"address": "module.b", "source": "../shared/b"},
	])
}

test_supported_resource_types_deny_sqs if {
	"supported_resource_types" in denied_rules with input as cs([{"address": "aws_sqs_queue.q", "type": "aws_sqs_queue", "actions": ["create"], "after": {}}])
}

test_supported_resource_types_allow_listed_types if {
	not "supported_resource_types" in denied_rules with input as cs([
		{"address": "aws_s3_bucket.b", "type": "aws_s3_bucket", "actions": ["create"], "after": {}},
		{"address": "aws_security_group.g", "type": "aws_security_group", "actions": ["update"], "after": {}},
		{"address": "aws_vpc_security_group_ingress_rule.r", "type": "aws_vpc_security_group_ingress_rule", "actions": ["create"], "after": {}},
		{"address": "aws_dynamodb_table.t", "type": "aws_dynamodb_table", "actions": ["create"], "after": {}},
		{"address": "aws_iam_policy.p", "type": "aws_iam_policy", "actions": ["create"], "after": {}},
		{"address": "aws_kms_key.k", "type": "aws_kms_key", "actions": ["create"], "after": {}},
	])
}

test_supported_resource_types_allow_delete_of_other_type if {
	not "supported_resource_types" in denied_rules with input as cs([{"address": "aws_sqs_queue.q", "type": "aws_sqs_queue", "actions": ["delete"], "after": null}])
}
