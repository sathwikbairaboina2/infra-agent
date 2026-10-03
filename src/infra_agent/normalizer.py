"""Turn `terraform show -json` plan output into the ChangeSet that policy evaluates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

REPLACE_ACTIONS = (["delete", "create"], ["create", "delete"])


class NormalizeError(Exception):
    """Raised when the plan JSON cannot be trusted (for example an errored plan)."""


def _constant(expr: Any) -> Any:
    if isinstance(expr, Mapping):
        return expr.get("constant_value")
    return None


def _providers(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cfgs = (plan.get("configuration") or {}).get("provider_config") or {}
    for key, cfg in cfgs.items():
        expr = cfg.get("expressions") or {}
        endpoints: dict[str, Any] = {}
        blocks = expr.get("endpoints")
        if isinstance(blocks, list) and blocks:
            endpoints = {svc: _constant(v) for svc, v in blocks[0].items()}
        out.append(
            {
                "key": key,
                "name": cfg.get("name"),
                "alias": cfg.get("alias"),
                "region": _constant(expr.get("region")),
                "endpoints": endpoints,
            }
        )
    return out


def _walk(
    module: Mapping[str, Any],
    prefix: str,
    provisioners: list[dict[str, Any]],
    module_calls: list[dict[str, Any]],
) -> None:
    for r in module.get("resources") or []:
        for p in r.get("provisioners") or []:
            provisioners.append({"address": prefix + r["address"], "type": p["type"]})
    for name, call in (module.get("module_calls") or {}).items():
        addr = f"{prefix}module.{name}"
        module_calls.append({"address": addr, "source": call.get("source", "")})
        _walk(call.get("module") or {}, addr + ".", provisioners, module_calls)


def normalize_terraform(
    plan: Mapping[str, Any], *, plan_sha256: str, base_commit: str, patch_sha256: str
) -> dict[str, Any]:
    if plan.get("errored"):
        raise NormalizeError("terraform reported the plan as errored")
    changes: list[dict[str, Any]] = []
    stats = {"create": 0, "update": 0, "delete": 0, "replace": 0}
    for rc in plan.get("resource_changes") or []:
        ch = rc.get("change") or {}
        actions = list(ch.get("actions") or [])
        if rc.get("mode") == "data" or actions in (["no-op"], ["read"]):
            continue
        replace = actions in REPLACE_ACTIONS
        changes.append(
            {
                "address": rc["address"],
                "type": rc["type"],
                "module_address": rc.get("module_address"),
                "actions": actions,
                "replace": replace,
                "before": ch.get("before"),
                "after": ch.get("after"),
                "after_unknown": ch.get("after_unknown") or {},
            }
        )
        if replace:
            stats["replace"] += 1
        else:
            for a in ("create", "update", "delete"):
                if a in actions:
                    stats[a] += 1
    provisioners: list[dict[str, Any]] = []
    module_calls: list[dict[str, Any]] = []
    root = (plan.get("configuration") or {}).get("root_module") or {}
    _walk(root, "", provisioners, module_calls)
    return {
        "tool": "terraform",
        "plan_sha256": plan_sha256,
        "base_commit": base_commit,
        "patch_sha256": patch_sha256,
        "changes": changes,
        "stats": stats,
        "providers": _providers(plan),
        "provisioners": provisioners,
        "module_calls": module_calls,
    }
