package infra

default outcome := "allow"

outcome := "deny" if count(deny) > 0

outcome := "needs_approval" if {
	count(deny) == 0
	count(needs_approval) > 0
}

decision := {
	"decision": outcome,
	"deny": [v | some v in deny],
	"needs_approval": [v | some v in needs_approval],
	"warn": [v | some v in warn],
}

# helpers shared by rules
changes contains c if {
	some c in input.changeset.changes
}

writes contains c if {
	some c in changes
	some a in c.actions
	a in {"create", "update"}
}
