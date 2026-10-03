"""Hash-chained JSONL audit log. Each line carries the SHA-256 of the previous line."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from infra_agent.hashing import sha256_bytes

GENESIS = "0" * 64


def utcnow() -> datetime:
    return datetime.now(UTC)


def _dump(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"))


class AuditLog:
    def __init__(self, path: Path, run_id: str, clock: Callable[[], datetime] = utcnow) -> None:
        self.path = path
        self.run_id = run_id
        self.clock = clock

    def _last(self) -> tuple[int, str]:
        """Next seq and prev hash, read from the last line on disk."""
        if not self.path.exists():
            return 0, GENESIS
        lines = [ln for ln in self.path.read_text(encoding="utf-8").split("\n") if ln]
        if not lines:
            return 0, GENESIS
        last = json.loads(lines[-1])
        return last["seq"] + 1, sha256_bytes(lines[-1].encode())

    def append(self, event: str, **fields: Any) -> dict[str, Any]:
        seq, prev = self._last()
        record = {
            "seq": seq,
            "run_id": self.run_id,
            "event": event,
            "at": self.clock().isoformat(),
            "prev_sha256": prev,
            **fields,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(_dump(record) + "\n")
        return record

    def events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(ln) for ln in self.path.read_text(encoding="utf-8").split("\n") if ln]


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    first_bad_seq: int | None
    message: str
    count: int


def verify_log(path: Path) -> VerifyResult:
    if not path.exists():
        return VerifyResult(False, None, f"missing file: {path}", 0)
    lines = [ln for ln in path.read_text(encoding="utf-8").split("\n") if ln]
    prev = GENESIS
    for i, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            return VerifyResult(False, i, f"line {i} is not valid JSON", i)
        if not isinstance(rec, dict) or rec.get("seq") != i:
            return VerifyResult(False, i, f"line {i}: seq is out of order", i)
        if rec.get("prev_sha256") != prev:
            return VerifyResult(False, i, f"line {i}: hash chain broken", i)
        prev = sha256_bytes(line.encode())
    return VerifyResult(True, None, "audit chain ok", len(lines))
