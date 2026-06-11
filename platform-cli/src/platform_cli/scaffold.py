"""Golden-path scaffolding on top of Copier.

A template renders *relative to the repository root* and produces every
artifact a service needs in one pass: the service source tree, its
deployment manifests, and its catalog entry. There is no separate "register
the service" step to forget — if the template ran, the service exists
everywhere it needs to exist.

Copier (rather than cookiecutter) is load-bearing here: the rendered
``.copier-answers.yml`` inside each service records template provenance and
makes ``copier update`` possible, which is how template evolution propagates
to already-scaffolded services.
"""

from __future__ import annotations

from pathlib import Path

import copier

from . import repo


class ScaffoldError(RuntimeError):
    pass


def available_templates(root: Path) -> list[str]:
    tdir = repo.templates_dir(root)
    if not tdir.is_dir():
        return []
    return sorted(p.name for p in tdir.iterdir() if (p / "copier.yml").is_file())


def new_service(
    root: Path,
    name: str,
    template: str,
    owner: str,
    tier: str,
    description: str,
    port: int = 8000,
) -> Path:
    """Render the golden-path template for a new service. Returns the service dir."""
    template_path = repo.templates_dir(root) / template
    if not (template_path / "copier.yml").is_file():
        available = ", ".join(available_templates(root)) or "none"
        raise ScaffoldError(f"unknown template {template!r} (available: {available})")

    service_dir = repo.services_dir(root) / name
    if service_dir.exists():
        raise ScaffoldError(f"services/{name} already exists")
    catalog_entry = repo.catalog_dir(root) / f"{name}.yaml"
    if catalog_entry.exists():
        raise ScaffoldError(f"catalog/{name}.yaml already exists")

    copier.run_copy(
        src_path=str(template_path),
        dst_path=str(root),
        data={
            "service_name": name,
            "owner": owner,
            "tier": tier,
            "description": description,
            "port": port,
        },
        defaults=True,
        overwrite=False,
        unsafe=False,
        vcs_ref="HEAD",
    )

    if not service_dir.is_dir():
        raise ScaffoldError(
            f"template {template!r} rendered without creating services/{name} — "
            "the template is broken, not your input"
        )
    return service_dir
