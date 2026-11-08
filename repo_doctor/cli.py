"""Command line entry point for repo-doctor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .checks import (
    DEFAULT_MAX_SIZE,
    Finding,
    KIB,
    check_conflict_markers,
    check_large_files,
    check_required_files,
    check_secrets,
)


def collect_findings(root: Path, max_size: int, exclude: Sequence[str] = ()) -> list[Finding]:
    findings: list[Finding] = []
    findings += check_required_files(root)
    findings += check_large_files(root, max_size, exclude)
    findings += check_secrets(root, exclude)
    findings += check_conflict_markers(root, exclude)
    return findings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-doctor",
        description="Check a repository checkout for common hygiene problems.",
    )
    parser.add_argument("path", nargs="?", default=Path("."), type=Path, help="repository root (default: .)")
    parser.add_argument(
        "--max-size",
        type=int,
        default=DEFAULT_MAX_SIZE // KIB,
        metavar="KIB",
        help="flag files larger than this many KiB (default: 1024)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="skip paths matching this glob, repeatable (e.g. --exclude '*.min.js')",
    )
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    root = args.path.expanduser().resolve()
    if not root.is_dir():
        print(f"repo-doctor: {root} is not a directory", file=sys.stderr)
        return 2
    if args.max_size < 1:
        print("repo-doctor: --max-size must be positive", file=sys.stderr)
        return 2

    findings = collect_findings(root, args.max_size * KIB, args.exclude)

    if args.json:
        print(json.dumps([f.__dict__ for f in findings], indent=2))
    elif findings:
        print(f"repo-doctor: {len(findings)} problem(s)")
        for finding in findings:
            print(f"  {finding.check:<17} {finding.path:<28} {finding.message}")
    else:
        print("repo-doctor: clean, no problems found")

    return 1 if findings else 0


def entry() -> None:  # pragma: no cover - console script wrapper
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    entry()
