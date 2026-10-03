package infra

public_acls := {"public-read", "public-read-write", "authenticated-read"}

pab_flags := ["block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"]

deny contains {"rule": "no_public_s3", "address": c.address, "msg": msg} if {
	some c in writes
	c.type == "aws_s3_bucket_public_access_block"
	some flag in pab_flags
	c.after[flag] == false
	msg := sprintf("public access block has %s = false", [flag])
}

deny contains {"rule": "no_public_s3", "address": c.address, "msg": msg} if {
	some c in writes
	c.type == "aws_s3_bucket_acl"
	c.after.acl in public_acls
	msg := sprintf("bucket ACL %s is public", [c.after.acl])
}

deny contains {"rule": "no_public_s3", "address": c.address, "msg": "bucket policy allows Principal *"} if {
	some c in writes
	c.type == "aws_s3_bucket_policy"
	doc := json.unmarshal(c.after.policy)
	some s in as_array(doc.Statement)
	s.Effect == "Allow"
	star_principal(s.Principal)
}

star_principal(p) if p == "*"

star_principal(p) if "*" in as_array(p.AWS)
