"""Record scripts/demo.sh as an asciicast v2 file plus a plain transcript (run on the host).

    python scripts/record_demo.py

Pauses longer than 1.5 s are compressed to 1.5 s so the GIF stays watchable.
Render the GIF afterwards with the agg image (see the README).
"""

from __future__ import annotations

import json
import subprocess
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "demo"
MAX_PAUSE = 1.5
# On Windows a bare "bash" can resolve to WSL; prefer Git Bash.
BASH = next((p for p in ("C:/Program Files/Git/bin/bash.exe",) if Path(p).exists()), shutil.which("bash") or "bash")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [BASH, "scripts/dev.sh", "bash", "scripts/demo.sh"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.stdout is not None
    events: list[list] = []
    lines: list[str] = []
    last = time.monotonic()
    clock = 0.0
    for raw in proc.stdout:
        now = time.monotonic()
        clock += min(now - last, MAX_PAUSE)
        last = now
        line = raw.rstrip("\r\n")
        if line.startswith(" Container ") or "Creating" in line and "Container" in line:
            continue
        lines.append(line)
        events.append([round(clock, 3), "o", line + "\r\n"])
    code = proc.wait()
    header = {"version": 2, "width": 110, "height": 34}
    with (OUT / "demo.cast").open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(header) + "\n")
        for ev in events:
            f.write(json.dumps(ev) + "\n")
    (OUT / "demo.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
