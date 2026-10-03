"""Run service: owns the SQLite checkpointer and drives the graph from the CLI."""

from __future__ import annotations

import re
import secrets
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from infra_agent.audit import utcnow
from infra_agent.config import Settings
from infra_agent.graph import Deps, build_graph
from infra_agent.planner import Planner, TerraformPlanner
from infra_agent.policy import OpaPolicy
from infra_agent.proposer import OllamaProposer, Proposer
from infra_agent.runner import Runner, SubprocessRunner


@dataclass(frozen=True)
class RunOutcome:
    run_id: str
    exit_code: int
    status: str
    message: str
    review: dict | None
    state: dict


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "repo"


class Service:
    def __init__(
        self,
        settings: Settings,
        *,
        proposer: Proposer | None = None,
        planner: Planner | None = None,
        runner: Runner | None = None,
        policy: OpaPolicy | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.settings = settings
        runner = runner or SubprocessRunner()
        self.deps = Deps(
            settings=settings,
            proposer=proposer or OllamaProposer(settings.ollama_url, settings.model),
            planner=planner or TerraformPlanner(settings, runner),
            policy=policy or OpaPolicy(settings.policy_dir, runner, settings.opa_bin),
            runner=runner,
            clock=clock,
        )
        settings.home.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(settings.home / "checkpoints.sqlite", check_same_thread=False)
        self.graph = build_graph(self.deps, SqliteSaver(self._conn))

    def __enter__(self) -> Service:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _config(run_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": run_id}, "recursion_limit": 100}

    def _outcome(self, run_id: str) -> RunOutcome:
        snap = self.graph.get_state(self._config(run_id))
        values = dict(snap.values or {})
        if not values:
            return RunOutcome(run_id, 1, "unknown", "unknown run", None, {})
        if tuple(snap.next) == ("approval",):
            return RunOutcome(
                run_id, 2, "awaiting_approval", "awaiting approval", values.get("review"), values
            )
        return RunOutcome(
            run_id,
            int(values.get("exit_code", 1)),
            str(values.get("status", "unknown")),
            str(values.get("message", "")),
            values.get("review"),
            values,
        )

    def propose(
        self,
        repo: Path,
        request: str,
        *,
        run_id: str | None = None,
        name_prefix: str | None = None,
    ) -> RunOutcome:
        run_id = run_id or "r-{}-{}".format(
            self.deps.clock().strftime("%Y%m%dT%H%M%S"), secrets.token_hex(3)
        )
        repo = repo.resolve()
        state_path = self.settings.home / "state" / f"{slugify(repo.name)}.tfstate"
        self.deps.audit(run_id).append("run_started", request=request, repo=str(repo))
        self.graph.invoke(
            {
                "run_id": run_id,
                "request": request,
                "repo": str(repo),
                "name_prefix": name_prefix or self.settings.name_prefix,
                "state_path": str(state_path.resolve()),
                "attempt": 0,
                "max_attempts": self.settings.max_attempts,
                "feedback": [],
                "refusal": [],
                "history": [],
            },
            self._config(run_id),
        )
        return self._outcome(run_id)

    def _pending(self, run_id: str):
        snap = self.graph.get_state(self._config(run_id))
        return snap, bool(snap.values) and tuple(snap.next) == ("approval",)

    def review(self, run_id: str) -> dict | None:
        snap, paused = self._pending(run_id)
        return snap.values.get("review") if paused else None

    def status(self, run_id: str) -> RunOutcome:
        return self._outcome(run_id)

    def approve(
        self, run_id: str, plan_sha256: str, *, approver: str = "cli", reason: str = ""
    ) -> RunOutcome:
        snap, paused = self._pending(run_id)
        if not snap.values:
            return self._outcome(run_id)
        if not paused:
            if snap.values.get("status") == "applied":
                return RunOutcome(
                    run_id, 0, "applied", "already applied", snap.values.get("review"), snap.values
                )
            return RunOutcome(
                run_id,
                1,
                str(snap.values.get("status", "unknown")),
                "run is not awaiting approval",
                snap.values.get("review"),
                dict(snap.values),
            )
        self.deps.audit(run_id).append("approved", approver=approver, plan_sha256=plan_sha256)
        self.graph.invoke(
            Command(
                resume={
                    "decision": "approve",
                    "plan_sha256": plan_sha256,
                    "approver": approver,
                    "reason": reason,
                    "at": self.deps.clock().isoformat(),
                }
            ),
            self._config(run_id),
        )
        return self._outcome(run_id)

    def reject(self, run_id: str, *, approver: str = "cli", reason: str = "") -> RunOutcome:
        snap, paused = self._pending(run_id)
        if not snap.values:
            return self._outcome(run_id)
        if not paused:
            return RunOutcome(
                run_id,
                1,
                str(snap.values.get("status", "unknown")),
                "run is not awaiting approval",
                snap.values.get("review"),
                dict(snap.values),
            )
        self.graph.invoke(
            Command(
                resume={
                    "decision": "reject",
                    "approver": approver,
                    "reason": reason,
                    "at": self.deps.clock().isoformat(),
                }
            ),
            self._config(run_id),
        )
        return self._outcome(run_id)
