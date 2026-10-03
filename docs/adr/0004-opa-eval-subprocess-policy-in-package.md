# ADR-0004: OPA through an `opa eval` subprocess, with the policy bundle shipped inside the package

- Status: accepted (2026-10-04)

## Context
The design ran OPA as a compose server. A server adds a moving part, a port and a readiness wait, and tests would then need the network. We need the same policy behaviour in unit tests, the benchmark and CI. The design also requires that the agent cannot weaken the policy.

## Decision
- The policy lives in `src/infra_agent/policy/` (package data). `OpaPolicy.evaluate` writes the input to a temp file and runs `opa eval --format json -d <policy_dir> -i <input> data.infra.decision` through the `Runner` (purpose `policy`).
- The policy knobs (admin ports, allowed regions, stateful types, blast radius limit, required tags) are Rego constants in `config.rego`. Only environment facts (`localstack_url`) come in through `input.context`.
- `policy_bundle_sha256` is `sha256_tree` over every `.rego` file in the bundle. It is added to every decision and to the `review_ready` audit event. A test checks that it is the same before and after a run.
- It fails closed. A non-zero exit, no result or an unknown decision raises `PolicyError`, and that counts as a refused attempt. It never counts as allow.

## Consequences
- Policy tests (`opa test`) and Python tests use the same files and the same binary (OPA 1.21.1 in the image).
- Each evaluation pays for a process start (about tens of ms). That is small next to `terraform plan`.

## What I gave up
- OPA decision logs and bundle serving.
- Loading policy config from `data.json`. Constants in Rego avoid path ambiguity and are covered by the bundle hash.
