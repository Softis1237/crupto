#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


def prune_run_dirs(reports_dir: Path, keep: int, dry_run: bool) -> list[Path]:
    run_dirs = sorted(
        (path for path in reports_dir.glob("run_*") if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    removed: list[Path] = []
    for path in run_dirs[keep:]:
        removed.append(path)
        if dry_run:
            print(f"[dry-run] would remove run directory {path}")
        else:
            shutil.rmtree(path, ignore_errors=True)
            print(f"[cleanup] removed run directory {path}")
    return removed


def prune_logs(log_dir: Path, keep: int, dry_run: bool) -> list[Path]:
    if not log_dir.exists():
        return []
    log_files = sorted(
        (path for path in log_dir.glob("*.log") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    removed: list[Path] = []
    for path in log_files[keep:]:
        removed.append(path)
        if dry_run:
            print(f"[dry-run] would remove log file {path}")
        else:
            path.unlink(missing_ok=True)
            print(f"[cleanup] removed log file {path}")
    return removed


EXCLUDE_DIRS = {".venv", ".git"}


def _is_excluded(path: Path, root: Path) -> bool:
    for name in EXCLUDE_DIRS:
        banned = (root / name).resolve()
        try:
            if path.resolve().is_relative_to(banned):
                return True
        except AttributeError:
            if str(banned) in str(path.resolve()):
                return True
    return False


def prune_pycache(root: Path, dry_run: bool) -> list[Path]:
    removed: list[Path] = []
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        if _is_excluded(current_path, root):
            dirs[:] = []
            continue

        for directory in list(dirs):
            if directory == "__pycache__":
                target = current_path / directory
                removed.append(target)
                if dry_run:
                    print(f"[dry-run] would remove cache directory {target}")
                else:
                    shutil.rmtree(target, ignore_errors=True)
                    print(f"[cleanup] removed cache directory {target}")
                dirs.remove(directory)

        for filename in files:
            if filename.endswith((".pyc", ".pyo")):
                target = current_path / filename
                removed.append(target)
                if dry_run:
                    print(f"[dry-run] would remove bytecode file {target}")
                else:
                    target.unlink(missing_ok=True)
                    print(f"[cleanup] removed bytecode file {target}")
    return removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean old run artifacts and temporary files.")
    parser.add_argument(
        "--keep-runs",
        type=int,
        default=2,
        help="number of recent run directories to keep (default: 2)",
    )
    parser.add_argument(
        "--keep-logs",
        type=int,
        default=5,
        help="number of recent log files to keep (default: 5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show actions without deleting anything",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    reports_dir = repo_root / "reports"
    logs_dir = repo_root / "logs"

    prune_run_dirs(reports_dir, keep=max(args.keep_runs, 0), dry_run=args.dry_run)
    prune_logs(logs_dir, keep=max(args.keep_logs, 0), dry_run=args.dry_run)
    prune_pycache(repo_root, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
