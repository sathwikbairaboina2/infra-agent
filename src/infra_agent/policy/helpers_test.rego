package infra_test

import data.infra

cs(changes) := {
	"changeset": {"changes": changes, "providers": [], "provisioners": [], "module_calls": []},
	"context": {"localstack_url": "http://localstack:4566"},
}

denied_rules := {v.rule | some v in infra.deny}

approval_rules := {v.rule | some v in infra.needs_approval}

warn_rules := {v.rule | some v in infra.warn}
