# ADR-0002: LocalStack Community 4.14.0 as the only apply target, with our own override file instead of tflocal

- Status: accepted (2026-10-04)

## Context
The design assumed a LocalStack Hobby auth token, because images since March 2026 need one. This machine has no token. Planning showed that `localstack/localstack:4.14.0` (build date 2026-02-26, the Community image) starts without a token. Terraform with AWS provider 6.67.0 planned and applied S3, EC2 security groups, DynamoDB with PITR, and IAM against it.

`tflocal` is deprecated (the docs point to `lstk terraform`). It also rewrites provider config in ways we would have to trust blindly.

## Decision
- Pin `localstack/localstack:4.14.0` in `docker-compose.yml`. The container is named `infra-agent-localstack` and the host port is `127.0.0.1:5312`. Inside compose the agent uses `http://localstack:4566`.
- The planner writes `zz_infra_agent_override.tf` into the scratch dir after the patch is committed, so it never shows in the diff. It has a `backend "local"` block whose path is `<home>/state/<repo-slug>.tfstate`, and a `provider "aws"` block with test credentials, the `skip_*` flags, `s3_use_path_style` and `endpoints` for s3, ec2, dynamodb, iam, sts and kms, all set to `Settings.localstack_url`.
- Patches may not create any `override.tf` or `*_override.tf` file (ADR-0003), so the agent cannot override our override.
- `TF_VAR_name_prefix` is set per run, so repeated benchmark runs do not collide on resource names in a long-lived LocalStack.

## Consequences
- No token, no account, and no paid features are needed. CI can run the same LocalStack image as a service.
- We are pinned to an image that will not get new AWS features. That is fine, because we claim policy enforcement, not AWS parity.

## What I gave up
- Newer LocalStack releases and `lstk` integration.
- The design's literal `tflocal plan` and `tflocal apply` commands.
