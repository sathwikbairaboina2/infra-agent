package infra_test

iam_change(type, doc) := {
	"address": sprintf("%s.p", [type]),
	"type": type,
	"actions": ["create"],
	"after": {"policy": json.marshal(doc)},
}

allow_stmt(action, resource) := {"Effect": "Allow", "Action": action, "Resource": resource}

doc_of(stmt) := {"Version": "2012-10-17", "Statement": stmt}

test_no_wildcard_iam_deny_star_star if {
	"no_wildcard_iam" in denied_rules with input as cs([iam_change("aws_iam_policy", doc_of([allow_stmt("*", "*")]))])
}

test_no_wildcard_iam_deny_s3_star_on_star if {
	"no_wildcard_iam" in denied_rules with input as cs([iam_change("aws_iam_policy", doc_of(allow_stmt("s3:*", "*")))])
}

test_no_wildcard_iam_deny_role_policy if {
	"no_wildcard_iam" in denied_rules with input as cs([iam_change("aws_iam_role_policy", doc_of([allow_stmt(["s3:GetObject", "s3:PutObject"], ["*"])]))])
}

test_no_wildcard_iam_allow_read_only_on_star if {
	not "no_wildcard_iam" in denied_rules with input as cs([iam_change("aws_iam_policy", doc_of([allow_stmt("s3:GetObject", "*")]))])
}

test_no_wildcard_iam_allow_scoped_resource if {
	not "no_wildcard_iam" in denied_rules with input as cs([iam_change("aws_iam_policy", doc_of([allow_stmt("s3:*", "arn:aws:s3:::bucket/*")]))])
}

test_no_wildcard_iam_allow_deny_statement_with_star if {
	stmt := {"Effect": "Deny", "Action": "*", "Resource": "*"}
	not "no_wildcard_iam" in denied_rules with input as cs([iam_change("aws_iam_policy", doc_of([stmt]))])
}
