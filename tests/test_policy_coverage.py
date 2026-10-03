from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

from infra_agent.config import Settings

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "policy_coverage.py"
spec = importlib.util.spec_from_file_location("policy_coverage", SCRIPT)
assert spec and spec.loader
cov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cov)

POLICY = Settings().policy_dir


def test_real_bundle_is_fully_covered(capsys):
    assert cov.main(["--policy-dir", str(POLICY)]) == 0
    out = capsys.readouterr().out
    assert "coverage: 11/11 rules (100%)" in out
    assert len(cov.find_rules(POLICY)) == 11


def test_missing_deny_test_fails(tmp_path: Path, capsys):
    bundle = tmp_path / "policy"
    shutil.copytree(POLICY, bundle)
    f = bundle / "rule_region_test.rego"
    text = f.read_text()
    f.write_text(text.replace("test_region_allowlist_deny_", "test_region_allowlist_xxx_"))
    assert cov.main(["--policy-dir", str(bundle)]) == 1
    assert "coverage: 10/11 rules" in capsys.readouterr().out
