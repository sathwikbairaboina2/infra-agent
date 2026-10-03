package infra

import data.infra.config

needs_approval contains {"rule": "stateful_delete_or_replace", "address": c.address, "msg": msg} if {
	some c in changes
	c.type in config.stateful_types
	"delete" in c.actions
	msg := sprintf("%s is a stateful resource and would be deleted or replaced", [c.type])
}

needs_approval contains {"rule": "blast_radius", "address": "*", "msg": msg} if {
	count(changes) > config.blast_radius_max
	msg := sprintf("%d changes exceed the limit of %d", [count(changes), config.blast_radius_max])
}

needs_approval contains {"rule": "blast_radius", "address": c.address, "msg": "resource would be deleted"} if {
	some c in changes
	"delete" in c.actions
}
