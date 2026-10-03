"""Settings read from the environment."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import infra_agent


def _num(env: Mapping[str, str], name: str, default, cast):
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        return cast(raw)
    except ValueError as e:
        raise ValueError(f"{name} must be a {cast.__name__}, got {raw!r}") from e


@dataclass(frozen=True)
class Settings:
    home: Path = Path(".infra-agent")
    localstack_url: str = "http://localhost:4566"
    ollama_url: str = "http://localhost:11434"
    model: str = "qwen3.8:27b"
    max_attempts: int = 3
    max_changed_lines: int = 200
    approval_ttl_hours: float = 24.0
    name_prefix: str = "demo"
    terraform_bin: str = "terraform"
    opa_bin: str = "opa"
    git_bin: str = "git"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        d = cls()
        return cls(
            home=Path(e.get("INFRA_AGENT_HOME") or d.home),
            localstack_url=e.get("INFRA_AGENT_LOCALSTACK_URL") or d.localstack_url,
            ollama_url=e.get("OLLAMA_BASE_URL") or d.ollama_url,
            model=e.get("INFRA_AGENT_MODEL") or d.model,
            max_attempts=_num(e, "INFRA_AGENT_MAX_ATTEMPTS", d.max_attempts, int),
            max_changed_lines=_num(e, "INFRA_AGENT_MAX_CHANGED_LINES", d.max_changed_lines, int),
            approval_ttl_hours=_num(
                e, "INFRA_AGENT_APPROVAL_TTL_HOURS", d.approval_ttl_hours, float
            ),
            name_prefix=e.get("INFRA_AGENT_NAME_PREFIX") or d.name_prefix,
        )

    @property
    def policy_dir(self) -> Path:
        return Path(infra_agent.__file__).parent / "policy"
