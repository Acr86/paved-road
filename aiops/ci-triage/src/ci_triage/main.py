"""ci-triage — classify a failed GitHub Actions run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from . import github, llm
from .rules import Classification, classify

app = typer.Typer(name="ci-triage", invoke_without_command=True, add_completion=False)


@app.callback()
def run(
    repo: str = typer.Option("", "--repo", help="owner/name (with --run-id)."),
    run_id: int = typer.Option(0, "--run-id", help="Failed workflow run id."),
    log_file: Path | None = typer.Option(
        None, "--log-file", help="Classify a local log file instead of a run."
    ),
    output: str = typer.Option("markdown", "--format", help="markdown or json."),
    use_llm: bool = typer.Option(
        True,
        "--llm/--no-llm",
        help="Add an LLM summary when ANTHROPIC_API_KEY is set (rules always run).",
    ),
) -> None:
    if log_file is not None:
        results = [("local-log", classify(log_file.read_text(encoding="utf-8", errors="replace")))]
    elif repo and run_id:
        jobs = github.fetch_failed_jobs(repo, run_id)
        if not jobs:
            typer.echo("no failed jobs found in the run", err=True)
            raise typer.Exit(code=1)
        results = [(job.name, classify(job.log_text)) for job in jobs]
    else:
        typer.echo("provide either --log-file or --repo with --run-id", err=True)
        raise typer.Exit(code=2)

    if output == "json":
        payload = [
            {
                "job": name,
                "category": c.category,
                "confidence": c.confidence,
                "owner_hint": c.owner_hint,
                "action": c.action,
                "evidence": c.evidence,
            }
            for name, c in results
        ]
        typer.echo(json.dumps(payload, indent=2))
        return

    for name, classification in results:
        _print_markdown(name, classification, use_llm)


def _print_markdown(job_name: str, c: Classification, use_llm: bool) -> None:
    lines = [
        f"## Triage: `{job_name}`",
        "",
        f"- **Category:** {c.category} (confidence: {c.confidence})",
        f"- **Likely owner:** {c.owner_hint}",
        f"- **Suggested action:** {c.action}",
        "",
    ]
    if c.evidence:
        lines += ["<details><summary>Evidence</summary>", "", "```"]
        lines += c.evidence
        lines += ["```", "", "</details>", ""]
    summary = llm.summarize(job_name, c) if use_llm else None
    if summary:
        lines += ["**Root-cause hypothesis (LLM):** " + summary, ""]
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    app()
