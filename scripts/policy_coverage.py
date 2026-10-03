"""Check that every Rego rule has at least one allow test and one deny test.

Rules are found by their `"rule": "<name>"` literal in non-test .rego files. Tests are found by
the naming convention `test_<rule>_allow...` and `test_<rule>_deny...` in *_test.rego files.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

RULE_RE = re.compile(r'"rule":\s*"([a-z0-9_]+)"')
TEST_RE = re.compile(r"^test_([a-z0-9_]+?)_(allow|deny)(?:_|\b)", re.M)


def find_rules(policy_dir: Path) -> list[str]:
    rules: set[str] = set()
    for p in policy_dir.rglob("*.rego"):
        if p.name.endswith("_test.rego"):
            continue
        rules.update(RULE_RE.findall(p.read_text(encoding="utf-8")))
    return sorted(rules)


def find_tests(policy_dir: Path) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for p in policy_dir.rglob("*_test.rego"):
        for name, kind in TEST_RE.findall(p.read_text(encoding="utf-8")):
            found.setdefault(name, set()).add(kind)
    return found


def main(argv: Sequence[str] | None = None) -> int:
    default_dir = Path(__file__).resolve().parent.parent / "src" / "infra_agent" / "policy"
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--policy-dir", type=Path, default=default_dir)
    args = ap.parse_args(argv)

    rules = find_rules(args.policy_dir)
    tests = find_tests(args.policy_dir)
    width = max((len(r) for r in rules), default=4)
    print(f"{'rule'.ljust(width)} | allow | deny")
    covered = 0
    for r in rules:
        kinds = tests.get(r, set())
        a, d = "allow" in kinds, "deny" in kinds
        covered += a and d
        print(f"{r.ljust(width)} | {'yes' if a else 'NO':<5} | {'yes' if d else 'NO'}")
    pct = round(100 * covered / len(rules)) if rules else 0
    print(f"coverage: {covered}/{len(rules)} rules ({pct}%)")
    return 0 if rules and covered == len(rules) else 1


if __name__ == "__main__":
    sys.exit(main())
