"""The LangGraph pipeline: propose, patch, plan, normalize, policy, review, approval, apply."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, ValidationError, model_validator

from infra_agent.apply_gate import run_apply_gate
from infra_agent.audit import AuditLog, utcnow
from infra_agent.config import Settings
from infra_agent.normalizer import NormalizeError, normalize_terraform
from infra_agent.patching import FileChange, PatchRefused, apply_changes, prepare_workdir
from infra_agent.planner import PlanError, Planner
from infra_agent.policy import OpaPolicy, PolicyError
from infra_agent.proposer import ProposalError, Proposer
from infra_agent.repo_tools import RepoTools
from infra_agent.runner import Runner

HEX64 = re.compile(r"^[0-9a-f]{64}$")


class RunState(TypedDict, total=False):
    run_id: str
    request: str
    repo: str
    name_prefix: str
    state_path: str
    attempt: int
    max_attempts: int
    feedback: list[str]
    refusal: list[str]
    history: list[dict]
    summary: str
    changes: list[dict]
    workdir: str
    base_commit: str
    diff: str
    patch_sha256: str
    plan_path: str
    plan_sha256: str
    changeset: dict
    decision: dict
    review: dict
    approval: dict
    status: str
    exit_code: int
    message: str


@dataclass
class Deps:
    settings: Settings
    proposer: Proposer
    planner: Planner
    policy: OpaPolicy
    runner: Runner
    clock: Callable[[], datetime] = utcnow

    def audit(self, run_id: str) -> AuditLog:
        return AuditLog(self.settings.home / "audit" / f"{run_id}.jsonl", run_id, self.clock)

    def run_dir(self, run_id: str) -> Path:
        return self.settings.home / "runs" / run_id


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]
    plan_sha256: str | None = None
    approver: str = "unknown"
    reason: str = ""
    at: str = ""

    @model_validator(mode="after")
    def _approve_needs_hash(self) -> ApprovalDecision:
        if self.decision == "approve" and not (self.plan_sha256 and HEX64.match(self.plan_sha256)):
            raise ValueError("approve needs a 64 hex plan_sha256")
        return self


def _attempt_dir(deps: Deps, state: RunState) -> Path:
    return deps.run_dir(state["run_id"]) / f"attempt-{state['attempt']}"


def _refuse(deps: Deps, state: RunState, stage: str, reasons: list[str], **extra: Any) -> dict:
    """Record a refused attempt: feedback for the next try, history, audit."""
    deps.audit(state["run_id"]).append(
        "attempt_refused", attempt=state.get("attempt", 0), stage=stage, reasons=reasons
    )
    history = [
        *state.get("history", []),
        {"attempt": state.get("attempt", 0), "stage": stage, "reasons": reasons},
    ]
    return {
        "refusal": reasons,
        "feedback": [*state.get("feedback", []), *reasons],
        "history": history,
        **extra,
    }


def _next_or_retry(nxt: str) -> Callable[[RunState], str]:
    def route(s: RunState) -> str:
        if s.get("refusal"):
            return "propose" if s["attempt"] < s["max_attempts"] else "rejected"
        return nxt

    return route


def _after_approval(s: RunState) -> str:
    return "apply_gate" if s.get("approval", {}).get("decision") == "approve" else "human_rejected"


def build_graph(deps: Deps, checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    def propose(state: RunState) -> dict:
        attempt = state.get("attempt", 0) + 1
        state = {**state, "attempt": attempt}
        try:
            proposal = deps.proposer.propose(
                request=state["request"],
                repo=RepoTools(Path(state["repo"])),
                feedback=state.get("feedback", []),
                attempt=attempt,
            )
        except ProposalError as e:
            return _refuse(deps, state, "propose", [f"proposer failed: {e}"], attempt=attempt)
        deps.audit(state["run_id"]).append(
            "proposal",
            attempt=attempt,
            summary=proposal.summary,
            files=[c.path for c in proposal.changes],
        )
        return {
            "attempt": attempt,
            "refusal": [],
            "summary": proposal.summary,
            "changes": [asdict(c) for c in proposal.changes],
        }

    def patch(state: RunState) -> dict:
        workdir = _attempt_dir(deps, state) / "work"
        try:
            prepare_workdir(Path(state["repo"]), workdir, deps.runner, deps.settings.git_bin)
            res = apply_changes(
                workdir,
                [FileChange.from_dict(c) for c in state["changes"]],
                max_changed_lines=deps.settings.max_changed_lines,
                runner=deps.runner,
                git_bin=deps.settings.git_bin,
            )
        except PatchRefused as e:
            return _refuse(deps, state, "patch", list(e.reasons))
        return {
            "workdir": str(workdir),
            "base_commit": res.base_commit,
            "diff": res.diff,
            "patch_sha256": res.patch_sha256,
        }

    def plan(state: RunState) -> dict:
        out_dir = _attempt_dir(deps, state)
        try:
            res = deps.planner.plan(
                Path(state["workdir"]),
                state_path=Path(state["state_path"]),
                out_dir=out_dir,
                name_prefix=state["name_prefix"],
            )
        except PlanError as e:
            return _refuse(deps, state, "plan", [str(e)])
        return {"plan_path": str(res.plan_path), "plan_sha256": res.plan_sha256}

    def normalize(state: RunState) -> dict:
        plan_json = json.loads((Path(state["plan_path"]).parent / "plan.json").read_text("utf-8"))
        try:
            cs = normalize_terraform(
                plan_json,
                plan_sha256=state["plan_sha256"],
                base_commit=state["base_commit"],
                patch_sha256=state["patch_sha256"],
            )
        except NormalizeError as e:
            return _refuse(deps, state, "normalize", [f"plan could not be normalized: {e}"])
        (_attempt_dir(deps, state) / "changeset.json").write_text(
            json.dumps(cs, indent=1, sort_keys=True), encoding="utf-8"
        )
        return {"changeset": cs}

    def policy(state: RunState) -> dict:
        try:
            decision = deps.policy.evaluate(
                state["changeset"], context={"localstack_url": deps.settings.localstack_url}
            )
        except PolicyError as e:
            return _refuse(deps, state, "policy", [f"policy error: {e}"])
        (_attempt_dir(deps, state) / "decision.json").write_text(
            json.dumps(decision, indent=1, sort_keys=True), encoding="utf-8"
        )
        if decision["decision"] == "deny":
            reasons = [f"{v['rule']}: {v['address']}: {v['msg']}" for v in decision["deny"]]
            return _refuse(deps, state, "policy", reasons, decision=decision)
        return {"decision": decision}

    def review(state: RunState) -> dict:
        d = state["decision"]
        now = deps.clock()
        payload = {
            "run_id": state["run_id"],
            "summary": state.get("summary", ""),
            "attempt": state["attempt"],
            "max_attempts": state["max_attempts"],
            "decision": d["decision"],
            "deny": d["deny"],
            "needs_approval": d["needs_approval"],
            "warn": d["warn"],
            "stats": state["changeset"]["stats"],
            "changes": [
                {"address": c["address"], "actions": c["actions"]}
                for c in state["changeset"]["changes"]
            ],
            "diff": state["diff"],
            "plan_sha256": state["plan_sha256"],
            "patch_sha256": state["patch_sha256"],
            "base_commit": state["base_commit"],
            "policy_bundle_sha256": d["policy_bundle_sha256"],
            "reviewed_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=deps.settings.approval_ttl_hours)).isoformat(),
            "refused_attempts": state.get("history", []),
        }
        deps.run_dir(state["run_id"]).mkdir(parents=True, exist_ok=True)
        (deps.run_dir(state["run_id"]) / "review.json").write_text(
            json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8"
        )
        deps.audit(state["run_id"]).append(
            "review_ready",
            attempt=state["attempt"],
            decision=d["decision"],
            plan_sha256=state["plan_sha256"],
            policy_bundle_sha256=d["policy_bundle_sha256"],
        )
        return {"review": payload, "status": "awaiting_approval", "exit_code": 2}

    def approval(state: RunState) -> dict:
        value = interrupt(state["review"])
        try:
            parsed = ApprovalDecision.model_validate(value)
        except (ValidationError, TypeError):
            return {"approval": {"decision": "reject", "reason": "invalid resume value"}}
        return {"approval": parsed.model_dump()}

    def apply_gate(state: RunState) -> dict:
        return run_apply_gate(state, deps)

    def rejected(state: RunState) -> dict:
        deps.audit(state["run_id"]).append(
            "run_rejected", attempts=state.get("attempt", 0), history=state.get("history", [])
        )
        last = (state.get("history") or [{}])[-1]
        reasons = "; ".join(last.get("reasons", []))
        return {
            "status": "rejected",
            "exit_code": 3,
            "message": f"refused after {state.get('attempt', 0)} attempts: {reasons}",
        }

    def human_rejected(state: RunState) -> dict:
        ap = state.get("approval", {})
        deps.audit(state["run_id"]).append(
            "human_rejected", approver=ap.get("approver", "unknown"), reason=ap.get("reason", "")
        )
        return {"status": "human_rejected", "exit_code": 4, "message": "rejected by a human"}

    g = StateGraph(RunState)
    for name, fn in [
        ("propose", propose),
        ("patch", patch),
        ("plan", plan),
        ("normalize", normalize),
        ("policy", policy),
        ("review", review),
        ("approval", approval),
        ("apply_gate", apply_gate),
        ("rejected", rejected),
        ("human_rejected", human_rejected),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "propose")
    g.add_conditional_edges("propose", _next_or_retry("patch"), ["patch", "propose", "rejected"])
    g.add_conditional_edges("patch", _next_or_retry("plan"), ["plan", "propose", "rejected"])
    g.add_conditional_edges(
        "plan", _next_or_retry("normalize"), ["normalize", "propose", "rejected"]
    )
    g.add_conditional_edges(
        "normalize", _next_or_retry("policy"), ["policy", "propose", "rejected"]
    )
    g.add_conditional_edges("policy", _next_or_retry("review"), ["review", "propose", "rejected"])
    g.add_edge("review", "approval")
    g.add_conditional_edges("approval", _after_approval, ["apply_gate", "human_rejected"])
    g.add_edge("apply_gate", END)
    g.add_edge("rejected", END)
    g.add_edge("human_rejected", END)
    return g.compile(checkpointer=checkpointer)
