"""Optional LLM-assisted summary.

Strictly additive: the deterministic classification stands on its own, and
this layer only writes a short narrative for humans when ANTHROPIC_API_KEY
is present. Dependency-free (urllib) so the tool stays a single small wheel.
"""

from __future__ import annotations

import json
import os
import urllib.request

from .rules import Classification

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"


def summarize(job_name: str, classification: Classification) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    prompt = (
        "You are a CI triage assistant. A pipeline job failed and a deterministic "
        "classifier already labelled it. Write a 2-3 sentence root-cause hypothesis "
        "for the engineer, based only on the evidence lines. Do not speculate beyond "
        "them and do not repeat the label.\n\n"
        f"Job: {job_name}\n"
        f"Category: {classification.category}\n"
        "Evidence:\n" + "\n".join(classification.evidence)
    )
    body = json.dumps(
        {
            "model": MODEL,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
        return "".join(
            block.get("text", "") for block in payload.get("content", [])
        ).strip() or None
    except Exception:  # noqa: BLE001 - the summary is optional by contract
        return None
