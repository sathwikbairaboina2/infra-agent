"""Seeded benchmark: real terraform, real OPA, real LocalStack, a human that approves everything.

    uv run python -m bench.seeded [--cases evals/seeded] [--only ID] [--out bench/results]

Headline: how many seeded policy violations reached `terraform apply`. The simulated human
approves every review it is shown (with the right hash, or deliberately a wrong one), so a
violation can only be stopped by the pipeline itself.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import platform
import re
import secrets
import shutil
import statistics
import sys
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from infra_agent.audit import AuditLog
from infra_agent.config import Settings
from infra_agent.patching import prepare_workdir
from infra_agent.planner import TerraformPlanner
from infra_agent.proposer import ScriptedProposer
from infra_agent.runner import RecordingRunner, SubprocessRunner, terraform_env
from infra_agent.service import Service

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "examples" / "tf-basic"
KINDS = ("violation", "benign", "approval")


def load_cases(cases_dir: Path, only: str | None = None) -> list[dict[str, Any]]:
    cases = [
        yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(cases_dir.glob("*.yaml"))
    ]
    return [c for c in cases if only is None or c["id"] == only]


def _policy_rules(history: list[dict[str, Any]]) -> list[str]:
    rules: list[str] = []
    for h in history:
        if h["stage"] != "policy":
            continue
        for reason in h["reasons"]:
            name = reason.split(":", 1)[0]
            if re.fullmatch(r"[a-z0-9_]+", name) and name not in rules:
                rules.append(name)
    return rules


def _seconds(events: list[dict[str, Any]], start: str, end: str) -> float | None:
    at = {e["event"]: e["at"] for e in events if e["event"] in (start, end)}
    if start in at and end in at:
        return round(
            (datetime.fromisoformat(at[end]) - datetime.fromisoformat(at[start])).total_seconds(), 2
        )
    return None


def run_case(
    case: dict[str, Any], settings: Settings, stamp: str, base_home: Path
) -> dict[str, Any]:
    started = datetime.now(UTC)
    home = base_home / "bench" / stamp / case["id"]
    prefix = f"{case['id'][:3]}{secrets.token_hex(3)}"
    settings = dataclasses.replace(settings, home=home, name_prefix=prefix)
    runner = RecordingRunner(SubprocessRunner())
    state_path = home / "state" / f"{REPO.name}.tfstate"

    baseline_applies = 0
    if case.get("baseline_apply"):
        work = home / "baseline" / "work"
        prepare_workdir(REPO, work, runner)
        res = TerraformPlanner(settings, runner).plan(
            work, state_path=state_path, out_dir=home / "baseline", name_prefix=prefix
        )
        applied = runner.run(
            [settings.terraform_bin, "apply", "-input=false", "-no-color", str(res.plan_path)],
            cwd=work,
            purpose="apply",
            env=terraform_env(settings, name_prefix=prefix),
        )
        if applied.returncode != 0:
            raise RuntimeError(f"baseline apply failed for {case['id']}: {applied.stderr[-500:]}")
        baseline_applies = len(runner.apply_calls())

    run_id = f"bench-{case['id']}"
    proposer = ScriptedProposer({"attempts": case["attempts"]})
    with Service(settings, proposer=proposer, runner=runner) as svc:
        out = svc.propose(REPO, case["request"], run_id=run_id)
        final = out
        review = out.review
        if out.exit_code == 2:
            sha = review["plan_sha256"]
            if case.get("tamper_plan"):
                plan_bin = Path(out.state["plan_path"])
                plan_bin.write_bytes(plan_bin.read_bytes() + b"tampered-after-review")
            if case.get("human") == "approve_wrong_hash":
                sha = "f" * 64
            final = svc.approve(run_id, sha, approver="bench-human")
    events = AuditLog(home / "audit" / f"{run_id}.jsonl", run_id).events()
    history = out.state.get("history", [])
    if final.exit_code == 0 and final.status == "applied":
        stage = "applied"
    elif final.exit_code == 5:
        stage = "apply_gate"
    elif final.exit_code == 3:
        stage = history[-1]["stage"] if history else "unknown"
    else:
        stage = final.status
    deny_rules = _policy_rules(history)
    needs_rules = [v["rule"] for v in (review or {}).get("needs_approval", [])]
    expect = case["expect"]
    rule = expect.get("rule")
    matched = stage == expect["stage"]
    if matched and rule:
        matched = rule in (needs_rules if case["kind"] == "approval" else deny_rules)
    result = {
        "id": case["id"],
        "kind": case["kind"],
        "expect": expect,
        "final_status": final.status,
        "exit_code": final.exit_code,
        "stage_reached": stage,
        "deny_rules": deny_rules,
        "needs_approval_rules": needs_rules,
        "attempts": out.state.get("attempt", 0),
        "reached_apply": len(runner.apply_calls()) - baseline_applies > 0,
        "seconds_to_review": _seconds(events, "run_started", "review_ready"),
        "seconds_total": round((datetime.now(UTC) - started).total_seconds(), 2),
        "matched_expectation": matched,
    }
    shutil.rmtree(home / "baseline", ignore_errors=True)
    return result


def _first_line(text: str) -> str:
    return text.strip().splitlines()[0] if text.strip() else ""


def collect_versions(settings: Settings) -> dict[str, Any]:
    runner = SubprocessRunner()
    tf = runner.run([settings.terraform_bin, "version"], cwd=ROOT, purpose="plan")
    opa = runner.run([settings.opa_bin, "version"], cwd=ROOT, purpose="policy")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    tag = re.search(r"image:\s*localstack/localstack:(\S+)", compose)
    return {
        "terraform": _first_line(tf.stdout),
        "opa": _first_line(opa.stdout),
        "localstack": tag.group(1) if tag else None,
        "python": platform.python_version(),
    }


def git_commit() -> str | None:
    res = SubprocessRunner().run(["git", "rev-parse", "HEAD"], cwd=ROOT, purpose="git")
    return res.stdout.strip() if res.returncode == 0 else None


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    by = {k: [r for r in results if r["kind"] == k] for k in KINDS}
    review_times = sorted(
        r["seconds_to_review"] for r in results if r["seconds_to_review"] is not None
    )
    p90 = (
        review_times[min(len(review_times) - 1, int(0.9 * len(review_times)))]
        if review_times
        else None
    )
    return {
        "violations_total": len(by["violation"]),
        "violations_reached_apply": sum(r["reached_apply"] for r in by["violation"]),
        "benign_total": len(by["benign"]),
        "benign_applied": sum(r["stage_reached"] == "applied" for r in by["benign"]),
        "approval_total": len(by["approval"]),
        "approval_paused_with_expected_rule": sum(
            r["matched_expectation"] and r["stage_reached"] == "applied" for r in by["approval"]
        ),
        "expectation_mismatches": sum(not r["matched_expectation"] for r in results),
        "median_seconds_to_review": round(statistics.median(review_times), 2)
        if review_times
        else None,
        "p90_seconds_to_review": p90,
    }


def headline(s: dict[str, Any]) -> str:
    return (
        f"{s['violations_reached_apply']} of {s['violations_total']} seeded policy violations "
        f"reached apply, while a simulated human approved every review; "
        f"{s['benign_applied']} of {s['benign_total']} benign changes applied."
    )


def render_md(report: dict[str, Any]) -> str:
    s, v = report["summary"], report["versions"]
    lines = [
        headline(s),
        "",
        f"- Approval-required cases that paused with the expected rule and then applied: "
        f"{s['approval_paused_with_expected_rule']} of {s['approval_total']}",
        f"- Expectation mismatches: {s['expectation_mismatches']}",
        f"- Seconds from start to review (median / p90): "
        f"{s['median_seconds_to_review']} / {s['p90_seconds_to_review']}",
        f"- {v['terraform']}, {v['opa']}, LocalStack {v['localstack']}, Python {v['python']}",
        f"- Host: {report['host']['platform']}, {report['host']['cpus']} CPUs; "
        f"commit {report['git_commit']}",
        f"- Started {report['started_at']}, finished {report['finished_at']}",
        "",
        "| case | kind | expected | reached | rules | attempts | reached apply | s to review |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in report["cases"]:
        rules = ", ".join(dict.fromkeys(r["deny_rules"] or r["needs_approval_rules"])) or "-"
        mark = "" if r["matched_expectation"] else " (MISMATCH)"
        lines.append(
            f"| {r['id']} | {r['kind']} | {r['expect']['stage']} | {r['stage_reached']}{mark} | "
            f"{rules} | {r['attempts']} | {'yes' if r['reached_apply'] else 'no'} | "
            f"{r['seconds_to_review'] if r['seconds_to_review'] is not None else '-'} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--cases", type=Path, default=ROOT / "evals" / "seeded")
    ap.add_argument("--only")
    ap.add_argument("--out", type=Path, default=ROOT / "bench" / "results")
    args = ap.parse_args(argv)

    settings = Settings.from_env()
    cases = load_cases(args.cases, args.only)
    if not cases:
        print("no cases found", file=sys.stderr)
        return 1
    base_home = Path(os.environ.get("INFRA_AGENT_HOME") or tempfile.mkdtemp(prefix="infra-agent-"))
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    started = datetime.now(UTC)
    results = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']} ...", end=" ", flush=True)
        r = run_case(case, settings, stamp, base_home)
        print(
            f"{r['stage_reached']} ({'ok' if r['matched_expectation'] else 'MISMATCH'}, "
            f"{r['seconds_total']}s)",
            flush=True,
        )
        results.append(r)

    report = {
        "summary": summarize(results),
        "versions": collect_versions(settings),
        "host": {"platform": platform.platform(), "cpus": os.cpu_count()},
        "git_commit": git_commit(),
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "cases": results,
    }
    s = report["summary"]
    if not args.only:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "seeded-latest.json").write_text(json.dumps(report, indent=2) + "\n", "utf-8")
        (args.out / "seeded-latest.md").write_text(render_md(report), encoding="utf-8")
    print(f"violations reached apply: {s['violations_reached_apply']}/{s['violations_total']}")
    print(f"benign applied: {s['benign_applied']}/{s['benign_total']}")
    print(
        f"approval cases paused with expected rule and applied: "
        f"{s['approval_paused_with_expected_rule']}/{s['approval_total']}"
    )
    print(f"expectation mismatches: {s['expectation_mismatches']}")
    bad = (
        s["violations_reached_apply"] > 0
        or s["benign_applied"] < s["benign_total"]
        or s["expectation_mismatches"] > 0
    )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
