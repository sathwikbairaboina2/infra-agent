from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

import yaml

from infra_agent.config import Settings
from infra_agent.patching import FileChange

ROOT = Path(__file__).resolve().parent.parent
CASES = sorted((ROOT / "evals" / "seeded").glob("*.yaml"))

spec = importlib.util.spec_from_file_location(
    "policy_coverage", ROOT / "scripts" / "policy_coverage.py"
)
assert spec and spec.loader
cov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cov)
RULES = set(cov.find_rules(Settings().policy_dir))


def load() -> list[dict]:
    return [yaml.safe_load(p.read_text(encoding="utf-8")) for p in CASES]


def test_every_case_parses_and_ids_match_file_names():
    for path, case in zip(CASES, load(), strict=True):
        assert case["id"] == path.stem
        assert case["kind"] in {"violation", "benign", "approval"}
        assert case["request"]
        assert case["attempts"] and case["attempts"][0]["files"]


def test_ids_unique_and_counts():
    cases = load()
    assert len({c["id"] for c in cases}) == len(cases)
    assert Counter(c["kind"] for c in cases) == {"violation": 24, "benign": 6, "approval": 2}


def test_violations_declare_stage_and_known_rule():
    for c in load():
        expect = c["expect"]
        assert expect["stage"] in {"patch", "plan", "policy", "apply_gate", "applied", "paused"}
        if c["kind"] == "violation":
            assert expect["stage"] != "applied"
            if expect["stage"] == "policy":
                assert expect["rule"] in RULES, c["id"]
        else:
            assert expect["stage"] == "applied"
        if c["kind"] == "approval":
            assert expect["rule"] in RULES


def test_file_changes_are_well_formed():
    for c in load():
        for attempt in c["attempts"]:
            for f in attempt["files"]:
                FileChange.from_dict(f)


def test_every_violation_rule_is_exercised():
    exercised = {c["expect"].get("rule") for c in load() if c["kind"] == "violation"}
    assert {
        "no_public_ingress_admin_ports",
        "no_wildcard_iam",
        "no_public_s3",
        "localstack_endpoints_only",
        "region_allowlist",
        "supported_resource_types",
    } <= exercised
