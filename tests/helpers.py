"""Shared builders for graph, service and restart tests."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from infra_agent.config import Settings
from infra_agent.graph import Deps
from infra_agent.planner import FakePlanner
from infra_agent.policy import OpaPolicy
from infra_agent.proposer import ScriptedProposer
from infra_agent.runner import (
    CommandResult,
    FakeRunner,
    Purpose,
    RecordingRunner,
    SubprocessRunner,
)
from tests.factories import LS, plan, provider_cfg, rc

EXAMPLE_REPO = Path(__file__).resolve().parent.parent / "examples" / "tf-basic"
TAGS = {"owner": "platform", "cost-center": "1234"}
FIXED_NOW = datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)

TABLE = rc(
    "aws_dynamodb_table.sessions",
    "aws_dynamodb_table",
    ["create"],
    after={"name": "sessions", "tags": TAGS},
)
SAFE_PLAN = plan([TABLE], providers={"aws": provider_cfg()})
SSH_PLAN = plan(
    [
        rc(
            "aws_security_group.web",
            "aws_security_group",
            ["create"],
            after={
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
            },
        )
    ],
    providers={"aws": provider_cfg()},
)
DELETE_TABLE_PLAN = plan(
    [
        rc(
            "aws_dynamodb_table.sessions",
            "aws_dynamodb_table",
            ["delete"],
            before={"name": "sessions"},
        )
    ],
    providers={"aws": provider_cfg()},
)


def ok_change() -> dict[str, Any]:
    return {
        "summary": "add sessions table",
        "files": [
            {
                "path": "db.tf",
                "content": 'resource "aws_dynamodb_table" "sessions" {\n  name = "sessions"\n}\n',
            }
        ],
    }


def bad_change() -> dict[str, Any]:
    return {
        "summary": "open ssh",
        "files": [{"path": "ssh.tf", "content": "# open ssh to the world\n"}],
    }


def forbidden_path_change() -> dict[str, Any]:
    return {
        "summary": "edit ci",
        "files": [{"path": ".github/workflows/x.yml", "content": "name: x\n"}],
    }


class SplitRunner:
    """Real git and opa. A recorded fake stands in for terraform apply."""

    def __init__(self, apply_response: Callable[[Sequence[str]], CommandResult] | None = None):
        self.real = SubprocessRunner()
        self.apply = RecordingRunner(
            FakeRunner({"apply": apply_response} if apply_response else None)
        )

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        purpose: Purpose,
        env: Mapping[str, str] | None = None,
        timeout: float = 900,
    ) -> CommandResult:
        if purpose == "apply":
            return self.apply.run(argv, cwd=cwd, purpose=purpose, env=env, timeout=timeout)
        return self.real.run(argv, cwd=cwd, purpose=purpose, env=env, timeout=timeout)

    def apply_calls(self) -> list[CommandResult]:
        return self.apply.apply_calls()


def make_settings(tmp_path: Path, **kw: Any) -> Settings:
    return Settings(home=tmp_path / "home", localstack_url=LS, **kw)


def make_deps(
    tmp_path: Path,
    *,
    proposer: Any,
    plans: Sequence[dict[str, Any]],
    runner: SplitRunner | None = None,
    policy: Any = None,
    settings: Settings | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Deps:
    settings = settings or make_settings(tmp_path)
    runner = runner or SplitRunner()
    return Deps(
        settings=settings,
        proposer=proposer,
        planner=FakePlanner(list(plans)),
        policy=policy or OpaPolicy(settings.policy_dir, runner),
        runner=runner,
        clock=clock or (lambda: FIXED_NOW),
    )


def scripted(*attempts: dict[str, Any]) -> ScriptedProposer:
    return ScriptedProposer({"attempts": list(attempts)})


def initial_state(
    tmp_path: Path, run_id: str = "r-test", max_attempts: int = 3, repo: Path = EXAMPLE_REPO
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "request": "add a sessions table",
        "repo": str(repo),
        "name_prefix": "demo",
        "state_path": str(tmp_path / "home" / "state" / "x.tfstate"),
        "attempt": 0,
        "max_attempts": max_attempts,
        "feedback": [],
        "refusal": [],
        "history": [],
    }


def service_factory(tmp_path: Path, proposer: Any, plans: Sequence[dict[str, Any]]):
    """A CLI service factory that builds a fresh Service (new sqlite connection) per call."""
    from infra_agent.service import Service

    runner = SplitRunner()
    deps = make_deps(tmp_path, proposer=proposer, plans=plans, runner=runner)

    def factory(settings: Settings, args: Any) -> Service:
        return Service(
            deps.settings,
            proposer=deps.proposer,
            planner=deps.planner,
            runner=runner,
            policy=deps.policy,
            clock=lambda: FIXED_NOW,
        )

    return factory, runner
