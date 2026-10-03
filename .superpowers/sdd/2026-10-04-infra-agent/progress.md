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
Task 7: complete (tests: opa test -> PASS: 10/10; pytest -q -> 82 passed). Note: temporary src/infra_agent/policy/stub.rego declares empty needs_approval/warn until Task 10
Ruling: builder helper scripts moved from shared /tmp to the scratchpad - a sibling session overwrote /tmp/c.sh and /tmp/l.sh; commit 76b4df5 carries the wrong subject (feat(adapters)) for the Task 3 runner files and one stray ledger line was written into ../durable-multi-agent (commit 5e1ae68 there) - history rewrite avoided; reported to orchestrator
Task 8: complete (tests: opa test -> PASS: 23/23; opa check --strict clean)
Task 9: complete (tests: opa test -> PASS: 39/39; red seen on one test, fixed object.union deep-merge in the test)
Task 10: complete (tests: opa test -> PASS: 53/53; policy_coverage -> coverage: 11/11 rules (100%); pytest -q -> 84 passed; red seen: regex missed digit in no_public_s3). stub.rego removed
Task 11: complete (tests: pytest -q -> 95 passed total)
Task 12: complete (tests: pytest -q -> 103 passed total)
Task 13: complete (tests: pytest -q -m 'not localstack' -> 108 passed; pytest -q -m localstack -> 3 passed in 105s; AWS_ENDPOINT_URL does route an unconfigured service (sqs data source) to LocalStack)
Task 14: complete (tests: pytest -q tests/test_corpus.py -> 18 passed; all 13 violation fixtures denied by exactly the indexed rules, compliant_base allow with 3 creates; aliased provider key is 'aws.real' with alias 'real' matching the factory, no normalizer change)
Task 15: complete (tests: pytest -q -m 'not localstack' -> 139 passed, 1 skipped (live))
Task 16: complete (tests: pytest -q -m 'not localstack' -> 146 passed, 1 skipped; tests/test_graph.py 7 passed; apply_gate.py is a stub until Task 17)
Task 17: complete (tests: pytest -q tests/test_apply_gate.py tests/test_service.py -> 20 passed)
Task 18: complete (tests: pytest -q tests/test_restart.py -> 2 passed; separate OS processes propose/approve/approve, apply log has 1 line)
Task 19: complete (tests: pytest -q tests/test_cli.py -> 11 passed; infra-agent --help prints in the container)
Task 20: complete (tests: pytest -q tests/integration/test_e2e_localstack.py -> 3 passed in 222s against LocalStack 4.14.0)
