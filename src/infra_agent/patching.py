"""Apply a proposed change to a scratch git copy of the repo and compute the diff."""

from __future__ import annotations

import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from infra_agent.hashing import sha256_bytes
from infra_agent.runner import Runner

ALLOWED_PATH = re.compile(r"^(?:[A-Za-z0-9_-]+/){0,2}[A-Za-z0-9_-]+\.tf$")
OVERRIDE_PATH = re.compile(r"(?:^|/)(?:[A-Za-z0-9_-]+_)?override\.tf$")
FORBIDDEN_CONTENT = [
    (re.compile(r'^\s*provisioner\s+"', re.M), "provisioner blocks are not allowed"),
    (re.compile(r'^\s*backend\s+"', re.M), "backend blocks are not allowed"),
    (re.compile(r"^\s*cloud\s*\{", re.M), "terraform cloud blocks are not allowed"),
]
GIT_ID = [
    "-c",
    "user.name=infra-agent",
    "-c",
    "user.email=infra-agent@localhost",
    "-c",
    "commit.gpgsign=false",
]
MAX_FILES = 20


@dataclass(frozen=True)
class FileChange:
    path: str
    content: str | None  # None deletes the file

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> FileChange:
        path = d.get("path")
        content = d.get("content")
        if not isinstance(path, str):
            raise ValueError("path must be a string")
        if content is not None and not isinstance(content, str):
            raise ValueError("content must be a string or null")
        return cls(path, content)


class PatchRefused(Exception):
    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons


@dataclass(frozen=True)
class PatchResult:
    workdir: Path
    base_commit: str
    diff: str
    patch_sha256: str
    changed_files: list[str]
    changed_lines: int


def validate_changes(changes: Sequence[FileChange]) -> list[str]:
    """Return refusal reasons. An empty list means the change set is acceptable."""
    reasons: list[str] = []
    if not changes:
        return ["no files were submitted"]
    if len(changes) > MAX_FILES:
        reasons.append(f"too many files: {len(changes)} > {MAX_FILES}")
    seen: set[str] = set()
    for c in changes:
        if c.path in seen:
            reasons.append(f"duplicate path: {c.path}")
        seen.add(c.path)
        if not ALLOWED_PATH.match(c.path):
            reasons.append(f"path not allowed: {c.path} (only .tf files, at most 3 levels deep)")
            continue
        if OVERRIDE_PATH.search(c.path):
            reasons.append(f"override files are not allowed: {c.path}")
            continue
        if c.content is not None:
            for rx, msg in FORBIDDEN_CONTENT:
                if rx.search(c.content):
                    reasons.append(f"{msg} ({c.path})")
    return reasons


def _git(runner: Runner, git_bin: str, args: Sequence[str], cwd: Path):
    return runner.run([git_bin, *args], cwd=cwd, purpose="git")


def prepare_workdir(repo: Path, workdir: Path, runner: Runner, git_bin: str = "git") -> str:
    """Copy the repo into workdir, commit it as the base and return the base commit."""
    shutil.copytree(
        repo,
        workdir,
        ignore=shutil.ignore_patterns(".git", ".terraform", "*.tfstate*", ".infra-agent"),
    )
    for args in (["init", "-q", "-b", "main"], ["add", "-A"]):
        res = _git(runner, git_bin, args, workdir)
        if res.returncode != 0:
            raise RuntimeError(f"git {args[0]} failed: {res.stderr.strip()}")
    res = _git(runner, git_bin, [*GIT_ID, "commit", "-q", "--allow-empty", "-m", "base"], workdir)
    if res.returncode != 0:
        raise RuntimeError(f"git commit failed: {res.stderr.strip()}")
    return _git(runner, git_bin, ["rev-parse", "HEAD"], workdir).stdout.strip()


def apply_changes(
    workdir: Path,
    changes: Sequence[FileChange],
    *,
    max_changed_lines: int,
    runner: Runner,
    git_bin: str = "git",
) -> PatchResult:
    reasons = validate_changes(changes)
    if reasons:
        raise PatchRefused(reasons)
    base = _git(runner, git_bin, ["rev-parse", "HEAD"], workdir).stdout.strip()
    root = workdir.resolve()
    for c in changes:
        target = (workdir / c.path).resolve()
        if root not in target.parents:
            raise PatchRefused([f"path resolves outside the repo: {c.path}"])
        if c.content is None:
            if not target.is_file():
                raise PatchRefused([f"cannot delete missing file: {c.path}"])
            target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(c.content, encoding="utf-8", newline="\n")
    _git(runner, git_bin, ["add", "-A"], workdir)
    numstat = _git(runner, git_bin, ["diff", "--cached", "--numstat"], workdir).stdout
    changed_lines = 0
    for line in numstat.splitlines():
        added, removed, *_ = line.split("\t")
        changed_lines += (int(added) if added.isdigit() else 0) + (
            int(removed) if removed.isdigit() else 0
        )
    if changed_lines > max_changed_lines:
        raise PatchRefused([f"change too large: {changed_lines} lines > {max_changed_lines}"])
    diff = _git(runner, git_bin, ["diff", "--cached", "--no-color"], workdir).stdout
    if not diff.strip():
        raise PatchRefused(["change is empty"])
    res = _git(runner, git_bin, [*GIT_ID, "commit", "-q", "-m", "proposal"], workdir)
    if res.returncode != 0:
        raise RuntimeError(f"git commit failed: {res.stderr.strip()}")
    return PatchResult(
        workdir=workdir,
        base_commit=base,
        diff=diff,
        patch_sha256=sha256_bytes(diff.encode()),
        changed_files=[c.path for c in changes],
        changed_lines=changed_lines,
    )
