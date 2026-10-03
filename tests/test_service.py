from __future__ import annotations

from pathlib import Path

from infra_agent.audit import verify_log
from infra_agent.hashing import sha256_tree
from infra_agent.service import Service
from tests.helpers import (
    EXAMPLE_REPO,
    FIXED_NOW,
    SAFE_PLAN,
    SSH_PLAN,
    SplitRunner,
    bad_change,
    make_deps,
    make_settings,
    ok_change,
    scripted,
)


def make_service(tmp_path: Path, proposer, plans) -> tuple[Service, SplitRunner]:
    runner = SplitRunner()
    deps = make_deps(tmp_path, proposer=proposer, plans=plans, runner=runner)
    svc = Service(
        deps.settings,
        proposer=proposer,
        planner=deps.planner,
        runner=runner,
        policy=deps.policy,
        clock=lambda: FIXED_NOW,
    )
    return svc, runner


def events(svc: Service, run_id: str) -> list[str]:
    return [e["event"] for e in svc.deps.audit(run_id).events()]


def paused(svc: Service):
    out = svc.propose(EXAMPLE_REPO, "add a table", run_id="r1")
    assert out.exit_code == 2, out
    return out


def test_propose_then_approve_applies_once(tmp_path: Path):
    svc, runner = make_service(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    out = paused(svc)
    assert svc.review("r1")["plan_sha256"] == out.review["plan_sha256"]
    done = svc.approve("r1", out.review["plan_sha256"])
    assert done.exit_code == 0 and done.status == "applied"
    assert len(runner.apply_calls()) == 1
    assert verify_log(svc.settings.home / "audit" / "r1.jsonl").ok
    assert events(svc, "r1") == ["run_started", "proposal", "review_ready", "approved", "applied"]
    assert svc.review("r1") is None


def test_stale_approval_refused(tmp_path: Path):
    svc, runner = make_service(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    out = paused(svc)
    plan_bin = Path(svc.status("r1").state["plan_path"])
    plan_bin.write_bytes(plan_bin.read_bytes() + b"x")
    done = svc.approve("r1", out.review["plan_sha256"])
    assert done.exit_code == 5
    assert runner.apply_calls() == []
    assert "apply_refused_hash_mismatch" in events(svc, "r1")


def test_wrong_hash_in_approval_refused(tmp_path: Path):
    svc, runner = make_service(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    paused(svc)
    done = svc.approve("r1", "f" * 64)
    assert done.exit_code == 5
    assert runner.apply_calls() == []


def test_malformed_hash_is_rejected_not_applied(tmp_path: Path):
    svc, runner = make_service(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    paused(svc)
    done = svc.approve("r1", "not-a-hash")
    assert done.exit_code == 4
    assert runner.apply_calls() == []


def test_reject_exit_4_no_apply(tmp_path: Path):
    svc, runner = make_service(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    paused(svc)
    done = svc.reject("r1", reason="not now")
    assert done.exit_code == 4 and done.status == "human_rejected"
    assert runner.apply_calls() == []
    assert events(svc, "r1")[-1] == "human_rejected"


def test_second_approve_says_already_applied(tmp_path: Path):
    svc, runner = make_service(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    out = paused(svc)
    sha = out.review["plan_sha256"]
    assert svc.approve("r1", sha).exit_code == 0
    again = svc.approve("r1", sha)
    assert again.exit_code == 0 and again.message == "already applied"
    assert len(runner.apply_calls()) == 1


def test_unknown_run_exit_1(tmp_path: Path):
    svc, _ = make_service(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    assert svc.approve("nope", "a" * 64).exit_code == 1
    assert svc.status("nope").message == "unknown run"
    assert svc.reject("nope").exit_code == 1


def test_policy_bundle_hash_unchanged_by_run(tmp_path: Path):
    svc, _ = make_service(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    before = sha256_tree(svc.settings.policy_dir)
    out = paused(svc)
    assert sha256_tree(svc.settings.policy_dir) == before == out.review["policy_bundle_sha256"]


def test_denied_run_exit_3_never_calls_apply(tmp_path: Path):
    svc, runner = make_service(tmp_path, scripted(bad_change()), [SSH_PLAN])
    out = svc.propose(EXAMPLE_REPO, "open ssh", run_id="r1")
    assert out.exit_code == 3 and out.status == "rejected"
    assert runner.apply_calls() == []
    assert svc.approve("r1", "a" * 64).exit_code == 1


def test_default_run_id_and_state_path(tmp_path: Path):
    svc, _ = make_service(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    out = svc.propose(EXAMPLE_REPO, "add a table")
    assert out.run_id.startswith("r-20261004T120000-")
    assert out.state["state_path"].endswith("/state/tf-basic.tfstate")
    assert make_settings(tmp_path).home == svc.settings.home
