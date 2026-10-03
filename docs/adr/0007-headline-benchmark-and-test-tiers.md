# ADR-0007: Headline from a seeded corpus run end to end with an always-approve human; three test tiers; CDK deferred

- Status: accepted (2026-10-04)

## Context
The headline "0 of N seeded violations reached apply" is only worth something if (a) the pipeline is real (real Terraform plan, real OPA, real LocalStack), (b) the human is not the thing saving us, and (c) benign changes still get through. A live 27B model takes about 50 s per turn on this machine, so a live LLM run cannot be the CI gate.

## Decision
- `evals/seeded/*.yaml` holds scripted cases: `violation`, `benign` and `approval` (stateful delete). `bench/seeded.py` runs each case through `Service` with a `ScriptedProposer`, the real `TerraformPlanner`, real `OpaPolicy` and a `RecordingRunner`. Then a simulated human **approves every review it sees**, echoing the payload hash. The tamper case changes `plan.bin` before approving.
- "Reached apply" means the `RecordingRunner` saw a `terraform apply` argv for that case. The bench exits 1 if any violation reached apply, if any benign case was not applied, or if any case ended at a stage or rule other than the one it declares.
- The output is `bench/results/seeded-latest.json` and `.md` (with versions, hardware and git commit). The README copies from it.
- The live LLM benchmark (`bench/live.py`, `evals/live.yaml`) is opt-in. It runs once and is reported as measured, with its date and model, or reported as not run.
- Test tiers: default (no network, real `opa` and `git`), `localstack` (needs `INFRA_AGENT_LOCALSTACK_URL`), `live` (needs `INFRA_AGENT_LIVE=1`). The last two skip cleanly with a reason.
- The CDK path stays in v0.2, as the design's milestones said.

## Consequences
- The headline can be reproduced with one command, with no GPU and no token.
- It measures the deterministic gate, not how well the model behaves. The live benchmark covers the model and is labelled as a separate number.

## What I gave up
- A headline about live-LLM safety. A 6-request live run is too small and too slow to be the headline.
- CDK support in v0.1.
