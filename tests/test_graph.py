from __future__ import annotations

from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from infra_agent.graph import build_graph
from infra_agent.policy import OpaPolicy
from infra_agent.runner import CommandResult, FakeRunner
from tests.helpers import (
    DELETE_TABLE_PLAN,
    SAFE_PLAN,
    SSH_PLAN,
    SplitRunner,
    bad_change,
    forbidden_path_change,
    initial_state,
    make_deps,
    ok_change,
    scripted,
)


def run(tmp_path: Path, deps, **state_kw):
    app = build_graph(deps, InMemorySaver())
    cfg = {"configurable": {"thread_id": "t"}, "recursion_limit": 100}
    return app, app.invoke(initial_state(tmp_path, **state_kw), cfg)


def audit_events(deps, run_id="r-test") -> list[str]:
    return [e["event"] for e in deps.audit(run_id).events()]


class CountingPolicy:
    def __init__(self, inner: OpaPolicy) -> None:
        self.inner = inner
        self.calls = 0

    def evaluate(self, changeset, *, context):
        self.calls += 1
        return self.inner.evaluate(changeset, context=context)


def test_apply_gate_only_reachable_through_policy_and_approval(tmp_path: Path):
    deps = make_deps(tmp_path, proposer=scripted(ok_change()), plans=[SAFE_PLAN])
    edges = build_graph(deps, InMemorySaver()).get_graph().edges

    def sources(target: str) -> set[str]:
        return {e.source for e in edges if e.target == target}

    assert sources("apply_gate") == {"approval"}
    assert sources("approval") == {"review"}
    assert sources("review") == {"policy"}
    assert sources("propose") - {"__start__"} <= {"policy", "patch", "plan", "normalize", "propose"}
    assert {e.target for e in edges if e.source == "__start__"} == {"propose"}


def test_allow_path_pauses_with_review_payload(tmp_path: Path):
    deps = make_deps(tmp_path, proposer=scripted(ok_change()), plans=[SAFE_PLAN])
    _, result = run(tmp_path, deps)
    payload = result["__interrupt__"][0].value
    assert payload["decision"] == "allow"
    assert len(payload["plan_sha256"]) == 64
    assert len(payload["policy_bundle_sha256"]) == 64
    assert payload["stats"]["create"] == 1
    assert "dynamodb" in payload["diff"]
    assert audit_events(deps) == ["proposal", "review_ready"]


def test_deny_then_fix_pauses_on_attempt_2(tmp_path: Path):
    proposer = scripted(bad_change(), ok_change())
    deps = make_deps(tmp_path, proposer=proposer, plans=[SSH_PLAN, SAFE_PLAN])
    _, result = run(tmp_path, deps)
    payload = result["__interrupt__"][0].value
    assert payload["attempt"] == 2
    assert len(payload["refused_attempts"]) == 1
    assert "no_public_ingress_admin_ports" in payload["refused_attempts"][0]["reasons"][0]
    assert any("no_public_ingress_admin_ports" in f for f in proposer.seen_feedback[1])
    assert audit_events(deps) == [
        "proposal",
        "attempt_refused",
        "proposal",
        "review_ready",
    ]


def test_max_attempts_exactly_three_policy_evals(tmp_path: Path):
    runner = SplitRunner()
    deps = make_deps(tmp_path, proposer=scripted(bad_change()), plans=[SSH_PLAN], runner=runner)
    counting = CountingPolicy(deps.policy)
    deps.policy = counting
    _, result = run(tmp_path, deps)
    assert counting.calls == 3
    assert result["status"] == "rejected"
    assert result["exit_code"] == 3
    assert "__interrupt__" not in result
    assert runner.apply_calls() == []
    assert audit_events(deps)[-1] == "run_rejected"


def test_patch_refusal_counts_as_attempt(tmp_path: Path):
    deps = make_deps(tmp_path, proposer=scripted(forbidden_path_change()), plans=[SAFE_PLAN])
    _, result = run(tmp_path, deps)
    assert result["status"] == "rejected"
    assert result["attempt"] == 3
    assert deps.planner.calls == 0
    assert result["history"][0]["stage"] == "patch"


def test_needs_approval_pauses(tmp_path: Path):
    deps = make_deps(tmp_path, proposer=scripted(ok_change()), plans=[DELETE_TABLE_PLAN])
    _, result = run(tmp_path, deps)
    payload = result["__interrupt__"][0].value
    assert payload["decision"] == "needs_approval"
    assert "stateful_delete_or_replace" in {v["rule"] for v in payload["needs_approval"]}


def test_policy_error_fails_closed(tmp_path: Path):
    runner = SplitRunner()
    broken = OpaPolicy(
        tmp_path, FakeRunner({"eval": CommandResult(("opa", "eval"), 1, "", "opa exploded")})
    )
    deps = make_deps(
        tmp_path, proposer=scripted(ok_change()), plans=[SAFE_PLAN], runner=runner, policy=broken
    )
    _, result = run(tmp_path, deps)
    assert result["status"] == "rejected"
    assert "__interrupt__" not in result
    assert "policy error" in result["history"][0]["reasons"][0]
