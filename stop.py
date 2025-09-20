#!/usr/bin/env python3
"""Stop backend and frontend dev servers using PID files."""
from __future__ import annotations

import contextlib
import os
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PID_DIR = ROOT / ".pids"
SERVICE_NAMES = ("backend", "frontend")
TIMEOUT_SECONDS = 10


def read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def kill_process_group(pid: int) -> bool:
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True

    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.3)

    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    return False


def stop_service(name: str) -> bool:
    pid_file = PID_DIR / f"{name}.pid"
    pid = read_pid(pid_file)
    if not pid:
        print(f"{name}: no PID file, skipping")
        return True

    print(f"{name}: stopping PID {pid}")
    success = kill_process_group(pid)
    if success:
        with contextlib.suppress(FileNotFoundError):
            pid_file.unlink()
        print(f"{name}: stopped")
    else:
        print(f"{name}: could not terminate", file=sys.stderr)
    return success


def main() -> int:
    if not PID_DIR.exists():
        print("No PID directory found; nothing to stop")
        return 0

    overall_success = True
    for service in SERVICE_NAMES:
        if not stop_service(service):
            overall_success = False

    return 0 if overall_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
