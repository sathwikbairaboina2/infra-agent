"""OPA evaluation through the `opa eval` binary. Fails closed on every error."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from infra_agent.hashing import sha256_tree
from infra_agent.runner import Runner

VALID_DECISIONS = {"allow", "deny", "needs_approval"}


class PolicyError(Exception):
    """OPA failed or returned something unusable. Callers must treat this as a refusal."""


class OpaPolicy:
    def __init__(self, policy_dir: Path, runner: Runner, opa_bin: str = "opa") -> None:
        self.policy_dir = policy_dir
        self.runner = runner
        self.opa_bin = opa_bin
        self._bundle_sha256: str | None = None

    @property
    def bundle_sha256(self) -> str:
        if self._bundle_sha256 is None:
            self._bundle_sha256 = sha256_tree(self.policy_dir)
        return self._bundle_sha256

    def evaluate(
        self, changeset: Mapping[str, Any], *, context: Mapping[str, Any]
    ) -> dict[str, Any]:
        payload = json.dumps({"changeset": changeset, "context": context})
        fd, tmp = tempfile.mkstemp(suffix=".json", prefix="opa-input-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            res = self.runner.run(
                [
                    self.opa_bin,
                    "eval",
                    "--format",
                    "json",
                    "-d",
                    str(self.policy_dir),
                    "-i",
                    tmp,
                    "data.infra.decision",
                ],
                cwd=self.policy_dir,
                purpose="policy",
            )
        finally:
            Path(tmp).unlink(missing_ok=True)
        if res.returncode != 0:
            raise PolicyError(f"opa exited {res.returncode}: {res.stderr.strip()[-500:]}")
        try:
            value = json.loads(res.stdout)["result"][0]["expressions"][0]["value"]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise PolicyError(f"opa returned no decision: {res.stdout.strip()[:200]!r}") from e
        if not isinstance(value, dict) or value.get("decision") not in VALID_DECISIONS:
            raise PolicyError(f"unknown policy decision: {str(value)[:200]}")
        return {**value, "policy_bundle_sha256": self.bundle_sha256}
