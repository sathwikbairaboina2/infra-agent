from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from infra_agent.config import Settings
from infra_agent.planner import (
    ENDPOINT_SERVICES,
    OVERRIDE_NAME,
    FakePlanner,
    PlanError,
    TerraformPlanner,
    render_override,
)
from infra_agent.runner import CommandResult, FakeRunner
from tests.factories import LS, plan, rc

SETTINGS = Settings(localstack_url=LS)


def _plan_writer(argv: Sequence[str]) -> CommandResult:
    out = next(a for a in argv if a.startswith("-out="))[len("-out=") :]
    Path(out).write_bytes(b"planbytes")
    return CommandResult(tuple(argv), 0, "", "")


def _show(argv: Sequence[str]) -> CommandResult:
    return CommandResult(tuple(argv), 0, json.dumps(plan()), "")


def test_override_names_every_service_and_state_path():
    text = render_override("http://x:4566", Path("/data/state/a.tfstate"))
    for svc in ENDPOINT_SERVICES:
        assert f"{svc}" in text
    assert text.count('"http://x:4566"') == len(ENDPOINT_SERVICES)
    assert 'path = "/data/state/a.tfstate"' in text
    assert 'backend "local"' in text


def test_argv_sequence_and_env(tmp_path: Path):
    runner = FakeRunner({"plan": _plan_writer, "show": _show})
    planner = TerraformPlanner(SETTINGS, runner)
    work = tmp_path / "work"
    work.mkdir()
    res = planner.plan(
        work, state_path=tmp_path / "s" / "x.tfstate", out_dir=tmp_path / "out", name_prefix="pfx"
    )
    assert [c.argv[1] for c in runner.calls] == ["init", "plan", "show"]
    assert (work / OVERRIDE_NAME).exists()
    assert len(res.plan_sha256) == 64
    assert res.plan_json["format_version"] == "1.2"
    assert (tmp_path / "out" / "plan.json").exists()


def test_plan_failure_raises_with_stderr_tail(tmp_path: Path):
    runner = FakeRunner(
        {"plan": CommandResult(("terraform", "plan"), 1, "", "line1\nBOOM happened")}
    )
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(PlanError, match="BOOM happened"):
        TerraformPlanner(SETTINGS, runner).plan(
            work, state_path=tmp_path / "s", out_dir=tmp_path / "o", name_prefix="p"
        )


def test_env_passes_name_prefix(tmp_path: Path):
    seen = {}

    class Spy(FakeRunner):
        def run(self, argv, *, cwd, purpose, env=None, timeout=900):
            seen["env"] = env
            return super().run(argv, cwd=cwd, purpose=purpose, env=env, timeout=timeout)

    runner = Spy({"plan": _plan_writer, "show": _show})
    work = tmp_path / "w"
    work.mkdir()
    TerraformPlanner(SETTINGS, runner).plan(
        work, state_path=tmp_path / "s", out_dir=tmp_path / "o", name_prefix="abc"
    )
    assert seen["env"]["TF_VAR_name_prefix"] == "abc"
    assert seen["env"]["AWS_ENDPOINT_URL"] == LS


def test_fake_planner_cycles_through_plans(tmp_path: Path):
    p1 = plan([rc("a.x", "a", ["create"])])
    p2 = plan([rc("a.y", "a", ["create"])])
    fp = FakePlanner([p1, p2])
    r1 = fp.plan(tmp_path, state_path=tmp_path, out_dir=tmp_path / "1", name_prefix="p")
    r2 = fp.plan(tmp_path, state_path=tmp_path, out_dir=tmp_path / "2", name_prefix="p")
    r3 = fp.plan(tmp_path, state_path=tmp_path, out_dir=tmp_path / "3", name_prefix="p")
    assert r1.plan_json == p1 and r2.plan_json == p2 and r3.plan_json == p2
    assert len({r1.plan_sha256, r2.plan_sha256, r3.plan_sha256}) == 3
