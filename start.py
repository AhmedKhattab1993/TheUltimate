#!/usr/bin/env python3
"""Start backend and frontend dev servers with PID tracking."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent
PID_DIR = ROOT / ".pids"

SERVICE_CONFIG = {
    "backend": {
        "cmd": ["python3", "run.py"],
        "cwd": ROOT / "backend",
        "log": ROOT / "backend.log",
    },
    "frontend": {
        "cmd": ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"],
        "cwd": ROOT / "frontend",
        "log": ROOT / "frontend.log",
    },
}


def ensure_pid_dir() -> None:
    PID_DIR.mkdir(exist_ok=True)


def read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start_service(name: str, config: Dict[str, Path | List[str]]) -> int:
    pid_file = PID_DIR / f"{name}.pid"
    existing_pid = read_pid(pid_file)
    if existing_pid and is_running(existing_pid):
        print(f"{name}: already running with PID {existing_pid}")
        return existing_pid

    log_path = config["log"]
    log_file = open(log_path, "ab", buffering=0)
    process = subprocess.Popen(
        config["cmd"],
        cwd=config["cwd"],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    pid_file.write_text(str(process.pid))
    print(f"{name}: started (PID {process.pid}) -> logging to {log_path}")
    time.sleep(0.2)
    return process.pid


def main() -> int:
    ensure_pid_dir()
    for service_name, cfg in SERVICE_CONFIG.items():
        try:
            start_service(service_name, cfg)
        except FileNotFoundError as exc:
            print(f"{service_name}: failed to start ({exc})", file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"{service_name}: unexpected error {exc}", file=sys.stderr)
            return 1

    print("All services launched. Use python3 stop.py or make stop to shut them down.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
