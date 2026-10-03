from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from infra_agent.audit import verify_log

HELPER = Path(__file__).resolve().parent / "restart_helper.py"


def run_helper(*args: str, popen: bool = False) -> dict:
    cmd = [sys.executable, str(HELPER), *args]
    if popen:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate(timeout=120)
        assert proc.returncode == 0, err
    else:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        assert res.returncode == 0, res.stderr
        out = res.stdout
    return json.loads(out.strip().splitlines()[-1])


def test_resume_after_restart_applies_once(tmp_path: Path):
    home = tmp_path / "home"
    first = run_helper("propose", str(home))
    assert first["exit_code"] == 2
    second = run_helper("approve", str(home), first["run_id"], first["plan_sha256"])
    assert second["exit_code"] == 0
    third = run_helper("approve", str(home), first["run_id"], first["plan_sha256"])
    assert third["exit_code"] == 0
    assert third["message"] == "already applied"
    assert (home / "apply_calls.log").read_text().splitlines() == ["apply"]
    assert verify_log(home / "audit" / f"{first['run_id']}.jsonl").ok


def test_process_killed_while_paused_resumes(tmp_path: Path):
    home = tmp_path / "home"
    first = run_helper("propose", str(home), popen=True)
    assert first["exit_code"] == 2
    sqlite = home / "checkpoints.sqlite"
    assert sqlite.exists() and sqlite.stat().st_size > 0
    assert not (home / "apply_calls.log").exists()
    done = run_helper("approve", str(home), first["run_id"], first["plan_sha256"], popen=True)
    assert done["exit_code"] == 0
    assert (home / "apply_calls.log").read_text().splitlines() == ["apply"]
