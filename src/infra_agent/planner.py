"""Run `terraform plan` offline against LocalStack and capture the saved plan."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from infra_agent.config import Settings
from infra_agent.hashing import sha256_file
from infra_agent.runner import Runner, terraform_env

OVERRIDE_NAME = "zz_infra_agent_override.tf"
ENDPOINT_SERVICES = ("s3", "ec2", "dynamodb", "iam", "sts", "kms")


class PlanError(Exception):
    """terraform init, plan or show failed."""


@dataclass(frozen=True)
class PlanResult:
    plan_path: Path
    plan_json_path: Path
    plan_json: dict[str, Any]
    plan_sha256: str


def render_override(localstack_url: str, state_path: Path, region: str = "us-east-1") -> str:
    endpoints = "\n".join(f'    {svc:<8} = "{localstack_url}"' for svc in ENDPOINT_SERVICES)
    return f"""# Written by infra-agent. Not part of the reviewed diff.
terraform {{
  backend "local" {{
    path = "{state_path.as_posix()}"
  }}
}}

provider "aws" {{
  region                      = "{region}"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  s3_use_path_style           = true
  endpoints {{
{endpoints}
  }}
}}
"""


class Planner(Protocol):
    def plan(
        self, workdir: Path, *, state_path: Path, out_dir: Path, name_prefix: str
    ) -> PlanResult: ...


def _tail(text: str, n: int = 15) -> str:
    return "\n".join(text.strip().splitlines()[-n:])


class TerraformPlanner:
    def __init__(self, settings: Settings, runner: Runner) -> None:
        self.settings = settings
        self.runner = runner

    def plan(
        self, workdir: Path, *, state_path: Path, out_dir: Path, name_prefix: str
    ) -> PlanResult:
        state_path = state_path.resolve()
        out_dir = out_dir.resolve()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        (workdir / OVERRIDE_NAME).write_text(
            render_override(self.settings.localstack_url, state_path), encoding="utf-8"
        )
        env = terraform_env(self.settings, name_prefix=name_prefix)
        tf = self.settings.terraform_bin
        plan_bin = out_dir / "plan.bin"
        steps = {
            "init": [tf, "init", "-input=false", "-no-color"],
            "plan": [
                tf,
                "plan",
                "-input=false",
                "-no-color",
                "-lock-timeout=60s",
                f"-out={plan_bin}",
            ],
            "show": [tf, "show", "-json", str(plan_bin)],
        }
        shown = ""
        for name, argv in steps.items():
            res = self.runner.run(argv, cwd=workdir, purpose="plan", env=env)
            if res.returncode != 0:
                raise PlanError(f"terraform {name} failed: {_tail(res.stderr or res.stdout)}")
            if name == "show":
                shown = res.stdout
        plan_json_path = out_dir / "plan.json"
        plan_json_path.write_text(shown, encoding="utf-8")
        try:
            plan_json = json.loads(shown)
        except ValueError as e:
            raise PlanError("terraform show -json did not return JSON") from e
        return PlanResult(plan_bin, plan_json_path, plan_json, sha256_file(plan_bin))


class FakePlanner:
    """For tests. Consumes one plan dict per call and repeats the last one."""

    def __init__(self, plans: list[dict[str, Any]]) -> None:
        self.plans = list(plans)
        self.calls = 0

    def plan(
        self, workdir: Path, *, state_path: Path, out_dir: Path, name_prefix: str
    ) -> PlanResult:
        plan = self.plans[min(self.calls, len(self.plans) - 1)]
        self.calls += 1
        out_dir.mkdir(parents=True, exist_ok=True)
        body = json.dumps(plan, sort_keys=True)
        plan_bin = out_dir / "plan.bin"
        plan_bin.write_bytes(body.encode() + uuid.uuid4().hex.encode())
        plan_json_path = out_dir / "plan.json"
        plan_json_path.write_text(body, encoding="utf-8")
        return PlanResult(plan_bin, plan_json_path, plan, sha256_file(plan_bin))
