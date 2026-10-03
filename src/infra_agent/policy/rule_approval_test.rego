package infra_test

import data.infra

table_change(actions) := {
	"address": "aws_dynamodb_table.t",
	"type": "aws_dynamodb_table",
	"actions": actions,
	"after": {"name": "t"},
}

queue_change(i) := {
	"address": sprintf("aws_security_group.g%d", [i]),
	"type": "aws_security_group",
	"actions": ["create"],
	"after": {},
}

test_stateful_delete_or_replace_deny_delete if {
	"stateful_delete_or_replace" in approval_rules with input as cs([table_change(["delete"])])
}

test_stateful_delete_or_replace_deny_replace_both_orders if {
	"stateful_delete_or_replace" in approval_rules with input as cs([table_change(["delete", "create"])])
	"stateful_delete_or_replace" in approval_rules with input as cs([table_change(["create", "delete"])])
}

test_stateful_delete_or_replace_allow_create_and_update if {
	not "stateful_delete_or_replace" in approval_rules with input as cs([table_change(["create"]), table_change(["update"])])
}

test_stateful_delete_or_replace_allow_stateless_delete if {
	sg := object.union(queue_change(1), {"actions": ["delete"]})
	not "stateful_delete_or_replace" in approval_rules with input as cs([sg])
}

test_blast_radius_deny_too_many_changes if {
	many := [queue_change(i) | some i in numbers.range(1, 11)]
	some v in infra.needs_approval with input as cs(many)
	v.rule == "blast_radius"
	v.address == "*"
}

test_blast_radius_deny_any_delete if {
	sg := object.union(queue_change(1), {"actions": ["delete"]})
	"blast_radius" in approval_rules with input as cs([sg])
}

test_blast_radius_allow_ten_creates if {
	ten := [queue_change(i) | some i in numbers.range(1, 10)]
	not "blast_radius" in approval_rules with input as cs(ten)
}
