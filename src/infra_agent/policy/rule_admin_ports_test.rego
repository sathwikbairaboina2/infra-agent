package infra_test

import data.infra

sg_inline(cidr, from, to, proto) := {
	"address": "aws_security_group.web",
	"type": "aws_security_group",
	"actions": ["create"],
	"after": {"ingress": [{
		"cidr_blocks": [cidr], "ipv6_cidr_blocks": [],
		"from_port": from, "to_port": to, "protocol": proto,
	}]},
}

test_no_public_ingress_admin_ports_deny_ssh_inline if {
	some v in infra.deny with input as cs([sg_inline("0.0.0.0/0", 22, 22, "tcp")])
	v.rule == "no_public_ingress_admin_ports"
	v.msg == "0.0.0.0/0 can reach port 22"
}

test_no_public_ingress_admin_ports_deny_rdp_rule if {
	"no_public_ingress_admin_ports" in denied_rules with input as cs([{
		"address": "aws_security_group_rule.rdp",
		"type": "aws_security_group_rule",
		"actions": ["create"],
		"after": {
			"type": "ingress", "cidr_blocks": ["0.0.0.0/0"], "ipv6_cidr_blocks": null,
			"from_port": 3389, "to_port": 3389, "protocol": "tcp",
		},
	}])
}

test_no_public_ingress_admin_ports_deny_vpc_rule_ipv6_postgres if {
	"no_public_ingress_admin_ports" in denied_rules with input as cs([{
		"address": "aws_vpc_security_group_ingress_rule.pg",
		"type": "aws_vpc_security_group_ingress_rule",
		"actions": ["create"],
		"after": {"cidr_ipv4": null, "cidr_ipv6": "::/0", "from_port": 5432, "to_port": 5432, "ip_protocol": "tcp"},
	}])
}

test_no_public_ingress_admin_ports_deny_protocol_minus_one if {
	"no_public_ingress_admin_ports" in denied_rules with input as cs([{
		"address": "aws_vpc_security_group_ingress_rule.all",
		"type": "aws_vpc_security_group_ingress_rule",
		"actions": ["create"],
		"after": {"cidr_ipv4": "0.0.0.0/0", "cidr_ipv6": null, "from_port": null, "to_port": null, "ip_protocol": "-1"},
	}])
}

test_no_public_ingress_admin_ports_deny_full_range if {
	"no_public_ingress_admin_ports" in denied_rules with input as cs([sg_inline("0.0.0.0/0", 0, 65535, "tcp")])
}

test_no_public_ingress_admin_ports_allow_https_world if {
	not "no_public_ingress_admin_ports" in denied_rules with input as cs([sg_inline("0.0.0.0/0", 443, 443, "tcp")])
}

test_no_public_ingress_admin_ports_allow_ssh_private if {
	not "no_public_ingress_admin_ports" in denied_rules with input as cs([sg_inline("10.0.0.0/8", 22, 22, "tcp")])
}

test_no_public_ingress_admin_ports_allow_delete if {
	delete_change := object.union(sg_inline("0.0.0.0/0", 22, 22, "tcp"), {"actions": ["delete"]})
	not "no_public_ingress_admin_ports" in denied_rules with input as cs([delete_change])
}
