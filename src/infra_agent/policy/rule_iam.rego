package infra

iam_policy_types := {
	"aws_iam_policy",
	"aws_iam_role_policy",
	"aws_iam_user_policy",
	"aws_iam_group_policy",
}

# Statement, Action and Resource may each be one value or a list.
as_array(x) := x if is_array(x)

as_array(x) := [x] if not is_array(x)

policy_doc(c) := json.unmarshal(c.after.policy) if is_string(c.after.policy)

read_only_action(a) if {
	parts := split(a, ":")
	count(parts) == 2
	some prefix in ["Get", "List", "Describe"]
	startswith(parts[1], prefix)
}

allow_statements(c) := [s |
	doc := policy_doc(c)
	some s in as_array(doc.Statement)
	s.Effect == "Allow"
]

deny contains {"rule": "no_wildcard_iam", "address": c.address, "msg": "Allow statement with Action *"} if {
	some c in writes
	c.type in iam_policy_types
	some s in allow_statements(c)
	"*" in as_array(s.Action)
}

deny contains {"rule": "no_wildcard_iam", "address": c.address, "msg": msg} if {
	some c in writes
	c.type in iam_policy_types
	some s in allow_statements(c)
	"*" in as_array(s.Resource)
	some a in as_array(s.Action)
	not read_only_action(a)
	msg := sprintf("action %s is allowed on Resource *", [a])
}
