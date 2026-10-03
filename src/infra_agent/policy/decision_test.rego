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

test_decision_needs_approval_only if {
	d := infra.decision with input as cs([table_change(["delete"])])
	d.decision == "needs_approval"
	d.deny == []
	count(d.needs_approval) > 0
}

test_decision_deny_beats_needs_approval if {
	d := infra.decision with input as cs([table_change(["delete"]), sg_inline("0.0.0.0/0", 22, 22, "tcp")])
	d.decision == "deny"
	count(d.needs_approval) > 0
}

test_decision_warn_only_still_allows if {
	d := infra.decision with input as cs([tagged(null)])
	d.decision == "allow"
	count(d.warn) > 0
}
