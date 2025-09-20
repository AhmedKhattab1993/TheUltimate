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
FORCE_TIMEOUT_SECONDS = 5


def read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None

def is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for_exit(pid: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_pid_alive(pid):
            return True
        time.sleep(0.3)
    return not is_pid_alive(pid)


def kill_process_group(pid: int) -> tuple[bool, bool]:
    if not is_pid_alive(pid):
        return True, False

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True, False
    except PermissionError:
        return False, False

    if wait_for_exit(pid, TIMEOUT_SECONDS):
        return True, False

    forced = True
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True, forced
    except PermissionError:
        return False, forced

    return wait_for_exit(pid, FORCE_TIMEOUT_SECONDS), forced


def stop_service(name: str) -> bool:
    pid_file = PID_DIR / f"{name}.pid"
    pid = read_pid(pid_file)
    if not pid:
        print(f"{name}: no PID file, skipping")
        return True

    if not is_pid_alive(pid):
        with contextlib.suppress(FileNotFoundError):
            pid_file.unlink()
        print(f"{name}: PID {pid} not running, cleaned up stale file")
        return True

    print(f"{name}: stopping PID {pid}")
    success, forced = kill_process_group(pid)
    if success:
        with contextlib.suppress(FileNotFoundError):
            pid_file.unlink()
        postfix = " (force killed)" if forced else ""
        print(f"{name}: stopped{postfix}")
    else:
        if forced:
            print(f"{name}: force kill failed", file=sys.stderr)
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
