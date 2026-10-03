# infra-agent v0.1 build ledger

Plan: docs/superpowers/plans/2026-10-04-infra-agent.md
Spec: docs/superpowers/specs/2026-10-04-infra-agent.md
ADRs: docs/adr/0001-0007
Format: one line per finished task: `Task N: complete (tests: <cmd> -> <result>; red seen)`. One `Ruling: <decision> - <why> - <cost>` line per deviation. `FINAL:` when the gates pass.
Gates (Task 25): G1 ruff check, G2 ruff format --check, G3 opa check --strict + opa fmt --list --fail, G4 opa test, G5 policy_coverage 100%, G6 pytest (0 failed), G7 uv build, G8 bench.seeded (0 violations reached apply, all benign applied, 0 mismatches), G9 compose config, G10 runtime image build, G11 secrets scan.

Task 0: complete (planner: spec, 7 ADRs, plan, ledger, handoff committed on main)
Ruling: apply target is localstack/localstack:4.14.0 without a token (verified it starts and applies S3/SG/DynamoDB/IAM) - no LocalStack token on this machine - pinned to a Feb-2026 Community image (ADR-0002)
Ruling: proposer submits whole files and git computes the diff - 27B models write broken hunks - more tokens per proposal (ADR-0001)
Ruling: OPA runs as an `opa eval` subprocess with the policy inside the package, not as a compose server - same binary in tests, bench and CI - no decision logs (ADR-0004)
Ruling: CDK path deferred to v0.2 - design milestones put it there - v0.1 is Terraform only (ADR-0007)
Ruling: added an 11th rule, supported_resource_types, and a minimal terraform env with AWS_ENDPOINT_URL - unconfigured services would otherwise route to real AWS endpoints - restricts v0.1 to s3/ec2-sg/dynamodb/iam/kms
Ruling: port 5310 is held by an unrelated container named infra-agent-proto-ls, which this session did not start - LocalStack uses 127.0.0.1:5312 - none
Ruling: ruff extend-exclude = ["docs"] - ruff 0.16 formats python code blocks inside markdown and flagged the committed plan, failing G2 - docs code samples are not auto-formatted
Task 1: complete (tests: scripts/dev.sh uv run pytest -q -> 2 passed; ruff check+format clean)
Task 2: complete (tests: pytest tests/test_config.py tests/test_hashing.py -> 10 passed; red seen)
Task 3: complete (tests: scripts/dev.sh uv run pytest -q -> 33 passed total)
Task 4: complete (tests: pytest -q -> all passed)
Task 5: complete (tests: pytest -q -> 57 passed total)
Task 6: complete (tests: pytest -q -> 79 passed total; red seen)
