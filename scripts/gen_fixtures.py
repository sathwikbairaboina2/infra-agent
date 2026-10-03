"""Regenerate golden plan JSON from fixtures/configs/* with real terraform.

Needs LocalStack (INFRA_AGENT_LOCALSTACK_URL). Run inside the dev container:
    scripts/dev.sh uv run python scripts/gen_fixtures.py [name ...]
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from infra_agent.config import Settings
from infra_agent.planner import TerraformPlanner
from infra_agent.runner import SubprocessRunner

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = ROOT / "fixtures" / "configs"
PLANS = ROOT / "fixtures" / "plans"


def generate(name: str, planner: TerraformPlanner) -> Path:
    with tempfile.TemporaryDirectory(prefix=f"fixture-{name}-") as tmp:
        tmp_path = Path(tmp)
        work = tmp_path / "work"
        shutil.copytree(
            CONFIGS / name, work, ignore=shutil.ignore_patterns(".terraform", "*.tfstate*")
        )
        res = planner.plan(
            work,
            state_path=tmp_path / "state" / "fixture.tfstate",
            out_dir=tmp_path / "out",
            name_prefix="demo",
        )
        plan = dict(res.plan_json)
        plan.pop("timestamp", None)  # volatile
        out = PLANS / f"{name}.json"
        out.write_text(json.dumps(plan, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return out


def main(argv: Sequence[str] | None = None) -> int:
    names = list(argv if argv is not None else sys.argv[1:]) or sorted(
        p.name for p in CONFIGS.iterdir() if p.is_dir()
    )
    planner = TerraformPlanner(Settings.from_env(), SubprocessRunner())
    PLANS.mkdir(parents=True, exist_ok=True)
    for name in names:
        print(f"planning {name} ...", flush=True)
        print(f"  wrote {generate(name, planner).relative_to(ROOT)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
