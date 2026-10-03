package infra

import data.infra.config

warn contains {"rule": "tags_required", "address": c.address, "msg": "tags are not set"} if {
	some c in writes
	"tags" in object.keys(c.after)
	c.after.tags == null
}

warn contains {"rule": "tags_required", "address": c.address, "msg": msg} if {
	some c in writes
	"tags" in object.keys(c.after)
	is_object(c.after.tags)
	some t in config.required_tags
	not t in object.keys(c.after.tags)
	msg := sprintf("missing required tag %s", [t])
}
