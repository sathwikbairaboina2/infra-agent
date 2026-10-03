from __future__ import annotations

from pathlib import Path

from infra_agent.config import Settings
from infra_agent.runner import SubprocessRunner

POLICY = Settings().policy_dir


def _opa(*args: str):
    return SubprocessRunner().run(["opa", *args], cwd=Path.cwd(), purpose="policy")


def test_opa_tests_pass():
    res = _opa("test", str(POLICY))
    assert res.returncode == 0, res.stdout + res.stderr


def test_opa_check_strict():
    res = _opa("check", "--strict", str(POLICY))
    assert res.returncode == 0, res.stdout + res.stderr


def test_opa_fmt_clean():
    res = _opa("fmt", "--list", "--fail", str(POLICY))
    assert res.returncode == 0, res.stdout + res.stderr
    assert res.stdout.strip() == ""
