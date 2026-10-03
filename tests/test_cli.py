from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from infra_agent.cli import main
from tests.factories import LS
from tests.helpers import (
    EXAMPLE_REPO,
    SAFE_PLAN,
    SSH_PLAN,
    bad_change,
    ok_change,
    scripted,
    service_factory,
)


@pytest.fixture(autouse=True)
def env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("INFRA_AGENT_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("INFRA_AGENT_LOCALSTACK_URL", LS)


def cli(factory, *argv: str) -> tuple[int, str]:
    buf = io.StringIO()
    code = main(list(argv), service_factory=factory, out=buf)
    return code, buf.getvalue()


def propose_args(*extra: str) -> list[str]:
    return ["propose", "--repo", str(EXAMPLE_REPO), *extra, "add a table"]


def test_propose_pause_then_approve_applies(tmp_path: Path):
    factory, runner = service_factory(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    code, text = cli(factory, *propose_args("--json"))
    assert code == 2
    payload = json.loads(text)
    assert payload["exit_code"] == 2 and payload["status"] == "awaiting_approval"
    run_id, sha = payload["run_id"], payload["review"]["plan_sha256"]

    code, text = cli(factory, "review", run_id)
    assert code == 0 and f"approve with: infra-agent approve {run_id} --plan-sha {sha}" in text

    code, text = cli(factory, "review", run_id, "--json")
    assert code == 0 and json.loads(text)["review"]["plan_sha256"] == sha

    code, text = cli(factory, "approve", run_id, "--plan-sha", sha, "--approver", "alice")
    assert code == 0 and "applied" in text
    assert len(runner.apply_calls()) == 1

    code, text = cli(factory, "audit", "verify", run_id)
    assert code == 0 and "audit chain ok" in text

    code, text = cli(factory, "approve", run_id, "--plan-sha", sha)
    assert code == 0 and "already applied" in text


def test_denied_exit_3_lists_attempts(tmp_path: Path):
    factory, runner = service_factory(tmp_path, scripted(bad_change()), [SSH_PLAN])
    code, text = cli(factory, *propose_args())
    assert code == 3
    assert text.count(" policy  no_public_ingress_admin_ports") == 3
    assert runner.apply_calls() == []


def test_review_output_lists_refusals_before_the_diff(tmp_path: Path):
    factory, _ = service_factory(
        tmp_path, scripted(bad_change(), ok_change()), [SSH_PLAN, SAFE_PLAN]
    )
    code, text = cli(factory, *propose_args())
    assert code == 2
    assert text.startswith("run r-")
    assert "attempt 2/3 · decision: ALLOW" in text.splitlines()[0]
    assert text.index("refused attempts:") < text.index("diff --git")
    assert "#1 policy  no_public_ingress_admin_ports" in text
    assert "changes: +1 ~0 -0 ±0" in text


def test_reject_exit_4(tmp_path: Path):
    factory, runner = service_factory(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    _, text = cli(factory, *propose_args("--json"))
    run_id = json.loads(text)["run_id"]
    code, _ = cli(factory, "reject", run_id, "--reason", "no")
    assert code == 4
    assert runner.apply_calls() == []


def test_stale_plan_exit_5(tmp_path: Path):
    factory, runner = service_factory(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    _, text = cli(factory, *propose_args("--json"))
    payload = json.loads(text)
    plan_bin = next((tmp_path / "home" / "runs").rglob("plan.bin"))
    plan_bin.write_bytes(plan_bin.read_bytes() + b"!")
    code, _ = cli(
        factory, "approve", payload["run_id"], "--plan-sha", payload["review"]["plan_sha256"]
    )
    assert code == 5
    assert runner.apply_calls() == []


def test_status_of_unknown_run_is_1(tmp_path: Path):
    factory, _ = service_factory(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    code, text = cli(factory, "status", "nope")
    assert code == 1 and "unknown run" in text
    assert cli(factory, "review", "nope")[0] == 1


def test_audit_verify_tampered_log_names_the_seq(tmp_path: Path):
    factory, _ = service_factory(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    _, text = cli(factory, *propose_args("--json"))
    run_id = json.loads(text)["run_id"]
    log = tmp_path / "home" / "audit" / f"{run_id}.jsonl"
    lines = log.read_text().splitlines()
    rec = json.loads(lines[1])
    rec["summary"] = "tampered"
    lines[1] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    log.write_text("\n".join(lines) + "\n")
    code, text = cli(factory, "audit", "verify", run_id)
    assert code == 1 and "first bad seq: 2" in text


def test_scripted_proposer_without_script_is_exit_1(capsys):
    code = main(["propose", "--repo", str(EXAMPLE_REPO), "--proposer", "scripted", "x"])
    assert code == 1
    assert "--script" in capsys.readouterr().err


def test_usage_error_exits_1_not_2(capsys):
    with pytest.raises(SystemExit) as e:
        main(["approve"])
    assert e.value.code == 1


def test_help_documents_exit_codes(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0
    text = capsys.readouterr().out
    assert "paused, awaiting approval" in text and "plan hash mismatch" in text


def test_policy_test_runs_opa(tmp_path: Path):
    factory, _ = service_factory(tmp_path, scripted(ok_change()), [SAFE_PLAN])
    code, text = cli(factory, "policy", "test")
    assert code == 0 and "PASS:" in text
