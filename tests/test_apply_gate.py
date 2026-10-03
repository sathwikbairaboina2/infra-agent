from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from infra_agent.apply_gate import run_apply_gate
from infra_agent.hashing import sha256_bytes
from infra_agent.runner import CommandResult
from tests.helpers import FIXED_NOW, SAFE_PLAN, SplitRunner, make_deps, ok_change, scripted

PLAN_BYTES = b"saved-plan"
SHA = sha256_bytes(PLAN_BYTES)


def build(tmp_path: Path, *, decision="allow", approval=None, apply_response=None, now=FIXED_NOW):
    runner = SplitRunner(apply_response)
    deps = make_deps(
        tmp_path,
        proposer=scripted(ok_change()),
        plans=[SAFE_PLAN],
        runner=runner,
        clock=lambda: now,
    )
    run_dir = deps.run_dir("r1")
    work = run_dir / "attempt-1" / "work"
    work.mkdir(parents=True)
    plan_path = run_dir / "attempt-1" / "plan.bin"
    plan_path.write_bytes(PLAN_BYTES)
    state = {
        "run_id": "r1",
        "name_prefix": "demo",
        "workdir": str(work),
        "plan_path": str(plan_path),
        "plan_sha256": SHA,
        "decision": {"decision": decision},
        "review": {"reviewed_at": FIXED_NOW.isoformat()},
        "approval": approval
        if approval is not None
        else {"decision": "approve", "plan_sha256": SHA, "approver": "me"},
    }
    return deps, runner, state, plan_path


def events(deps) -> list[str]:
    return [e["event"] for e in deps.audit("r1").events()]


def test_refuses_without_allow_decision(tmp_path: Path):
    deps, runner, state, _ = build(tmp_path, decision="deny")
    out = run_apply_gate(state, deps)
    assert out["exit_code"] == 1
    assert runner.apply_calls() == []
    assert events(deps) == ["apply_refused_no_decision"]


def test_refuses_when_decision_missing(tmp_path: Path):
    deps, runner, state, _ = build(tmp_path)
    state["decision"] = {}
    assert run_apply_gate(state, deps)["exit_code"] == 1
    assert runner.apply_calls() == []


def test_hash_mismatch_on_disk(tmp_path: Path):
    deps, runner, state, plan_path = build(tmp_path)
    plan_path.write_bytes(PLAN_BYTES + b"x")
    out = run_apply_gate(state, deps)
    assert out["exit_code"] == 5
    assert runner.apply_calls() == []
    assert events(deps) == ["apply_refused_hash_mismatch"]
    rec = deps.audit("r1").events()[0]
    assert rec["expected"] == SHA and rec["on_disk"] != SHA


def test_hash_mismatch_in_approval(tmp_path: Path):
    deps, runner, state, _ = build(
        tmp_path, approval={"decision": "approve", "plan_sha256": "f" * 64}
    )
    out = run_apply_gate(state, deps)
    assert out["exit_code"] == 5
    assert runner.apply_calls() == []


def test_missing_plan_file_is_a_mismatch(tmp_path: Path):
    deps, runner, state, plan_path = build(tmp_path)
    plan_path.unlink()
    assert run_apply_gate(state, deps)["exit_code"] == 5
    assert runner.apply_calls() == []


def test_expired_approval(tmp_path: Path):
    deps, runner, state, _ = build(tmp_path, now=FIXED_NOW + timedelta(hours=25))
    out = run_apply_gate(state, deps)
    assert out["exit_code"] == 5
    assert runner.apply_calls() == []
    assert events(deps) == ["apply_refused_expired"]


def test_not_expired_just_inside_ttl(tmp_path: Path):
    deps, runner, state, _ = build(tmp_path, now=FIXED_NOW + timedelta(hours=23))
    assert run_apply_gate(state, deps)["exit_code"] == 0
    assert len(runner.apply_calls()) == 1


def test_marker_makes_it_idempotent(tmp_path: Path):
    deps, runner, state, _ = build(tmp_path)
    first = run_apply_gate(state, deps)
    second = run_apply_gate(state, deps)
    assert first["exit_code"] == 0 and second["exit_code"] == 0
    assert second["message"] == "already applied"
    assert len(runner.apply_calls()) == 1


def test_apply_failure_exit_1(tmp_path: Path):
    def fail(argv):
        return CommandResult(tuple(argv), 1, "", "Error: boom")

    deps, runner, state, _ = build(tmp_path, apply_response=fail)
    out = run_apply_gate(state, deps)
    assert out["exit_code"] == 1 and out["status"] == "apply_failed"
    assert "boom" in out["message"]
    assert events(deps) == ["apply_failed"]
    assert not (deps.run_dir("r1") / "applied.json").exists()


def test_success_writes_marker_and_audit(tmp_path: Path):
    deps, runner, state, plan_path = build(tmp_path)
    out = run_apply_gate(state, deps)
    assert out == {"status": "applied", "exit_code": 0, "message": "applied"}
    assert (deps.run_dir("r1") / "applied.json").exists()
    assert events(deps) == ["applied"]
    argv = runner.apply_calls()[0].argv
    assert argv[1:] == ("apply", "-input=false", "-no-color", str(plan_path))
