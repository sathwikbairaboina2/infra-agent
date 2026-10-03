"""The only code that can run `terraform apply`, and only on a saved plan that was approved.

Checks, in order: the policy decision allows an apply, the plan was not already applied, a human
approved, the approved hash equals the reviewed hash equals the hash of plan.bin on disk right now,
and the approval has not expired.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from infra_agent.hashing import sha256_file
from infra_agent.runner import terraform_env

if TYPE_CHECKING:
    from infra_agent.graph import Deps, RunState

APPLIABLE = {"allow", "needs_approval"}


def _tail(text: str, n: int = 15) -> str:
    return "\n".join(text.strip().splitlines()[-n:])


def _result(status: str, exit_code: int, message: str) -> dict[str, Any]:
    return {"status": status, "exit_code": exit_code, "message": message}


def run_apply_gate(state: RunState, deps: Deps) -> dict[str, Any]:
    run_id = state["run_id"]
    audit = deps.audit(run_id)
    outcome = (state.get("decision") or {}).get("decision")
    if outcome not in APPLIABLE:
        audit.append("apply_refused_no_decision", decision=outcome)
        return _result("apply_refused", 1, f"policy decision {outcome!r} does not allow apply")

    marker = deps.run_dir(run_id) / "applied.json"
    if marker.exists():
        return _result("applied", 0, "already applied")

    approval = state.get("approval") or {}
    if approval.get("decision") != "approve":
        audit.append("apply_refused_no_decision", decision=outcome, approval=approval)
        return _result("apply_refused", 1, "no approval recorded")

    plan_path = Path(state["plan_path"])
    expected = state["plan_sha256"]
    approved = approval.get("plan_sha256")
    on_disk = sha256_file(plan_path) if plan_path.exists() else None
    if not (approved == expected == on_disk):
        audit.append(
            "apply_refused_hash_mismatch", expected=expected, approved=approved, on_disk=on_disk
        )
        return _result("apply_refused", 5, "plan hash mismatch: refusing to apply")

    reviewed_at = datetime.fromisoformat(state["review"]["reviewed_at"])
    ttl = timedelta(hours=deps.settings.approval_ttl_hours)
    if deps.clock() > reviewed_at + ttl:
        audit.append("apply_refused_expired", reviewed_at=state["review"]["reviewed_at"])
        return _result("apply_refused", 5, "approval expired: review the change again")

    res = deps.runner.run(
        [deps.settings.terraform_bin, "apply", "-input=false", "-no-color", str(plan_path)],
        cwd=Path(state["workdir"]),
        purpose="apply",
        env=terraform_env(deps.settings, name_prefix=state["name_prefix"]),
    )
    if res.returncode != 0:
        tail = _tail(res.stderr or res.stdout)
        audit.append("apply_failed", returncode=res.returncode, stderr_tail=tail)
        return _result("apply_failed", 1, f"terraform apply failed: {tail}")

    marker.write_text(
        json.dumps({"plan_sha256": expected, "at": deps.clock().isoformat()}), encoding="utf-8"
    )
    audit.append("applied", plan_sha256=expected, stdout_tail=_tail(res.stdout))
    return _result("applied", 0, "applied")
