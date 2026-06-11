"""Golden tests for the fastapi-service template.

We test the template by testing its output: render it into a fresh
repository fixture, assert every artifact a service needs actually exists,
and assert the result passes the same catalog validation CI enforces.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from platform_cli import catalog, scaffold

pytestmark = pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "templates" / "fastapi-service").is_dir(),
    reason="fastapi-service template not present",
)


@pytest.fixture()
def rendered(tmp_repo: Path) -> Path:
    scaffold.new_service(
        tmp_repo,
        name="demo-ledger",
        template="fastapi-service",
        owner="team-treasury",
        tier="t3",
        description="Golden-test rendering of the fastapi-service template.",
        port=8000,
    )
    return tmp_repo


class TestRenderedArtifacts:
    def test_all_three_artifact_groups_exist(self, rendered: Path) -> None:
        assert (rendered / "services" / "demo-ledger" / "pyproject.toml").is_file()
        assert (rendered / "services" / "demo-ledger" / "src" / "app" / "main.py").is_file()
        assert (rendered / "services" / "demo-ledger" / "Dockerfile").is_file()
        assert (rendered / "catalog" / "demo-ledger.yaml").is_file()
        base = rendered / "deploy" / "kustomize" / "services" / "demo-ledger"
        assert (base / "base" / "kustomization.yaml").is_file()
        assert (base / "overlays" / "local" / "kustomization.yaml").is_file()
        assert (base / "overlays" / "preview" / "kustomization.yaml").is_file()

    def test_no_unrendered_jinja_left_behind(self, rendered: Path) -> None:
        leftovers = [
            p for p in (rendered / "services" / "demo-ledger").rglob("*.jinja")
        ]
        assert leftovers == []

    def test_answers_file_records_provenance(self, rendered: Path) -> None:
        answers = yaml.safe_load(
            (rendered / "services" / "demo-ledger" / ".copier-answers.yml").read_text(
                encoding="utf-8"
            )
        )
        assert answers["service_name"] == "demo-ledger"
        assert answers["owner"] == "team-treasury"

    def test_rendered_repo_passes_catalog_validation(self, rendered: Path) -> None:
        entries = catalog.validate(rendered)
        assert [e.name for e in entries] == ["demo-ledger"]

    def test_deployment_pins_hardened_security_context(self, rendered: Path) -> None:
        deployment = yaml.safe_load(
            (
                rendered / "deploy" / "kustomize" / "services" / "demo-ledger"
                / "base" / "deployment.yaml"
            ).read_text(encoding="utf-8")
        )
        pod = deployment["spec"]["template"]["spec"]
        container = pod["containers"][0]
        assert pod["securityContext"]["runAsNonRoot"] is True
        assert container["securityContext"]["allowPrivilegeEscalation"] is False
        assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
        assert "limits" in container["resources"]


class TestScaffoldGuardrails:
    def test_scaffolding_twice_fails_cleanly(self, rendered: Path) -> None:
        with pytest.raises(scaffold.ScaffoldError, match="already exists"):
            scaffold.new_service(
                rendered,
                name="demo-ledger",
                template="fastapi-service",
                owner="team-treasury",
                tier="t3",
                description="Duplicate scaffold attempt must be rejected.",
            )

    def test_unknown_template_lists_available_ones(self, tmp_repo: Path) -> None:
        with pytest.raises(scaffold.ScaffoldError, match="fastapi-service"):
            scaffold.new_service(
                tmp_repo,
                name="demo-ledger",
                template="does-not-exist",
                owner="team-treasury",
                tier="t3",
                description="Unknown template must fail with guidance.",
            )


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_generated_service_test_suite_passes(rendered: Path) -> None:
    """The strongest golden assertion: the generated service's own tests pass."""
    service_dir = rendered / "services" / "demo-ledger"
    result = subprocess.run(
        ["uv", "run", "--extra", "dev", "--project", str(service_dir), "pytest"],
        cwd=service_dir,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
