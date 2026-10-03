"""Read-only repo tools handed to the model. Confined to the repo root."""

from __future__ import annotations

import re
from pathlib import Path

TOOL_NAMES = ("list_files", "read_file", "submit_change")

_WINDOWS_ABS = re.compile(r"^[A-Za-z]:")


class RepoAccessError(Exception):
    """Raised when a path is outside what the model may read."""


class RepoTools:
    def __init__(self, root: Path, max_file_bytes: int = 64_000, max_files: int = 500) -> None:
        self.root = root
        self.max_file_bytes = max_file_bytes
        self.max_files = max_files

    def _inside(self, p: Path) -> bool:
        try:
            p.resolve().relative_to(self.root.resolve())
        except ValueError:
            return False
        return True

    def list_files(self) -> list[str]:
        out: list[str] = []
        for p in self.root.rglob("*"):
            rel = p.relative_to(self.root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            if ".tfstate" in p.name:
                continue
            if not p.is_file() or not self._inside(p):
                continue
            out.append(rel.as_posix())
        return sorted(out)[: self.max_files]

    def read_file(self, path: str) -> str:
        if not path:
            raise RepoAccessError("path is empty")
        if "\0" in path:
            raise RepoAccessError("path contains NUL")
        if "\\" in path:
            raise RepoAccessError("backslashes are not allowed in paths")
        if path.startswith("/") or _WINDOWS_ABS.match(path):
            raise RepoAccessError("absolute paths are not allowed")
        if ".." in path.split("/"):
            raise RepoAccessError("'..' segments are not allowed")
        target = self.root / path
        if not self._inside(target):
            raise RepoAccessError("path resolves outside the repo")
        if not target.exists():
            raise RepoAccessError(f"no such file: {path}")
        if not target.is_file():
            raise RepoAccessError(f"not a file: {path}")
        if target.stat().st_size > self.max_file_bytes:
            raise RepoAccessError(f"file too large (limit {self.max_file_bytes} bytes): {path}")
        try:
            return target.read_bytes().decode("utf-8")
        except UnicodeDecodeError as e:
            raise RepoAccessError(f"file is not valid UTF-8: {path}") from e
