from __future__ import annotations

import os
from pathlib import Path

import pytest

from infra_agent.config import Settings
from infra_agent.runner import (
    CommandResult,
    FakeRunner,
    ForbiddenCommand,
    RecordingRunner,
    SubprocessRunner,
    check_argv,
    terraform_env,
)

APPLY = ["terraform", "apply", "-input=false", "-no-color"]


@pytest.mark.parametrize(
    "argv",
    [
        ["terraform", "apply"],
        ["terraform", "plan", "-destroy"],
        ["terraform", "plan", "-destroy=true"],
        ["terraform", "state", "rm", "x"],
        ["terraform", "destroy"],
        ["terraform", "plan", "apply"],
    ],
)
def test_plan_purpose_rejects_apply_and_destroy(argv):
    with pytest.raises(ForbiddenCommand):
        check_argv(argv, "plan")


@pytest.mark.parametrize(
    "argv",
    [
        ["terraform", "init", "-input=false"],
        ["terraform", "plan", "-out=plan.bin"],
        ["terraform", "show", "-json", "plan.bin"],
    ],
)
def test_plan_purpose_allows_init_plan_show(argv):
    check_argv(argv, "plan")


def test_apply_purpose_only_exact_saved_plan_form():
    check_argv([*APPLY, "/x/attempt-1/plan.bin"], "apply")
    for bad in (
        [*APPLY, "-auto-approve", "plan.bin"],
        [*APPLY, "-target=a.b", "plan.bin"],
        [*APPLY, "-var", "x=1", "plan.bin"],
        [*APPLY, "main.tf"],
        [*APPLY],
        ["terraform", "destroy", "-input=false", "-no-color", "plan.bin"],
        [*APPLY, "plan.bin", "extra"],
    ):
        with pytest.raises(ForbiddenCommand):
            check_argv(bad, "apply")


@pytest.mark.parametrize("argv", [["bash", "-c", "id"], ["python", "-c", "1"], []])
def test_unknown_executable_refused(argv):
    for purpose in ("git", "plan", "policy", "apply"):
        with pytest.raises(ForbiddenCommand):
            check_argv(argv, purpose)


def test_policy_purpose_only_opa():
    check_argv(["opa", "eval", "x"], "policy")
    check_argv(["opa", "test", "x"], "policy")
    with pytest.raises(ForbiddenCommand):
        check_argv(["opa", "run", "-s"], "policy")
    with pytest.raises(ForbiddenCommand):
        check_argv(["terraform", "plan"], "policy")


def test_git_purpose_subcommand_allowlist():
    check_argv(["git", "init", "-q"], "git")
    check_argv(["git", "-c", "user.name=a", "-c", "x=y", "commit", "-m", "m"], "git")
    for bad in (["git", "push"], ["git", "remote", "add", "o", "u"], ["git", "-c", "a=b"]):
        with pytest.raises(ForbiddenCommand):
            check_argv(bad, "git")


def test_git_version_flag_refused():
    with pytest.raises(ForbiddenCommand):
        check_argv(["git", "--version"], "git")


def test_terraform_env_has_no_host_aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "prod")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "tok")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "realsecret")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ASIAREALKEY")
    s = Settings(localstack_url="http://ls:4566")
    env = terraform_env(s, name_prefix="abc")
    assert "AWS_PROFILE" not in env
    assert "AWS_SESSION_TOKEN" not in env
    assert env["AWS_ACCESS_KEY_ID"] == "test"
    assert env["AWS_SECRET_ACCESS_KEY"] == "test"
    assert env["AWS_ENDPOINT_URL"] == "http://ls:4566"
    assert env["TF_VAR_name_prefix"] == "abc"
    assert env["TF_IN_AUTOMATION"] == "1"


def test_fake_runner_still_checks_argv(tmp_path: Path):
    r = FakeRunner()
    with pytest.raises(ForbiddenCommand):
        r.run(["terraform", "apply"], cwd=tmp_path, purpose="plan")
    assert r.run(["terraform", "plan"], cwd=tmp_path, purpose="plan").returncode == 0
    assert len(r.calls) == 1


def test_fake_runner_responses(tmp_path: Path):
    r = FakeRunner({"plan": CommandResult(("terraform", "plan"), 1, "", "boom")})
    assert r.run(["terraform", "plan"], cwd=tmp_path, purpose="plan").stderr == "boom"
    r2 = FakeRunner({"plan": lambda argv: CommandResult(tuple(argv), 7, "", "")})
    assert r2.run(["terraform", "plan"], cwd=tmp_path, purpose="plan").returncode == 7


def test_recording_runner_apply_calls(tmp_path: Path):
    rec = RecordingRunner(FakeRunner())
    rec.run(["terraform", "plan"], cwd=tmp_path, purpose="plan")
    rec.run([*APPLY, "plan.bin"], cwd=tmp_path, purpose="apply")
    assert len(rec.calls) == 2
    assert len(rec.apply_calls()) == 1


def test_subprocess_runner_runs_real_git(tmp_path: Path):
    r = SubprocessRunner()
    assert r.run(["git", "init", "-q"], cwd=tmp_path, purpose="git").returncode == 0
    out = r.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=tmp_path, purpose="git")
    assert out.stdout.strip() == "true"
    assert os.path.isdir(tmp_path / ".git")
