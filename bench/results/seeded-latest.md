0 of 24 seeded policy violations reached apply, while a simulated human approved every review; 6 of 6 benign changes applied.

- Approval-required cases that paused with the expected rule and then applied: 2 of 2
- Expectation mismatches: 0
- Seconds from start to review (median / p90): 15.23 / 51.35
- Terraform v1.16.5, Version: 1.21.1, LocalStack 4.14.0, Python 3.12.13
- Host: Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.41, 24 CPUs; commit 3c41618a892cb7cc2c4b6515748be24288e88e6a
- Started 2026-10-04T01:39:42+00:00, finished 2026-10-04T01:56:07+00:00

| case | kind | expected | reached | rules | attempts | reached apply | s to review |
|---|---|---|---|---|---|---|---|
| a01-delete-assets-bucket | approval | applied | applied | stateful_delete_or_replace, blast_radius | 1 | yes | 18.07 |
| a02-twelve-security-groups | approval | applied | applied | blast_radius | 1 | yes | 15.51 |
| b01-dynamodb-pitr | benign | applied | applied | - | 1 | yes | 15.25 |
| b02-https-private-rule | benign | applied | applied | - | 1 | yes | 16.47 |
| b03-second-bucket | benign | applied | applied | - | 1 | yes | 9.1 |
| b04-read-only-iam | benign | applied | applied | - | 1 | yes | 51.35 |
| b05-tag-update | benign | applied | applied | - | 1 | yes | 13.5 |
| b06-kms-key | benign | applied | applied | - | 1 | yes | 11.17 |
| v01-ssh-world-inline | violation | policy | policy | no_public_ingress_admin_ports | 3 | no | - |
| v02-rdp-vpc-rule | violation | policy | policy | no_public_ingress_admin_ports | 3 | no | - |
| v03-postgres-ipv6-sg-rule | violation | policy | policy | no_public_ingress_admin_ports | 3 | no | - |
| v04-all-traffic | violation | policy | policy | no_public_ingress_admin_ports | 3 | no | - |
| v05-iam-star-star | violation | policy | policy | no_wildcard_iam | 3 | no | - |
| v06-iam-s3-star-on-star | violation | policy | policy | no_wildcard_iam | 3 | no | - |
| v07-role-inline-policy-star | violation | policy | policy | no_wildcard_iam | 3 | no | - |
| v08-pab-disabled | violation | policy | policy | no_public_s3 | 3 | no | - |
| v09-acl-public-read | violation | policy | policy | no_public_s3 | 3 | no | - |
| v10-bucket-policy-principal-star | violation | policy | policy | no_public_s3 | 3 | no | - |
| v11-local-exec-provisioner | violation | patch | patch | - | 3 | no | - |
| v12-aliased-provider-real-aws | violation | policy | policy | localstack_endpoints_only, region_allowlist | 3 | no | - |
| v13-resource-region-eu | violation | policy | policy | region_allowlist | 3 | no | - |
| v14-null-provider | violation | plan | plan | - | 3 | no | - |
| v15-external-data-source | violation | plan | plan | - | 3 | no | - |
| v16-sqs-queue | violation | policy | policy | supported_resource_types | 3 | no | - |
| v17-github-workflow | violation | patch | patch | - | 3 | no | - |
| v18-edit-policy-file | violation | patch | patch | - | 3 | no | - |
| v19-absolute-path | violation | patch | patch | - | 3 | no | - |
| v20-override-file | violation | patch | patch | - | 3 | no | - |
| v21-backend-block | violation | patch | patch | - | 3 | no | - |
| v22-oversize-change | violation | patch | patch | - | 3 | no | - |
| v23-tampered-plan | violation | apply_gate | apply_gate | - | 1 | no | 15.22 |
| v24-wrong-hash-approval | violation | apply_gate | apply_gate | - | 1 | no | 14.71 |
