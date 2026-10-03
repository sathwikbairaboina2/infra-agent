from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from infra_agent.proposer import (
    TOOLS,
    OllamaProposer,
    ProposalError,
    ScriptedProposer,
)
from infra_agent.repo_tools import TOOL_NAMES, RepoTools


@pytest.fixture
def repo(tmp_path: Path) -> RepoTools:
    r = tmp_path / "repo"
    r.mkdir()
    (r / "main.tf").write_text('resource "aws_s3_bucket" "b" {}\n')
    return RepoTools(r)


def call(name: str, args) -> dict:
    return {"function": {"name": name, "arguments": args}}


def reply(*calls: dict, content: str = "") -> dict:
    return {"message": {"role": "assistant", "content": content, "tool_calls": list(calls)}}


class Transport:
    """Scripted ollama: returns the queued responses in order and records the requests."""

    def __init__(self, responses: list[dict | int]) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        nxt = self.responses.pop(0)
        if isinstance(nxt, int):
            return httpx.Response(nxt, text="nope")
        return httpx.Response(200, json=nxt)


def proposer(t: Transport, **kw) -> OllamaProposer:
    client = httpx.Client(transport=httpx.MockTransport(t))
    return OllamaProposer("http://ollama:11434", "m", client=client, **kw)


SUBMIT = call(
    "submit_change",
    {"summary": "add table", "files": [{"path": "db.tf", "content": "# db\n"}]},
)


def test_tool_registry_closed():
    names = tuple(t["function"]["name"] for t in TOOLS)
    assert names == TOOL_NAMES
    assert len(names) == 3


def test_happy_path_read_then_submit(repo: RepoTools):
    t = Transport([reply(call("read_file", {"path": "main.tf"})), reply(SUBMIT)])
    p = proposer(t).propose(request="add a table", repo=repo, feedback=[], attempt=1)
    assert p.summary == "add table"
    assert [(c.path, c.content) for c in p.changes] == [("db.tf", "# db\n")]
    second = t.requests[1]
    assert second["think"] is False
    assert second["stream"] is False
    assert any(
        m["role"] == "tool" and 'resource "aws_s3_bucket"' in m["content"]
        for m in second["messages"]
    )


def test_list_files_tool(repo: RepoTools):
    t = Transport([reply(call("list_files", {})), reply(SUBMIT)])
    proposer(t).propose(request="x", repo=repo, feedback=[], attempt=1)
    tool_msgs = [m for m in t.requests[1]["messages"] if m["role"] == "tool"]
    assert tool_msgs[0]["content"] == "main.tf"


def test_read_outside_repo_returns_error_to_model_not_exception(repo: RepoTools):
    t = Transport([reply(call("read_file", {"path": "../../etc/passwd"})), reply(SUBMIT)])
    proposer(t).propose(request="x", repo=repo, feedback=[], attempt=1)
    tool_msgs = [m for m in t.requests[1]["messages"] if m["role"] == "tool"]
    assert tool_msgs[0]["content"].startswith("error:")


def test_unknown_tool_gets_error(repo: RepoTools):
    t = Transport([reply(call("run_shell", {"cmd": "id"})), reply(SUBMIT)])
    proposer(t).propose(request="x", repo=repo, feedback=[], attempt=1)
    tool_msgs = [m for m in t.requests[1]["messages"] if m["role"] == "tool"]
    assert tool_msgs[0]["content"] == "error: unknown tool"


def test_feedback_included_in_first_user_message(repo: RepoTools):
    t = Transport([reply(SUBMIT)])
    proposer(t).propose(
        request="add a table", repo=repo, feedback=["policy: no ssh", "plan failed"], attempt=2
    )
    user = t.requests[0]["messages"][1]["content"]
    assert user.startswith("add a table")
    assert "Your previous attempt was refused:\n- policy: no ssh\n- plan failed\n" in user
    assert user.endswith("Fix these and submit again.")


def test_turn_limit_raises(repo: RepoTools):
    t = Transport([reply(content="thinking"), reply(content="still thinking")])
    with pytest.raises(ProposalError, match="2 turns"):
        proposer(t, max_turns=2).propose(request="x", repo=repo, feedback=[], attempt=1)
    nudge = t.requests[1]["messages"][-1]
    assert nudge["content"] == "Call submit_change with the full file contents."


def test_string_arguments_parsed(repo: RepoTools):
    args = json.dumps({"summary": "s", "files": [{"path": "a.tf", "content": None}]})
    t = Transport([reply(call("submit_change", args))])
    p = proposer(t).propose(request="x", repo=repo, feedback=[], attempt=1)
    assert p.changes[0].content is None


def test_invalid_submit_is_sent_back_then_fixed(repo: RepoTools):
    bad = call("submit_change", {"summary": "s", "files": []})
    t = Transport([reply(bad), reply(SUBMIT)])
    p = proposer(t).propose(request="x", repo=repo, feedback=[], attempt=1)
    assert p.changes[0].path == "db.tf"
    assert t.requests[1]["messages"][-1]["content"].startswith("error:")


def test_http_error_raises_proposal_error(repo: RepoTools):
    with pytest.raises(ProposalError):
        proposer(Transport([500])).propose(request="x", repo=repo, feedback=[], attempt=1)


def test_connection_error_raises_proposal_error(repo: RepoTools):
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    client = httpx.Client(transport=httpx.MockTransport(boom))
    p = OllamaProposer("http://x", "m", client=client)
    with pytest.raises(ProposalError):
        p.propose(request="x", repo=repo, feedback=[], attempt=1)


def test_scripted_replays_and_repeats_last(repo: RepoTools):
    spec = {
        "attempts": [
            {"summary": "one", "files": [{"path": "a.tf", "content": "# 1\n"}]},
            {"summary": "two", "files": [{"path": "a.tf", "content": "# 2\n"}]},
        ]
    }
    sp = ScriptedProposer(spec)
    assert sp.propose(request="r", repo=repo, feedback=[], attempt=1).summary == "one"
    assert sp.propose(request="r", repo=repo, feedback=["bad"], attempt=2).summary == "two"
    assert sp.propose(request="r", repo=repo, feedback=["bad", "bad2"], attempt=3).summary == "two"
    assert sp.seen_feedback == [[], ["bad"], ["bad", "bad2"]]


def test_scripted_from_file(tmp_path: Path, repo: RepoTools):
    f = tmp_path / "s.yaml"
    f.write_text("attempts:\n  - summary: hi\n    files:\n      - {path: a.tf, content: '# x'}\n")
    p = ScriptedProposer.from_file(f).propose(request="r", repo=repo, feedback=[], attempt=1)
    assert p.summary == "hi" and p.changes[0].path == "a.tf"
