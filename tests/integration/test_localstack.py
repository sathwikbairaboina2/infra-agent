from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from infra_agent.config import Settings
from infra_agent.normalizer import normalize_terraform
from infra_agent.patching import prepare_workdir
from infra_agent.planner import PlanError, TerraformPlanner
from infra_agent.policy import OpaPolicy
from infra_agent.runner import SubprocessRunner

pytestmark = pytest.mark.localstack

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "tf-basic"


def _settings() -> Settings:
    return Settings(localstack_url=os.environ["INFRA_AGENT_LOCALSTACK_URL"])


def _prepare(tmp_path: Path, extra: dict[str, str] | None = None) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(EXAMPLE, repo)
    for name, content in (extra or {}).items():
        (repo / name).write_text(content)
    work = tmp_path / "work"
    prepare_workdir(repo, work, SubprocessRunner())
    return work


def _plan(tmp_path: Path, work: Path):
    planner = TerraformPlanner(_settings(), SubprocessRunner())
    return planner.plan(
        work,
        state_path=tmp_path / "state" / "t.tfstate",
        out_dir=tmp_path / "out",
        name_prefix="t1x",
    )


def test_plan_tf_basic_against_localstack(tmp_path: Path):
    work = _prepare(tmp_path)
    res = _plan(tmp_path, work)
    assert len(res.plan_sha256) == 64
    cs = normalize_terraform(
        res.plan_json, plan_sha256=res.plan_sha256, base_commit="b" * 40, patch_sha256="1" * 64
    )
    assert cs["stats"]["create"] == 3
    aws = next(p for p in cs["providers"] if p["name"] == "aws")
    assert aws["endpoints"]["s3"] == _settings().localstack_url
    decision = OpaPolicy(_settings().policy_dir, SubprocessRunner()).evaluate(
        cs, context={"localstack_url": _settings().localstack_url}
    )
    assert decision["decision"] == "allow"
    assert decision["warn"] == []


def test_non_allowlisted_provider_fails_init(tmp_path: Path):
    extra = {
        "nullp.tf": (
            "terraform {\n  required_providers {\n"
            '    null = { source = "hashicorp/null" }\n  }\n}\n\n'
            'resource "null_resource" "x" {}\n'
        )
    }
    work = _prepare(tmp_path, extra)
    with pytest.raises(PlanError, match="init"):
        _plan(tmp_path, work)


def test_aws_endpoint_url_env_routes_unconfigured_service(tmp_path: Path):
    extra = {"sqs.tf": 'data "aws_sqs_queues" "all" {}\n'}
    work = _prepare(tmp_path, extra)
    res = _plan(tmp_path, work)
    assert res.plan_json.get("errored") is not True
