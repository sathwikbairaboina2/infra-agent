"""Golden terraform plans (made with real terraform) pushed through the normalizer and real OPA."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from infra_agent.config import Settings
from infra_agent.normalizer import normalize_terraform
from infra_agent.policy import OpaPolicy
from infra_agent.runner import SubprocessRunner

PLANS = Path(__file__).resolve().parent.parent / "fixtures" / "plans"
INDEX = yaml.safe_load((PLANS / "index.yaml").read_text())
CTX = {"localstack_url": "http://localstack:4566"}


def _load(name: str) -> dict:
    return json.loads((PLANS / f"{name}.json").read_text())


def _cs(name: str) -> dict:
    return normalize_terraform(
        _load(name), plan_sha256="0" * 64, base_commit="b" * 40, patch_sha256="1" * 64
    )


def _decide(name: str) -> dict:
    policy = OpaPolicy(Settings().policy_dir, SubprocessRunner())
    return policy.evaluate(_cs(name), context=CTX)


@pytest.mark.parametrize("name", sorted(INDEX))
def test_seeded_violation_fixtures_denied(name: str):
    expected = INDEX[name]
    decision = _decide(name)
    assert decision["decision"] == expected["decision"], decision
    denied = {v["rule"] for v in decision["deny"]}
    for rule in expected.get("rules", []):
        assert rule in denied, (rule, decision["deny"])
    if expected["decision"] == "allow":
        assert decision["warn"] == []


def test_every_fixture_is_indexed():
    on_disk = {p.stem for p in PLANS.glob("*.json")}
    assert on_disk == set(INDEX)
    configs = {p.name for p in (PLANS.parent / "configs").iterdir() if p.is_dir()}
    assert configs == set(INDEX)


def test_compliant_base_stats():
    assert _cs("compliant_base")["stats"] == {"create": 3, "update": 0, "delete": 0, "replace": 0}


def test_provisioner_in_module_found():
    provs = _cs("provisioner_in_module")["provisioners"]
    assert provs and provs[0]["address"].startswith("module.m.")
    assert provs[0]["type"] == "local-exec"


def test_aliased_provider_shape():
    providers = {p["key"]: p for p in _cs("aliased_provider_real_aws")["providers"]}
    print("provider keys:", sorted(providers))
    aliased = [p for p in providers.values() if p["alias"] == "real"]
    assert len(aliased) == 1
    assert aliased[0]["region"] == "us-west-2"
    assert aliased[0]["endpoints"] == {}
