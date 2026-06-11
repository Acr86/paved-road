"""``platform`` — the paved-road golden-path CLI."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__, catalog, preview, render, repo, scaffold

app = typer.Typer(
    name="platform",
    help="Golden-path tooling: scaffold services, validate the catalog, manage previews.",
    no_args_is_help=True,
)
new_app = typer.Typer(
    help="Scaffold new resources from golden-path templates.", no_args_is_help=True
)
preview_app = typer.Typer(help="Manage ephemeral preview environments.", no_args_is_help=True)
catalog_app = typer.Typer(help="Catalog utilities.", no_args_is_help=True)
app.add_typer(new_app, name="new")
app.add_typer(preview_app, name="preview")
app.add_typer(catalog_app, name="catalog")

console = Console()
err_console = Console(stderr=True)


def _root() -> Path:
    try:
        return repo.find_repo_root()
    except repo.NotInsideRepoError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc


@app.callback()
def main_callback(
    version: bool = typer.Option(False, "--version", help="Print version and exit."),
) -> None:
    if version:
        console.print(f"platform {__version__}")
        raise typer.Exit()


@new_app.command("service")
def new_service(
    name: str = typer.Argument(..., help="Service name (kebab-case)."),
    template: str = typer.Option("fastapi-service", "--template", "-t"),
    owner: str = typer.Option(..., "--owner", "-o", help="Owning team."),
    tier: str = typer.Option("t3", "--tier", help="Criticality tier: t1, t2 or t3."),
    description: str = typer.Option(
        "A new service scaffolded from the golden path.", "--description", "-d"
    ),
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Scaffold a service: source tree, deploy manifests and catalog entry in one pass."""
    root = _root()
    try:
        service_dir = scaffold.new_service(
            root,
            name=name,
            template=template,
            owner=owner,
            tier=tier,
            description=description,
            port=port,
        )
    except scaffold.ScaffoldError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]created[/green] {service_dir.relative_to(root)}")
    console.print(f"[green]created[/green] deploy/kustomize/services/{name}")
    console.print(f"[green]created[/green] catalog/{name}.yaml")
    console.print()
    console.print("Next steps:")
    console.print(f"  1. cd services/{name} && uv run pytest")
    console.print("  2. open a pull request — CI builds, scans and publishes the image")
    console.print("  3. add the 'preview' label to get an ephemeral environment")
    console.print("  4. merge — GitOps deploys it; no further registration needed")


@app.command("list")
def list_entries() -> None:
    """List every catalog entry."""
    root = _root()
    try:
        entries = catalog.load_entries(root)
    except catalog.CatalogError as exc:
        _print_problems(exc.problems)
        raise typer.Exit(code=1) from exc

    table = Table(title=f"paved-road catalog ({len(entries)} entries)")
    table.add_column("name", style="bold")
    table.add_column("kind")
    table.add_column("owner")
    table.add_column("tier")
    table.add_column("lifecycle")
    table.add_column("description", overflow="fold")
    for entry in entries:
        table.add_row(
            entry.name,
            entry.kind.value,
            entry.owner,
            entry.tier.value,
            entry.lifecycle.value,
            entry.description,
        )
    console.print(table)


@app.command("info")
def info(name: str = typer.Argument(..., help="Catalog entry name.")) -> None:
    """Show one catalog entry in detail."""
    root = _root()
    try:
        entries = catalog.load_entries(root)
    except catalog.CatalogError as exc:
        _print_problems(exc.problems)
        raise typer.Exit(code=1) from exc
    match = next((e for e in entries if e.name == name), None)
    if match is None:
        err_console.print(f"[red]error:[/red] no catalog entry named {name!r}")
        raise typer.Exit(code=1)
    console.print_json(match.model_dump_json())


@app.command("validate")
def validate() -> None:
    """Validate the catalog: schema plus repository cross-checks. CI runs this too."""
    root = _root()
    try:
        entries = catalog.validate(root)
    except catalog.CatalogError as exc:
        _print_problems(exc.problems)
        raise typer.Exit(code=1) from exc
    console.print(f"[green]ok[/green] catalog is consistent ({len(entries)} entries)")


@catalog_app.command("render")
def catalog_render(
    output: Path = typer.Option(Path("dist/catalog/index.html"), "--output", "-o"),
) -> None:
    """Render the catalog as a static HTML page."""
    root = _root()
    try:
        entries = catalog.validate(root)
    except catalog.CatalogError as exc:
        _print_problems(exc.problems)
        raise typer.Exit(code=1) from exc
    destination = render.render_html(entries, root / output)
    console.print(f"[green]rendered[/green] {destination.relative_to(root)}")


@preview_app.command("create")
def preview_create(
    pr: int = typer.Option(..., "--pr", help="Pull request number."),
    ttl: int = typer.Option(7200, "--ttl-seconds", help="Time to live in seconds."),
) -> None:
    """Create a TTL-labelled preview namespace (normally done by the PR generator)."""
    name = preview.create_preview_namespace(pr, ttl)
    console.print(f"[green]created[/green] namespace {name} (ttl {ttl}s)")


@preview_app.command("list")
def preview_list() -> None:
    """List preview namespaces and their expiry state."""
    import time as _time

    namespaces = preview.list_preview_namespaces()
    now = _time.time()
    table = Table(title=f"preview environments ({len(namespaces)})")
    table.add_column("namespace", style="bold")
    table.add_column("expires-at (epoch)")
    table.add_column("state")
    for ns in namespaces:
        deadline = ns.labels.get(preview.EXPIRES_LABEL, "—")
        state = "[red]expired[/red]" if preview.expired(ns, now) else "[green]active[/green]"
        table.add_row(ns.name, deadline, state)
    console.print(table)


@preview_app.command("gc")
def preview_gc(
    dry_run: bool = typer.Option(False, "--dry-run", help="Report, do not delete."),
    orphans: bool = typer.Option(
        False,
        "--orphans",
        help="Also reclaim namespaces whose ArgoCD Application no longer exists "
        "(the in-cluster janitor runs with this flag).",
    ),
) -> None:
    """Garbage-collect preview namespaces: expired TTLs, and orphans with --orphans."""
    namespaces = preview.list_preview_namespaces()
    doomed = preview.select_expired(namespaces)
    if orphans:
        active = preview.list_application_destinations()
        already = {ns.name for ns in doomed}
        doomed += [
            ns for ns in preview.select_orphans(namespaces, active) if ns.name not in already
        ]
    broken = preview.select_unlabeled(namespaces)

    for ns in broken:
        err_console.print(
            f"[yellow]warning:[/yellow] {ns.name} has a missing or malformed "
            f"{preview.EXPIRES_LABEL} label — refusing to touch it (see RB-001)"
        )
    if not doomed:
        console.print("nothing to collect")
        return
    for ns in doomed:
        if dry_run:
            console.print(f"[yellow]would delete[/yellow] {ns.name}")
        else:
            preview.delete_namespace(ns.name)
            console.print(f"[red]deleted[/red] {ns.name}")


def _print_problems(problems: list[str]) -> None:
    err_console.print(f"[red]catalog validation failed ({len(problems)} problems):[/red]")
    for problem in problems:
        err_console.print(f"  - {problem}")


if __name__ == "__main__":
    sys.exit(app())
