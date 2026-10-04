from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_ci_has_both_jobs():
    ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    assert {"checks", "localstack"} <= set(ci["jobs"])


def test_ci_runs_every_gate():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    for needle in (
        "ruff check",
        "ruff format --check",
        "opa check --strict",
        "opa fmt --list --fail",
        "opa test",
        "policy_coverage.py",
        "uv build",
        "bench.seeded",
    ):
        assert needle in text


def test_compose_ports_and_names():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    names = []
    for svc in compose["services"].values():
        for port in svc.get("ports", []):
            host_port = int(str(port).split(":")[-2])
            assert 5310 <= host_port <= 5319, port
        if "container_name" in svc:
            names.append(svc["container_name"])
    assert names and all(n.startswith("infra-agent-") for n in names)
    assert compose["name"] == "infra-agent"
