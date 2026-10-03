"""SHA-256 helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(64 * 1024):
            h.update(chunk)
    return h.hexdigest()


def sha256_tree(root: Path, suffixes: tuple[str, ...] = (".rego",)) -> str:
    """Hash of every matching file's relative posix path and content, order independent."""
    files = sorted(
        (p for p in root.rglob("*") if p.is_file() and p.suffix in suffixes),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    h = hashlib.sha256()
    for p in files:
        h.update(f"{p.relative_to(root).as_posix()}\0{sha256_file(p)}\n".encode())
    return h.hexdigest()
