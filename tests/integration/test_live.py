from __future__ import annotations

import os
from pathlib import Path

import pytest

from infra_agent.config import Settings
from infra_agent.proposer import OllamaProposer
from infra_agent.repo_tools import RepoTools

pytestmark = pytest.mark.live

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "tf-basic"


def test_live_model_returns_a_tf_change():
    settings = Settings.from_env()
    proposer = OllamaProposer(
        settings.ollama_url, os.environ.get("INFRA_AGENT_MODEL", settings.model)
    )
    proposal = proposer.propose(
        request="add a DynamoDB table named sessions with point-in-time recovery on",
        repo=RepoTools(EXAMPLE),
        feedback=[],
        attempt=1,
    )
    assert proposal.changes
    assert any(c.path.endswith(".tf") for c in proposal.changes)
