"""The only code that can run `terraform apply`. Implemented in task 17."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from infra_agent.graph import Deps, RunState


def run_apply_gate(state: RunState, deps: Deps) -> dict[str, Any]:
    raise NotImplementedError("apply gate arrives in task 17")
