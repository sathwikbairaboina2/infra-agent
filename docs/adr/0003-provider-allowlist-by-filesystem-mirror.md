# ADR-0003: A provider allowlist through an offline filesystem mirror, plus Rego for provisioners, endpoints and modules

- Status: accepted (2026-10-04)

## Context
`terraform plan` is not harmless when an LLM writes the HCL. `data "external"` runs a program at plan time. A `local-exec` provisioner ran `echo hi` at apply time in our prototype. A second `provider "aws"` alias with no endpoints would point at real AWS. A remote module can pull in any code.

## Decision
- **Install time:** the image runs `terraform providers mirror` for `hashicorp/aws` 6.67.0 into `/opt/terraform/mirror`. `TF_CLI_CONFIG_FILE` points to a `terraformrc` that has only a `filesystem_mirror` (no `direct` block) and a `plugin_cache_dir`. That cache is filled during the image build with a throwaway `terraform init`. `init` therefore works offline, and any other provider (`null`, `external`, `local`, `http`) fails at init. The failure goes back to the proposer as a refused attempt.
- **Patch time:** only `.tf` files at most 3 levels deep are allowed. Files named `override.tf` or `*_override.tf` are refused, and so is any file that contains a `provisioner` or `backend` block or a `cloud {` block.
- **Policy time:** the normalizer extracts `provisioners`, `providers` (with endpoints and aliases) and `module_calls` from the plan's `configuration` section, walking into modules too. Rego denies any provisioner (`no_provisioners`), any `aws` provider config whose 6 endpoints are not the LocalStack URL (`localstack_endpoints_only`), and any module source that is not local (`local_modules_only`).

## Consequences
- Plan and apply cannot reach a real AWS endpoint, run an arbitrary program or download a provider. Two independent layers enforce each of these.
- `init` is fast and works offline (about 8 s per run, measured while planning).

## What I gave up
- Using registry or git modules in target repos.
- Any provider other than `hashicorp/aws`. Adding one means rebuilding the image.
