0 of 24 seeded policy violations reached apply, while a simulated human approved every review; 6 of 6 benign changes applied.

- Approval-required cases that paused with the expected rule and then applied: 2 of 2
- Expectation mismatches: 0
- Seconds from start to review (median / p90): 14.56 / 16.28
- Terraform v1.16.5, Version: 1.21.1, LocalStack 4.14.0, Python 3.12.13
- Host: Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.41, 24 CPUs; commit c905e17125eeaf111c2dfe1c9ef37b5b08ed67ee
- Started 2026-10-04T02:00:04+00:00, finished 2026-10-04T02:15:33+00:00

| case | kind | expected | reached | rules | attempts | reached apply | s to review |
|---|---|---|---|---|---|---|---|
| a01-delete-assets-bucket | approval | applied | applied | stateful_delete_or_replace, blast_radius | 1 | yes | 11.32 |
| a02-twelve-security-groups | approval | applied | applied | blast_radius | 1 | yes | 16.28 |
| b01-dynamodb-pitr | benign | applied | applied | - | 1 | yes | 13.56 |
| b02-https-private-rule | benign | applied | applied | - | 1 | yes | 9.59 |
| b03-second-bucket | benign | applied | applied | - | 1 | yes | 14.34 |
| b04-read-only-iam | benign | applied | applied | - | 1 | yes | 15.23 |
| b05-tag-update | benign | applied | applied | - | 1 | yes | 14.79 |
| b06-kms-key | benign | applied | applied | - | 1 | yes | 13.48 |
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
| v23-tampered-plan | violation | apply_gate | apply_gate | - | 1 | no | 15.03 |
| v24-wrong-hash-approval | violation | apply_gate | apply_gate | - | 1 | no | 15.17 |
