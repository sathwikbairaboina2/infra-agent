from __future__ import annotations

import json
from pathlib import Path

from infra_agent.audit import GENESIS, AuditLog, verify_log


def _log(tmp_path: Path, n: int = 3) -> Path:
    p = tmp_path / "a.jsonl"
    log = AuditLog(p, "r1")
    for i in range(n):
        log.append("evt", i=i)
    return p


def test_chain_roundtrip(tmp_path: Path):
    p = _log(tmp_path)
    res = verify_log(p)
    assert res.ok and res.count == 3 and res.first_bad_seq is None
    events = AuditLog(p, "r1").events()
    assert events[0]["prev_sha256"] == GENESIS
    assert [e["seq"] for e in events] == [0, 1, 2]


def test_tamper_detected_names_first_bad_seq(tmp_path: Path):
    p = _log(tmp_path)
    lines = p.read_text().splitlines()
    rec = json.loads(lines[1])
    rec["i"] = 99
    lines[1] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    p.write_text("\n".join(lines) + "\n")
    res = verify_log(p)
    assert not res.ok
    assert res.first_bad_seq == 2


def test_deleted_line_detected(tmp_path: Path):
    p = _log(tmp_path)
    lines = p.read_text().splitlines()
    del lines[1]
    p.write_text("\n".join(lines) + "\n")
    assert not verify_log(p).ok


def test_reordered_lines_detected(tmp_path: Path):
    p = _log(tmp_path)
    lines = p.read_text().splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    p.write_text("\n".join(lines) + "\n")
    assert not verify_log(p).ok


def test_append_continues_chain_across_instances(tmp_path: Path):
    p = tmp_path / "a.jsonl"
    AuditLog(p, "r1").append("one")
    AuditLog(p, "r1").append("two")
    res = verify_log(p)
    assert res.ok and res.count == 2


def test_non_json_line_reported(tmp_path: Path):
    p = _log(tmp_path, 2)
    with open(p, "a", encoding="utf-8") as f:
        f.write("not json\n")
    res = verify_log(p)
    assert not res.ok and res.first_bad_seq == 2


def test_missing_file_not_ok(tmp_path: Path):
    assert not verify_log(tmp_path / "none.jsonl").ok
