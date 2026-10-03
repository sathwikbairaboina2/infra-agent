from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config, items):
    has_ls = bool(os.environ.get("INFRA_AGENT_LOCALSTACK_URL"))
    live = os.environ.get("INFRA_AGENT_LIVE") == "1"
    for item in items:
        if "localstack" in item.keywords and not has_ls:
            item.add_marker(pytest.mark.skip(reason="set INFRA_AGENT_LOCALSTACK_URL to run"))
        if "live" in item.keywords and not live:
            item.add_marker(pytest.mark.skip(reason="set INFRA_AGENT_LIVE=1 to run"))
