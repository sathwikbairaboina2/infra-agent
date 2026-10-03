package infra

import data.infra.config

deny contains {"rule": "no_provisioners", "address": p.address, "msg": sprintf("provisioner %s is not allowed", [p.type])} if {
	some p in input.changeset.provisioners
}

deny contains {"rule": "localstack_endpoints_only", "address": p.key, "msg": msg} if {
	some p in input.changeset.providers
	p.name == "aws"
	some svc in config.endpoint_services
	object.get(p.endpoints, svc, "") != input.context.localstack_url
	msg := sprintf("provider %s endpoint %s must be %s", [p.key, svc, input.context.localstack_url])
}

deny contains {"rule": "local_modules_only", "address": m.address, "msg": msg} if {
	some m in input.changeset.module_calls
	not local_source(m.source)
	msg := sprintf("module source %s must be a local path", [m.source])
}

local_source(src) if startswith(src, "./")

local_source(src) if startswith(src, "../")

deny contains {"rule": "supported_resource_types", "address": c.address, "msg": msg} if {
	some c in writes
	not supported_type(c.type)
	msg := sprintf("%s is not routed to LocalStack in v0.1", [c.type])
}

supported_type(t) if {
	some prefix in config.supported_type_prefixes
	startswith(t, prefix)
}
