from __future__ import annotations

import os
from pathlib import Path

import pytest

from infra_agent.repo_tools import TOOL_NAMES, RepoAccessError, RepoTools


@pytest.fixture
def root(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "mod").mkdir(parents=True)
    (r / "main.tf").write_text('resource "x" "y" {}\n')
    (r / "mod" / "a.tf").write_text("# a\n")
    return r


def test_tool_names():
    assert TOOL_NAMES == ("list_files", "read_file", "submit_change")


def test_reads_nested_file(root: Path):
    assert RepoTools(root).read_file("mod/a.tf") == "# a\n"


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/etc/passwd",
        "C:\\x",
        "C:/x",
        "\\\\server\\x",
        "../outside.tf",
        "mod/../../outside.tf",
        "mod\\a.tf",
        "main.tf\0",
        "mod",
        "missing.tf",
    ],
)
def test_refusals(root: Path, path: str):
    with pytest.raises(RepoAccessError):
        RepoTools(root).read_file(path)


def test_size_cap(root: Path):
    (root / "big.tf").write_text("x" * 100)
    with pytest.raises(RepoAccessError, match="too large"):
        RepoTools(root, max_file_bytes=50).read_file("big.tf")


def test_non_utf8(root: Path):
    (root / "bin.tf").write_bytes(b"\xff\xfe\x00\x80")
    with pytest.raises(RepoAccessError, match="UTF-8"):
        RepoTools(root).read_file("bin.tf")


def test_symlink_escape_blocked(root: Path):
    outside = root.parent / "outside.tf"
    outside.write_text("secret")
    os.symlink(outside, root / "link.tf")
    with pytest.raises(RepoAccessError):
        RepoTools(root).read_file("link.tf")
    assert "link.tf" not in RepoTools(root).list_files()


def test_list_skips_dot_dirs_and_state(root: Path):
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("x")
    (root / ".terraform").mkdir()
    (root / ".terraform" / "p.tf").write_text("x")
    (root / "terraform.tfstate").write_text("{}")
    (root / "terraform.tfstate.backup").write_text("{}")
    assert RepoTools(root).list_files() == ["main.tf", "mod/a.tf"]
