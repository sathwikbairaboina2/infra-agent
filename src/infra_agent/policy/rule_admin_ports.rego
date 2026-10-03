package infra

import data.infra.config

as_list(x) := x if is_array(x)

as_list(x) := [x] if is_string(x)

as_list(x) := [] if x == null

# One entry per (resource, source CIDR) for every ingress shape we understand.
ingress_entries contains e if {
	some c in writes
	c.type == "aws_security_group"
	some ing in c.after.ingress
	some cidr in array.concat(
		as_list(object.get(ing, "cidr_blocks", [])),
		as_list(object.get(ing, "ipv6_cidr_blocks", [])),
	)
	e := {
		"address": c.address, "cidr": cidr,
		"from": object.get(ing, "from_port", null),
		"to": object.get(ing, "to_port", null),
		"proto": object.get(ing, "protocol", null),
	}
}

ingress_entries contains e if {
	some c in writes
	c.type == "aws_security_group_rule"
	c.after.type == "ingress"
	some cidr in array.concat(
		as_list(object.get(c.after, "cidr_blocks", [])),
		as_list(object.get(c.after, "ipv6_cidr_blocks", [])),
	)
	e := {
		"address": c.address, "cidr": cidr,
		"from": object.get(c.after, "from_port", null),
		"to": object.get(c.after, "to_port", null),
		"proto": object.get(c.after, "protocol", null),
	}
}

ingress_entries contains e if {
	some c in writes
	c.type == "aws_vpc_security_group_ingress_rule"
	some cidr in array.concat(
		as_list(object.get(c.after, "cidr_ipv4", null)),
		as_list(object.get(c.after, "cidr_ipv6", null)),
	)
	e := {
		"address": c.address, "cidr": cidr,
		"from": object.get(c.after, "from_port", null),
		"to": object.get(c.after, "to_port", null),
		"proto": object.get(c.after, "ip_protocol", null),
	}
}

deny contains {"rule": "no_public_ingress_admin_ports", "address": e.address, "msg": msg} if {
	some e in ingress_entries
	e.cidr in config.open_cidrs
	e.proto == "-1"
	msg := sprintf("%s allows all protocols and ports", [e.cidr])
}

deny contains {"rule": "no_public_ingress_admin_ports", "address": e.address, "msg": msg} if {
	some e in ingress_entries
	e.cidr in config.open_cidrs
	some p in config.admin_ports
	e.from <= p
	p <= e.to
	msg := sprintf("%s can reach port %d", [e.cidr, p])
}
