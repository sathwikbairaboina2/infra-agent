"""Subprocess runner with an argv allowlist. Every git, terraform and opa call goes through it."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from infra_agent.config import Settings

Purpose = Literal["git", "plan", "policy", "apply"]

TF_FORBIDDEN_SUBCOMMANDS = {
    "apply",
    "destroy",
    "import",
    "state",
    "taint",
    "untaint",
    "force-unlock",
    "console",
    "login",
    "logout",
    "workspace",
    "test",
}
TF_PLAN_SUBCOMMANDS = {"init", "plan", "show", "version", "validate", "providers"}
OPA_SUBCOMMANDS = {"eval", "test", "check", "fmt", "version"}
GIT_SUBCOMMANDS = {"init", "add", "commit", "diff", "rev-parse", "config", "status"}


class ForbiddenCommand(Exception):
    """Raised when an argv is not allowed for its purpose."""


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class Runner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        purpose: Purpose,
        env: Mapping[str, str] | None = None,
        timeout: float = 900,
    ) -> CommandResult: ...


def _exe(argv: Sequence[str]) -> str:
    if not argv:
        raise ForbiddenCommand("empty command")
    return Path(argv[0]).name


def _git_subcommand(argv: Sequence[str]) -> str | None:
    i = 1
    while i + 1 < len(argv) and argv[i] == "-c":
        i += 2
    return argv[i] if i < len(argv) else None


def check_argv(argv: Sequence[str], purpose: Purpose) -> None:
    """Raise ForbiddenCommand unless argv is allowed for this purpose."""
    exe = _exe(argv)
    if purpose == "git":
        if exe != "git":
            raise ForbiddenCommand(f"purpose git cannot run {exe}")
        sub = _git_subcommand(argv)
        if sub not in GIT_SUBCOMMANDS:
            raise ForbiddenCommand(f"git subcommand not allowed: {sub}")
    elif purpose == "policy":
        if exe != "opa":
            raise ForbiddenCommand(f"purpose policy cannot run {exe}")
        if len(argv) < 2 or argv[1] not in OPA_SUBCOMMANDS:
            raise ForbiddenCommand(f"opa subcommand not allowed: {argv[1:2]}")
    elif purpose == "plan":
        if exe != "terraform":
            raise ForbiddenCommand(f"purpose plan cannot run {exe}")
        if len(argv) < 2 or argv[1] not in TF_PLAN_SUBCOMMANDS:
            raise ForbiddenCommand(f"terraform subcommand not allowed for plan: {argv[1:2]}")
        for tok in argv[1:]:
            if tok in TF_FORBIDDEN_SUBCOMMANDS or tok.startswith("-destroy"):
                raise ForbiddenCommand(f"forbidden terraform token: {tok}")
    elif purpose == "apply":
        ok = (
            exe == "terraform"
            and len(argv) == 5
            and argv[1] == "apply"
            and argv[2] == "-input=false"
            and argv[3] == "-no-color"
            and str(argv[4]).endswith("plan.bin")
        )
        if not ok:
            raise ForbiddenCommand(
                "apply is only allowed as: terraform apply -input=false -no-color <plan.bin>"
            )
    else:
        raise ForbiddenCommand(f"unknown purpose {purpose}")


def terraform_env(settings: Settings, *, name_prefix: str) -> dict[str, str]:
    """Minimal env for terraform, built from scratch so host AWS credentials never leak in."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "TF_IN_AUTOMATION": "1",
        "CHECKPOINT_DISABLE": "1",
        "TF_VAR_name_prefix": name_prefix,
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_REGION": "us-east-1",
        "AWS_ENDPOINT_URL": settings.localstack_url,
        "AWS_EC2_METADATA_DISABLED": "true",
    }
    if "TF_CLI_CONFIG_FILE" in os.environ:
        env["TF_CLI_CONFIG_FILE"] = os.environ["TF_CLI_CONFIG_FILE"]
    return env


class SubprocessRunner:
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        purpose: Purpose,
        env: Mapping[str, str] | None = None,
        timeout: float = 900,
    ) -> CommandResult:
        check_argv(argv, purpose)
        p = subprocess.run(
            list(argv),
            cwd=cwd,
            env=dict(env) if env is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CommandResult(tuple(argv), p.returncode, p.stdout, p.stderr)


class RecordingRunner:
    """Wraps another runner and remembers every result."""

    def __init__(self, inner: Runner) -> None:
        self.inner = inner
        self.calls: list[CommandResult] = []

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        purpose: Purpose,
        env: Mapping[str, str] | None = None,
        timeout: float = 900,
    ) -> CommandResult:
        res = self.inner.run(argv, cwd=cwd, purpose=purpose, env=env, timeout=timeout)
        self.calls.append(res)
        return res

    def apply_calls(self) -> list[CommandResult]:
        return [c for c in self.calls if len(c.argv) > 1 and c.argv[1] == "apply"]


class FakeRunner:
    """Test double. The argv check still runs, so fakes cannot hide a violation."""

    def __init__(
        self,
        responses: Mapping[str, CommandResult | Callable[[Sequence[str]], CommandResult]]
        | None = None,
    ) -> None:
        self.responses = dict(responses or {})
        self.calls: list[CommandResult] = []

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        purpose: Purpose,
        env: Mapping[str, str] | None = None,
        timeout: float = 900,
    ) -> CommandResult:
        check_argv(argv, purpose)
        sub = argv[1] if len(argv) > 1 else ""
        resp = self.responses.get(sub)
        if resp is None:
            res = CommandResult(tuple(argv), 0, "", "")
        elif callable(resp):
            res = resp(argv)
        else:
            res = CommandResult(tuple(argv), resp.returncode, resp.stdout, resp.stderr)
        self.calls.append(res)
        return res
