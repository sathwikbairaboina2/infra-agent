# ADR-0006: LangGraph interrupt() with SqliteSaver; the proposer calls Ollama /api/chat through httpx

- Status: accepted (2026-10-04)

## Context
Human-in-the-loop must survive the CLI process exiting between `propose` and `approve`. The proposer needs tool calling with a local model.

## Decision
- `langgraph==1.2.12` and `langgraph-checkpoint-sqlite==3.1.1`. `Service` opens `sqlite3.connect(<home>/checkpoints.sqlite, check_same_thread=False)` and passes `SqliteSaver(conn)` to `build_graph`. `thread_id = run_id`. Prototyped on 2026-10-04: pause in one process, resume in another, and a second resume runs nothing.
- The `approval` node only calls `interrupt(payload)` and validates the resume value. All side effects (writing `review.json`, the audit `review_ready`) happen in the `review` node before it. LangGraph re-runs the interrupted node from the top on resume, so side effects there would run twice.
- The proposer talks to Ollama's native `/api/chat` with `tools`, `"think": false` and `"options": {"temperature": 0}`, using `httpx` (the client is injectable, and tests use `httpx.MockTransport`). There is no LangChain dependency.
- State holds only JSON-serialisable values (str, int, list, dict).

## Consequences
- Runtime dependencies: langgraph, langgraph-checkpoint-sqlite, httpx, pydantic, pyyaml. That is all.
- Moving to a hosted model means writing another `Proposer`. The graph does not change.

## What I gave up
- LangChain's chat model abstraction and its tracing integrations.
- Streaming tokens to the terminal during a proposal.
