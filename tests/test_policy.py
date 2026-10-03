from __future__ import annotations

import json
from pathlib import Path

import pytest

from infra_agent.config import Settings
from infra_agent.policy import OpaPolicy, PolicyError
from infra_agent.runner import CommandResult, FakeRunner, SubprocessRunner
from tests.factories import LS, changeset, rc

POLICY_DIR = Settings().policy_dir
CTX = {"localstack_url": LS}
TAGS = {"owner": "me", "cost-center": "1"}


def real() -> OpaPolicy:
    return OpaPolicy(POLICY_DIR, SubprocessRunner())


def fake(stdout: str, rc_: int = 0, stderr: str = "") -> OpaPolicy:
    runner = FakeRunner({"eval": CommandResult(("opa", "eval"), rc_, stdout, stderr)})
    return OpaPolicy(POLICY_DIR, runner)


def test_compliant_allows():
    cs = changeset(
        resource_changes=[
            rc("aws_dynamodb_table.t", "aws_dynamodb_table", ["create"], after={"tags": TAGS})
        ]
    )
    d = real().evaluate(cs, context=CTX)
    assert d["decision"] == "allow"
    assert d["deny"] == [] and d["warn"] == []
    assert len(d["policy_bundle_sha256"]) == 64


def test_ssh_denied_with_rule_name():
    after = {
        "tags": TAGS,
        "ingress": [
            {
                "cidr_blocks": ["0.0.0.0/0"],
                "ipv6_cidr_blocks": [],
                "from_port": 22,
                "to_port": 22,
                "protocol": "tcp",
            }
        ],
    }
    cs = changeset(
        resource_changes=[rc("aws_security_group.w", "aws_security_group", ["create"], after=after)]
    )
    d = real().evaluate(cs, context=CTX)
    assert d["decision"] == "deny"
    assert {v["rule"] for v in d["deny"]} == {"no_public_ingress_admin_ports"}


def test_table_delete_needs_approval():
    cs = changeset(
        resource_changes=[
            rc("aws_dynamodb_table.t", "aws_dynamodb_table", ["delete"], before={"name": "t"})
        ]
    )
    d = real().evaluate(cs, context=CTX)
    assert d["decision"] == "needs_approval"
    assert "stateful_delete_or_replace" in {v["rule"] for v in d["needs_approval"]}


def test_opa_failure_raises():
    with pytest.raises(PolicyError, match="boom"):
        fake("", rc_=1, stderr="boom").evaluate({}, context=CTX)


def test_empty_result_raises():
    with pytest.raises(PolicyError):
        fake(json.dumps({"result": []})).evaluate({}, context=CTX)
    with pytest.raises(PolicyError):
        fake("{}").evaluate({}, context=CTX)
    with pytest.raises(PolicyError):
        fake("not json").evaluate({}, context=CTX)


def test_unknown_decision_raises():
    out = json.dumps({"result": [{"expressions": [{"value": {"decision": "maybe"}}]}]})
    with pytest.raises(PolicyError, match="maybe"):
        fake(out).evaluate({}, context=CTX)


def test_bundle_hash_stable_across_instances():
    assert real().bundle_sha256 == real().bundle_sha256


def test_temp_input_file_removed(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    real().evaluate(changeset(), context=CTX)
    assert list(tmp_path.glob("opa-input-*")) == []
