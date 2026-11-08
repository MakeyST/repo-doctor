# repo-doctor

[![CI](https://github.com/MakeyST/repo-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/MakeyST/repo-doctor/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://github.com/MakeyST/repo-doctor)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A tiny, dependency-free command line tool that checks a repository checkout for
the hygiene problems that are easy to miss before you publish it.

| Check | Catches |
| --- | --- |
| `required-files` | missing README, LICENSE or `.gitignore` |
| `large-files` | files above the size limit (1 MiB by default) |
| `secrets` | AWS keys, GitHub/Slack tokens, private key blocks |
| `conflict-markers` | leftovers from an unresolved merge |

It only reads files, never writes, and never touches the network.

## Install

```bash
python -m pip install .
```

Or run it straight from a checkout without installing anything:

```bash
python -m repo_doctor .
```

## Usage

```bash
$ repo-doctor .
repo-doctor: 2 problem(s)
  large-files      assets/demo.gif            3.2 MiB exceeds 1.0 MiB
  secrets          config/local.py            possible AWS access key
```

```bash
$ repo-doctor path/to/repo --max-size 2M --json
[
  {
    "check": "large-files",
    "path": "assets/demo.gif",
    "message": "3.2 MiB exceeds 2.0 MiB"
  }
]
```

Options:

| Option | Meaning |
| --- | --- |
| `PATH` | repository root, defaults to `.` |
| `--max-size SIZE` | size limit for `large-files`, default `1024` (1 MiB); `K`, `M` and `G` suffixes are accepted |
| `--exclude GLOB` | skip paths matching the glob, repeatable |
| `--json` | machine-readable output |

Exit codes: `0` means clean, `1` means at least one finding, `2` means bad usage.

Vendored and generated directories (`node_modules`, `.venv`, `dist`, `build`,
`__pycache__` and friends) are skipped, so the output stays readable on large
checkouts.

## Limitations

- Only the working tree is inspected: `.git` and vendored directories are skipped.
- Symlinks are not followed.
- Secret patterns are heuristics, so a hit is a hint to check, not a verdict.

## Tests

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## License

MIT
