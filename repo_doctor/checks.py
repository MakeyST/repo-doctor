"""Hygiene checks for a repository checkout.

Every check is a small pure function: it receives the repository root and
returns a list of :class:`Finding` objects.  The CLI only wires them together,
which keeps the checks easy to test and easy to extend.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

KIB = 1024
DEFAULT_MAX_SIZE = 1024 * KIB

# Directories that never belong to the source tree we want to audit.
SKIP_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".venv", "venv", "env",
    "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "dist", "build", ".tox",
}

# High-signal patterns only: these rarely appear in prose by accident.
SECRET_PATTERNS = (
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("Slack token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
)

# "=======" is left out on purpose: it is also a valid Markdown heading rule.
CONFLICT_MARKERS = re.compile(r"^(?:<{7} |>{7} )", re.MULTILINE)

# Public examples from the provider documentation.  They are not leaks, and
# flagging them only teaches people to ignore the output.
ALLOWED_EXAMPLES = {"AKIAIOSFODNN7EXAMPLE"}


@dataclass(frozen=True)
class Finding:
    """One problem found in the checkout."""

    check: str
    path: str
    message: str


def iter_files(root: Path) -> Iterator[Path]:
    """Yield files under *root*, skipping vendored and generated directories."""
    for path in sorted(root.rglob("*")):
        try:
            rel = path.relative_to(root)
        except ValueError:  # pragma: no cover - rglob always stays below root
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.is_symlink() or path.is_dir():
            continue
        yield path


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _human_size(size: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"  # pragma: no cover - unreachable


def _read_text(path: Path, max_size: int = DEFAULT_MAX_SIZE) -> str | None:
    """Return the file decoded as UTF-8, or None if it is binary/too large."""
    try:
        if path.stat().st_size > max_size:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:4096]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def check_required_files(root: Path) -> list[Finding]:
    """README, LICENSE and .gitignore should exist next to the source."""
    try:
        names = [p.name.lower() for p in root.iterdir() if p.is_file()]
    except OSError:
        return []

    findings: list[Finding] = []
    if not any(name.startswith("readme") for name in names):
        findings.append(Finding("required-files", "README", "no README file"))
    if not any(name.startswith(("license", "licence", "copying")) for name in names):
        findings.append(Finding("required-files", "LICENSE", "no license file"))
    if ".gitignore" not in names:
        findings.append(Finding("required-files", ".gitignore", "no .gitignore"))
    return findings


def check_large_files(root: Path, max_size: int = DEFAULT_MAX_SIZE) -> list[Finding]:
    """Flag files that are larger than *max_size* bytes."""
    findings: list[Finding] = []
    for path in iter_files(root):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > max_size:
            findings.append(
                Finding(
                    "large-files",
                    _relative(root, path),
                    f"{_human_size(size)} exceeds {_human_size(max_size)}",
                )
            )
    return findings


def check_secrets(root: Path) -> list[Finding]:
    """Look for credentials that should never be committed."""
    findings: list[Finding] = []
    for path in iter_files(root):
        text = _read_text(path)
        if text is None:
            continue
        for label, pattern in SECRET_PATTERNS:
            if any(match.group(0) not in ALLOWED_EXAMPLES for match in pattern.finditer(text)):
                findings.append(Finding("secrets", _relative(root, path), f"possible {label}"))
    return findings


def check_conflict_markers(root: Path) -> list[Finding]:
    """Catch files saved in the middle of a merge."""
    findings: list[Finding] = []
    for path in iter_files(root):
        text = _read_text(path)
        if text is None:
            continue
        if CONFLICT_MARKERS.search(text):
            findings.append(Finding("conflict-markers", _relative(root, path), "unresolved merge conflict markers"))
    return findings
