"""Out-of-process driver for the restart tests. Not collected by pytest (no test_ prefix).

python tests/restart_helper.py propose <home>
python tests/restart_helper.py approve <home> <run_id> <plan_sha256>
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from infra_agent.config import Settings  # noqa: E402
from infra_agent.runner import CommandResult  # noqa: E402
from infra_agent.service import Service  # noqa: E402
from tests.factories import LS  # noqa: E402
from tests.helpers import (  # noqa: E402
    EXAMPLE_REPO,
    SAFE_PLAN,
    SplitRunner,
    make_deps,
    ok_change,
    scripted,
)


def build(home: Path) -> Service:
    def log_apply(argv: Sequence[str]) -> CommandResult:
        with open(home / "apply_calls.log", "a", encoding="utf-8") as f:
            f.write("apply\n")
        return CommandResult(tuple(argv), 0, "Apply complete!", "")

    runner = SplitRunner(log_apply)
    settings = Settings(home=home, localstack_url=LS)
    deps = make_deps(
        home.parent,
        proposer=scripted(ok_change()),
        plans=[SAFE_PLAN],
        runner=runner,
        settings=settings,
    )
    return Service(
        settings, proposer=deps.proposer, planner=deps.planner, runner=runner, policy=deps.policy
    )


def main(argv: Sequence[str]) -> int:
    cmd, home = argv[0], Path(argv[1])
    home.mkdir(parents=True, exist_ok=True)
    with build(home) as svc:
        if cmd == "propose":
            out = svc.propose(EXAMPLE_REPO, "add a sessions table", run_id="r-restart")
            plan_sha = (out.review or {}).get("plan_sha256")
            print(
                json.dumps(
                    {"run_id": out.run_id, "exit_code": out.exit_code, "plan_sha256": plan_sha}
                )
            )
        elif cmd == "approve":
            out = svc.approve(argv[2], argv[3])
            print(json.dumps({"exit_code": out.exit_code, "message": out.message}))
        else:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
