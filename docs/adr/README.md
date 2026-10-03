# Architecture decision records

| ADR | Decision |
|---|---|
| [0001](0001-llm-proposes-whole-files.md) | The LLM proposes whole files and git computes the diff. Everything after that is deterministic. |
| [0002](0002-localstack-community-4-14-no-tflocal.md) | Apply target is LocalStack Community 4.14.0 (no token). We write our own override file instead of using `tflocal`. |
| [0003](0003-provider-allowlist-by-filesystem-mirror.md) | Provider allowlist through an offline filesystem mirror, plus Rego rules for provisioners, endpoints and modules. |
| [0004](0004-opa-eval-subprocess-policy-in-package.md) | OPA runs as an `opa eval` subprocess. The policy ships inside the package and its hash is recorded. |
| [0005](0005-hash-bound-approval.md) | Approval is bound to the SHA-256 of `plan.bin`, checked again at apply, expires after 24 h, and applies at most once. |
| [0006](0006-langgraph-sqlite-raw-ollama.md) | LangGraph `interrupt()` with SqliteSaver. The proposer calls Ollama `/api/chat` with httpx directly (no LangChain). |
| [0007](0007-headline-benchmark-and-test-tiers.md) | The headline comes from a seeded corpus run end to end with an always-approve human. There are three test tiers, and CDK is deferred. |
