"""Command line interface. `main(argv) -> int` returns the documented exit codes."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

from infra_agent import __version__
from infra_agent.audit import verify_log
from infra_agent.config import Settings
from infra_agent.proposer import OllamaProposer, ScriptedProposer
from infra_agent.runner import SubprocessRunner
from infra_agent.service import RunOutcome, Service

EXIT_CODES = """exit codes:
  0  applied (or already applied)
  1  internal error or bad usage
  2  paused, awaiting approval (run `infra-agent approve`)
  3  denied or refused after all attempts
  4  rejected by a human
  5  apply refused (plan hash mismatch or expired approval)
"""


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on bad usage, which would clash with 'paused'. Use 1 instead."""

    def error(self, message: str):  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


ServiceFactory = Callable[[Settings, argparse.Namespace], Service]


def build_parser() -> Parser:
    p = Parser(
        prog="infra-agent",
        description="An LLM proposes Terraform changes; policy and a hash-bound approval decide.",
        epilog=EXIT_CODES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"infra-agent {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("propose", help="ask the proposer for a change and run the pipeline")
    pr.add_argument("--repo", required=True, type=Path)
    pr.add_argument("--proposer", choices=["ollama", "scripted"], default="ollama")
    pr.add_argument("--script", type=Path, help="YAML script for --proposer scripted")
    pr.add_argument("--name-prefix")
    pr.add_argument("--json", action="store_true")
    pr.add_argument("request")

    for name in ("review", "status"):
        sp = sub.add_parser(name, help=f"show a run's {name}")
        sp.add_argument("run_id")
        sp.add_argument("--json", action="store_true")

    ap = sub.add_parser("approve", help="approve a paused run, bound to its plan hash")
    ap.add_argument("run_id")
    ap.add_argument("--plan-sha", required=True)
    ap.add_argument("--approver", default="cli")
    ap.add_argument("--reason", default="")
    ap.add_argument("--json", action="store_true")

    rj = sub.add_parser("reject", help="reject a paused run")
    rj.add_argument("run_id")
    rj.add_argument("--approver", default="cli")
    rj.add_argument("--reason", default="")
    rj.add_argument("--json", action="store_true")

    au = sub.add_parser("audit", help="audit log tools")
    au_sub = au.add_subparsers(dest="audit_cmd", required=True)
    av = au_sub.add_parser("verify", help="verify a run's hash-chained audit log")
    av.add_argument("run_id")

    po = sub.add_parser("policy", help="policy tools")
    po_sub = po.add_subparsers(dest="policy_cmd", required=True)
    po_sub.add_parser("test", help="run the Rego unit tests")
    return p


def default_factory(settings: Settings, args: argparse.Namespace) -> Service:
    proposer = None
    if getattr(args, "proposer", "ollama") == "scripted":
        if not args.script:
            raise ValueError("--proposer scripted needs --script FILE")
        proposer = ScriptedProposer.from_file(args.script)
    elif args.cmd == "propose":
        proposer = OllamaProposer(settings.ollama_url, settings.model)
    return Service(settings, proposer=proposer)


def _lines(items: list[dict]) -> list[str]:
    return [f"  {v['rule']}: {v['address']}: {v['msg']}" for v in items]


def render_review(review: dict, settings: Settings) -> str:
    stats = review.get("stats", {})
    out = [
        f"run {review['run_id']} · attempt {review['attempt']}/"
        f"{review.get('max_attempts', settings.max_attempts)} · "
        f"decision: {review['decision'].upper().replace('_', ' ')}"
    ]
    refused = review.get("refused_attempts") or []
    if refused:
        out.append("refused attempts:")
        for h in refused:
            for reason in h["reasons"]:
                out.append(f"  #{h['attempt']} {h['stage']}  {reason}")
    if review.get("needs_approval"):
        out.append("needs approval:")
        out += _lines(review["needs_approval"])
    if review.get("warn"):
        out.append("warnings:")
        out += _lines(review["warn"])
    risky = [c for c in review.get("changes", []) if "delete" in c["actions"]]
    if risky:
        out.append("deletes/replaces:")
        out += [f"  {c['address']} ({'+'.join(c['actions'])})" for c in risky]
    out.append(
        f"changes: +{stats.get('create', 0)} ~{stats.get('update', 0)} "
        f"-{stats.get('delete', 0)} ±{stats.get('replace', 0)}"
    )
    out.append(review["diff"].rstrip("\n"))
    out.append(f"plan sha256: {review['plan_sha256']}")
    out.append(
        f"approve with: infra-agent approve {review['run_id']} --plan-sha {review['plan_sha256']}"
    )
    return "\n".join(out)


def _emit(outcome: RunOutcome, args: argparse.Namespace, settings: Settings, out: TextIO) -> None:
    if getattr(args, "json", False):
        payload = {
            "run_id": outcome.run_id,
            "exit_code": outcome.exit_code,
            "status": outcome.status,
            "message": outcome.message,
            "review": outcome.review,
        }
        print(json.dumps(payload, indent=2), file=out)
        return
    if outcome.exit_code == 2 and outcome.review:
        print(render_review(outcome.review, settings), file=out)
        return
    print(
        f"run {outcome.run_id}: {outcome.status} (exit {outcome.exit_code}): {outcome.message}",
        file=out,
    )
    for h in outcome.state.get("history", []) if outcome.exit_code == 3 else []:
        for reason in h["reasons"]:
            print(f"  #{h['attempt']} {h['stage']}  {reason}", file=out)


def main(
    argv: Sequence[str] | None = None,
    *,
    service_factory: ServiceFactory | None = None,
    out: TextIO | None = None,
) -> int:
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    factory = service_factory or default_factory

    if args.cmd == "audit":
        res = verify_log(settings.home / "audit" / f"{args.run_id}.jsonl")
        print(res.message, file=out)
        if not res.ok:
            if res.first_bad_seq is not None:
                print(f"first bad seq: {res.first_bad_seq}", file=out)
            return 1
        print(f"{res.count} events", file=out)
        return 0
    if args.cmd == "policy":
        res = SubprocessRunner().run(
            [settings.opa_bin, "test", str(settings.policy_dir), "-v"],
            cwd=Path.cwd(),
            purpose="policy",
        )
        print(res.stdout + res.stderr, file=out, end="")
        return res.returncode

    try:
        with factory(settings, args) as svc:
            if args.cmd == "propose":
                outcome = svc.propose(args.repo, args.request, name_prefix=args.name_prefix)
            elif args.cmd == "status":
                outcome = svc.status(args.run_id)
            elif args.cmd == "review":
                review = svc.review(args.run_id)
                outcome = svc.status(args.run_id)
                if review is None and outcome.review is None:
                    print(f"run {args.run_id}: nothing to review ({outcome.message})", file=out)
                    return 1
                if args.json:
                    _emit(outcome, args, settings, out)
                else:
                    print(render_review(review or outcome.review, settings), file=out)
                return 0
            elif args.cmd == "approve":
                outcome = svc.approve(
                    args.run_id, args.plan_sha, approver=args.approver, reason=args.reason
                )
            else:
                outcome = svc.reject(args.run_id, approver=args.approver, reason=args.reason)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    _emit(outcome, args, settings, out)
    return outcome.exit_code


def entrypoint() -> None:
    sys.exit(main())
