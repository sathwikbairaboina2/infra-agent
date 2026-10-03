from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

import pytest

from infra_agent.config import Settings
from infra_agent.proposer import ScriptedProposer
from infra_agent.service import Service

pytestmark = pytest.mark.localstack

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / "examples" / "tf-basic"
SCRIPT = ROOT / "examples" / "demo" / "ssh-then-private.yaml"
LS = os.environ.get("INFRA_AGENT_LOCALSTACK_URL", "")


def service(tmp_path: Path) -> tuple[Service, str]:
    prefix = "e" + uuid.uuid4().hex[:8]
    settings = Settings(home=tmp_path / "home", localstack_url=LS, name_prefix=prefix)
    return Service(settings, proposer=ScriptedProposer.from_file(SCRIPT)), prefix


def state_addresses(tmp_path: Path) -> set[str]:
    state = tmp_path / "home" / "state" / "tf-basic.tfstate"
    if not state.exists():
        return set()
    data = json.loads(state.read_text())
    return {
        f"{r['type']}.{r['name']}" for r in data.get("resources", []) if r.get("mode") == "managed"
    }


def test_deny_then_fix_then_approve_applies(tmp_path: Path):
    svc, _ = service(tmp_path)
    with svc:
        out = svc.propose(REPO, "let me SSH into the web servers")
        assert out.exit_code == 2, out.message
        assert out.review["attempt"] == 2
        assert "no_public_ingress_admin_ports" in out.review["refused_attempts"][0]["reasons"][0]
        assert out.review["stats"]["create"] == 4
        done = svc.approve(out.run_id, out.review["plan_sha256"])
        assert done.exit_code == 0, done.message
    assert "aws_vpc_security_group_ingress_rule.ssh" in state_addresses(tmp_path)


def test_stale_plan_bin_refused_on_real_terraform(tmp_path: Path):
    svc, _ = service(tmp_path)
    with svc:
        out = svc.propose(REPO, "let me SSH into the web servers")
        assert out.exit_code == 2, out.message
        plan_bin = Path(out.state["plan_path"])
        plan_bin.write_bytes(plan_bin.read_bytes() + b"tamper")
        done = svc.approve(out.run_id, out.review["plan_sha256"])
        assert done.exit_code == 5
    assert state_addresses(tmp_path) == set()


def test_apply_endpoint_is_localstack(tmp_path: Path):
    svc, _ = service(tmp_path)
    with svc:
        out = svc.propose(REPO, "let me SSH into the web servers")
        assert out.exit_code == 2, out.message
        assert svc.approve(out.run_id, out.review["plan_sha256"]).exit_code == 0
        attempt_dir = Path(out.state["plan_path"]).parent
    plan = json.loads((attempt_dir / "plan.json").read_text())
    for cfg in plan["configuration"]["provider_config"].values():
        endpoints = cfg["expressions"]["endpoints"][0]
        assert {v["constant_value"] for v in endpoints.values()} == {LS}
    override = (attempt_dir / "work" / "zz_infra_agent_override.tf").read_text()
    assert set(re.findall(r"https?://[^\s\"]+", override)) == {LS}
