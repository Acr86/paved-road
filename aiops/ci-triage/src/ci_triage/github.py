"""Fetch failed-job logs from a GitHub Actions run.

Uses the `gh` CLI (present on every GitHub runner and most laptops) instead
of carrying an HTTP client and a token-handling code path of our own.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class FailedJob:
    name: str
    log_text: str


def _gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return result.stdout


def fetch_failed_jobs(repo: str, run_id: int) -> list[FailedJob]:
    raw = _gh("api", f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")
    jobs = json.loads(raw).get("jobs", [])
    failed = [j for j in jobs if j.get("conclusion") == "failure"]
    out: list[FailedJob] = []
    for job in failed:
        try:
            log_text = _gh("api", f"repos/{repo}/actions/jobs/{job['id']}/logs")
        except subprocess.CalledProcessError:
            log_text = ""
        out.append(FailedJob(name=job.get("name", "unknown"), log_text=log_text))
    return out
