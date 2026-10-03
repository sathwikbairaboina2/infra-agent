"""Builders for terraform plan JSON and ChangeSets used across the unit tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from infra_agent.normalizer import normalize_terraform

LS = "http://localstack:4566"
SERVICES = ("s3", "ec2", "dynamodb", "iam", "sts", "kms")


def rc(
    address: str,
    type_: str,
    actions: Sequence[str],
    after: Mapping[str, Any] | None = None,
    before: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """One item of plan["resource_changes"]."""
    return {
        "address": address,
        "mode": "managed",
        "type": type_,
        "name": address.rsplit(".", 1)[-1],
        "change": {
            "actions": list(actions),
            "before": dict(before) if before is not None else None,
            "after": dict(after) if after is not None else None,
            "after_unknown": {},
        },
    }


def provider_cfg(
    endpoints: str | Mapping[str, str] | None = LS,
    region: str | None = "us-east-1",
    key: str = "aws",
    alias: str | None = None,
) -> dict[str, Any]:
    """One entry of configuration.provider_config (as terraform renders it)."""
    expr: dict[str, Any] = {}
    if region is not None:
        expr["region"] = {"constant_value": region}
    if endpoints is not None:
        urls = {s: endpoints for s in SERVICES} if isinstance(endpoints, str) else endpoints
        expr["endpoints"] = [{s: {"constant_value": u} for s, u in urls.items()}]
    cfg: dict[str, Any] = {"name": "aws", "full_name": "registry.terraform.io/hashicorp/aws"}
    if alias:
        cfg["alias"] = alias
    cfg["expressions"] = expr
    return cfg


def plan(
    resource_changes: Sequence[Mapping[str, Any]] = (),
    providers: Mapping[str, Any] | None = None,
    resources_cfg: Sequence[Mapping[str, Any]] = (),
    module_calls: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "format_version": "1.2",
        "terraform_version": "1.16.5",
        "resource_changes": list(resource_changes),
        "configuration": {
            "provider_config": dict(providers)
            if providers is not None
            else {"aws": provider_cfg()},
            "root_module": {
                "resources": list(resources_cfg),
                "module_calls": dict(module_calls or {}),
            },
        },
    }


def changeset(**kw: Any) -> dict[str, Any]:
    return normalize_terraform(
        plan(**kw), plan_sha256="0" * 64, base_commit="b" * 40, patch_sha256="1" * 64
    )
