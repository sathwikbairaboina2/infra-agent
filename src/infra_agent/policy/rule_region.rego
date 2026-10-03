package infra

import data.infra.config

deny contains {"rule": "region_allowlist", "address": p.key, "msg": msg} if {
	some p in input.changeset.providers
	is_string(p.region)
	not p.region in config.allowed_regions
	msg := sprintf("provider region %s is not allowed", [p.region])
}

deny contains {"rule": "region_allowlist", "address": c.address, "msg": msg} if {
	some c in writes
	is_string(c.after.region)
	not c.after.region in config.allowed_regions
	msg := sprintf("resource region %s is not allowed", [c.after.region])
}
