package infra_test

import data.infra

test_decision_empty_changeset_allows if {
	d := infra.decision with input as cs([])
	d.decision == "allow"
	d.deny == []
	d.needs_approval == []
	d.warn == []
}

test_decision_any_deny_wins if {
	d := infra.decision with input as cs([sg_inline("0.0.0.0/0", 22, 22, "tcp")])
	d.decision == "deny"
	count(d.deny) == 1
}

# TODO(task 10): needs_approval-only, deny-beats-needs_approval and warn-only decision tests.
