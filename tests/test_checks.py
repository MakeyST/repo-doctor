from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Iterator

import pytest

from repo_doctor.checks import (
    check_conflict_markers,
    check_large_files,
    check_required_files,
    check_secrets,
)
from repo_doctor.cli import parse_size

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORK = PROJECT_ROOT / ".test-work"


@pytest.fixture
def repo_dir() -> Iterator[Path]:
    """A throw-away directory inside the project, removed after the test."""
    WORK.mkdir(exist_ok=True)
    path = WORK / f"case-{uuid.uuid4().hex[:10]}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def make_repo(root: Path) -> Path:
    (root / "README.md").write_text("# demo\n", encoding="utf-8")
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    return root


def test_clean_checkout_has_no_findings(repo_dir: Path) -> None:
    root = make_repo(repo_dir)
    assert check_required_files(root) == []
    assert check_large_files(root) == []
    assert check_secrets(root) == []
    assert check_conflict_markers(root) == []


def test_missing_files_are_reported(repo_dir: Path) -> None:
    findings = check_required_files(repo_dir)
    reported = {finding.path for finding in findings}
    assert reported == {"README", "LICENSE", ".gitignore"}
    assert all(finding.check == "required-files" for finding in findings)


def test_large_file_is_reported(repo_dir: Path) -> None:
    root = make_repo(repo_dir)
    (root / "blob.bin").write_bytes(b"x" * 200)
    findings = check_large_files(root, max_size=64)
    assert [finding.path for finding in findings] == ["blob.bin"]
    assert "exceeds" in findings[0].message


def test_vendor_directories_are_skipped(repo_dir: Path) -> None:
    root = make_repo(repo_dir)
    vendor = root / "node_modules" / "pkg"
    vendor.mkdir(parents=True)
    (vendor / "bundle.js").write_bytes(b"x" * 200)
    assert check_large_files(root, max_size=64) == []


def test_secret_patterns_are_detected(repo_dir: Path) -> None:
    root = make_repo(repo_dir)
    (root / "settings.py").write_text(
        'AWS_KEY = "AKIA2E0A8F3B244C9986"\nTOKEN = "ghp_' + "a" * 36 + '"\n',
        encoding="utf-8",
    )
    labels = {finding.message for finding in check_secrets(root)}
    assert labels == {"possible AWS access key", "possible GitHub token"}


def test_documentation_example_key_is_ignored(repo_dir: Path) -> None:
    root = make_repo(repo_dir)
    (root / "README.md").write_text('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")
    assert check_secrets(root) == []


def test_binary_files_are_ignored(repo_dir: Path) -> None:
    root = make_repo(repo_dir)
    (root / "blob.dat").write_bytes(b"\x00AKIAIOSFODNN7EXAMPLE")
    assert check_secrets(root) == []


def test_conflict_markers_are_detected(repo_dir: Path) -> None:
    root = make_repo(repo_dir)
    (root / "app.py").write_text(
        "<<<<<<< HEAD\nprint(1)\n=======\nprint(2)\n>>>>>>> feature\n",
        encoding="utf-8",
    )
    assert [finding.path for finding in check_conflict_markers(root)] == ["app.py"]


def test_markdown_heading_rule_is_not_a_conflict(repo_dir: Path) -> None:
    root = make_repo(repo_dir)
    (root / "NOTES.md").write_text("Title\n=====\n\nSome text.\n", encoding="utf-8")
    assert check_conflict_markers(root) == []


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "repo_doctor", str(root), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_excluded_paths_are_skipped(repo_dir: Path) -> None:
    root = make_repo(repo_dir)
    vendor = root / "vendor"
    vendor.mkdir()
    (vendor / "bundle.min.js").write_bytes(b"x" * 200)
    assert check_large_files(root, max_size=64) != []
    assert check_large_files(root, max_size=64, exclude=["vendor/*"]) == []
    assert check_large_files(root, max_size=64, exclude=["*.min.js"]) == []


def test_parse_size_accepts_suffixes() -> None:
    assert parse_size("512") == 512
    assert parse_size("512KiB") == 512
    assert parse_size("2M") == 2048
    assert parse_size("1GiB") == 1024 * 1024


def test_parse_size_rejects_garbage() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        parse_size("big")


def test_cli_accepts_size_suffix(repo_dir: Path) -> None:
    root = make_repo(repo_dir)
    (root / "blob.bin").write_bytes(b"x" * 2048)
    result = run_cli(root, "--max-size", "1K", "--json")
    assert result.returncode == 1
    assert json.loads(result.stdout)[0]["check"] == "large-files"


def test_cli_reports_findings_and_exit_code(repo_dir: Path) -> None:
    root = make_repo(repo_dir)
    (root / "blob.bin").write_bytes(b"x" * 2048)
    result = run_cli(root, "--max-size", "1", "--json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload[0]["check"] == "large-files"


def test_cli_clean_repo_exits_zero(repo_dir: Path) -> None:
    result = run_cli(make_repo(repo_dir))
    assert result.returncode == 0
    assert "clean" in result.stdout
