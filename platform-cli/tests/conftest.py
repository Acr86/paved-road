from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """A minimal platform repository: catalog/, services/, manifests, templates, git.

    Scaffolding renders templates from committed state (vcs_ref=HEAD), so the
    fixture commits the template copy — exactly the invariant the real repo has.
    """
    (tmp_path / "catalog").mkdir()
    (tmp_path / "services").mkdir()
    (tmp_path / "deploy" / "kustomize" / "services").mkdir(parents=True)

    template_src = REPO_ROOT / "templates" / "fastapi-service"
    if template_src.is_dir():
        shutil.copytree(template_src, tmp_path / "templates" / "fastapi-service")

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            env={
                "GIT_AUTHOR_NAME": "test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
                "PATH": __import__("os").environ["PATH"],
            },
        )

    git("init", "-b", "main")
    git("add", "-A")
    git("commit", "-m", "fixture", "--no-gpg-sign")
    return tmp_path


def write_entry(root: Path, name: str, **overrides: object) -> Path:
    """Write a valid catalog entry, overridable per test."""
    import yaml

    entry: dict[str, object] = {
        "name": name,
        "kind": "service",
        "owner": "team-payments",
        "description": "A test service used by the catalog test-suite.",
        "tier": "t3",
        "lifecycle": "experimental",
    }
    entry.update(overrides)
    path = root / "catalog" / f"{name}.yaml"
    path.write_text(yaml.safe_dump(entry), encoding="utf-8")
    return path
