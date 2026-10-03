# ADR-0005: Approval bound to the SHA-256 of plan.bin, re-checked at apply, with expiry and at-most-once apply

- Status: accepted (2026-10-04)

## Context
A human approval only means something if it is tied to the exact artifact that gets applied. A saved Terraform plan holds a snapshot of the configuration, so `terraform apply plan.bin` applies exactly what was reviewed, as long as `plan.bin` itself does not change.

## Decision
- `plan_sha256 = sha256(plan.bin)`. It is recorded in state, in `review.json`, in the interrupt payload and in the `review_ready` audit event.
- `approve` must pass `--plan-sha`. The apply gate refuses (exit 5, audit `apply_refused_hash_mismatch`, no apply) unless `approval.plan_sha256 == state.plan_sha256 == sha256_file(plan.bin)` at that moment.
- The approval expires `approval_ttl_hours` (default 24) after `review_ready`. A later approval gives exit 5 and `apply_refused_expired`.
- The gate refuses unless the decision is `allow` or `needs_approval` (audit `apply_refused_no_decision`, exit 1). This is defence in depth on top of the graph edges.
- At most once: after a successful apply the gate writes `runs/<run_id>/applied.json`. A finished LangGraph thread runs no nodes on a later resume. `Service.approve` on a finished applied run returns exit 0 with "already applied" and does not call terraform.
- The only argv the runner allows for purpose `apply` is `terraform apply -input=false -no-color <path ending in plan.bin>`.

## Consequences
- Editing the plan, re-planning or reusing an old hash cannot be approved by accident. The only way forward is a new `propose`.

## What I gave up
- Two-person approval (the resume schema can grow an `approvers` list later).
- Proof that the reviewer actually read the plan. The review output lists denies, warnings and deletes first to make careless approval harder.
