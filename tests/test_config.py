from __future__ import annotations

from pathlib import Path

import pytest

from infra_agent.config import Settings


def test_defaults():
    s = Settings.from_env({})
    assert s.home == Path(".infra-agent")
    assert s.localstack_url == "http://localhost:4566"
    assert s.ollama_url == "http://localhost:11434"
    assert s.model == "qwen3.8:27b"
    assert s.max_attempts == 3
    assert s.max_changed_lines == 200
    assert s.approval_ttl_hours == 24.0
    assert s.name_prefix == "demo"


def test_env_overrides():
    s = Settings.from_env(
        {
            "INFRA_AGENT_HOME": "/data",
            "INFRA_AGENT_LOCALSTACK_URL": "http://ls:4566",
            "OLLAMA_BASE_URL": "http://o:1",
            "INFRA_AGENT_MODEL": "m",
            "INFRA_AGENT_MAX_ATTEMPTS": "5",
            "INFRA_AGENT_MAX_CHANGED_LINES": "50",
            "INFRA_AGENT_APPROVAL_TTL_HOURS": "1.5",
            "INFRA_AGENT_NAME_PREFIX": "x",
        }
    )
    assert s.home == Path("/data")
    assert s.localstack_url == "http://ls:4566"
    assert s.ollama_url == "http://o:1"
    assert s.model == "m"
    assert s.max_attempts == 5
    assert s.max_changed_lines == 50
    assert s.approval_ttl_hours == 1.5
    assert s.name_prefix == "x"


def test_invalid_int_raises_value_error_naming_the_variable():
    with pytest.raises(ValueError, match="INFRA_AGENT_MAX_ATTEMPTS"):
        Settings.from_env({"INFRA_AGENT_MAX_ATTEMPTS": "abc"})


def test_policy_dir_points_into_package():
    assert Settings.from_env({}).policy_dir.name == "policy"
