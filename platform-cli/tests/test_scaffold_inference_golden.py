"""Golden tests for the inference-service template.

Same discipline as the fastapi-service golden tests — test the template by
testing its output — plus the parts of the inference contract that other
platform components depend on: the metric names the shared alert rules
select on, and the probe/provenance shape the inference policies enforce.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from platform_cli import catalog, scaffold

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not (REPO_ROOT / "templates" / "inference-service").is_dir(),
    reason="inference-service template not present",
)

NAME = "demo-embedder"

# The alert rules in observability/alerts/inference.yaml select on these.
# Renaming one in the template without updating the alerts blinds them.
CONTRACT_METRICS = (
    "inference_duration_seconds",
    "inference_batch_size",
    "inference_model_loaded",
    "inference_model_info",
    "inference_max_batch",
    "inference_index_vectors",
)


@pytest.fixture()
def rendered(tmp_repo: Path) -> Path:
    scaffold.new_service(
        tmp_repo,
        name=NAME,
        template="inference-service",
        owner="team-ml",
        tier="t3",
        description="Golden-test rendering of the inference-service template.",
        port=8000,
    )
    return tmp_repo


def _deployment(root: Path) -> dict:
    path = root / "deploy" / "kustomize" / "services" / NAME / "base" / "deployment.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class TestRenderedArtifacts:
    def test_all_three_artifact_groups_exist(self, rendered: Path) -> None:
        svc = rendered / "services" / NAME
        for rel in ("pyproject.toml", "Dockerfile", "src/app/main.py", "src/app/embedder.py"):
            assert (svc / rel).is_file(), rel
        assert (rendered / "catalog" / f"{NAME}.yaml").is_file()
        overlays = rendered / "deploy" / "kustomize" / "services" / NAME / "overlays"
        for overlay in ("local", "preview", "gpu"):
            assert (overlays / overlay / "kustomization.yaml").is_file(), overlay

    def test_no_unrendered_jinja_left_behind(self, rendered: Path) -> None:
        leftovers = list((rendered / "services" / NAME).rglob("*.jinja"))
        leftovers += list((rendered / "deploy").rglob("*.jinja"))
        assert leftovers == []

    def test_catalog_entry_records_the_template(self, rendered: Path) -> None:
        entries = catalog.validate(rendered)
        assert [(e.name, e.template) for e in entries] == [(NAME, "inference-service")]


class TestInferenceContract:
    def test_deployment_opts_into_inference_policies(self, rendered: Path) -> None:
        template = _deployment(rendered)["spec"]["template"]
        assert template["metadata"]["labels"]["pavedroad.dev/workload"] == "inference"
        assert template["metadata"]["annotations"]["pavedroad.dev/model"] == "hashing@v1"

    def test_model_load_is_absorbed_by_startup_probe_not_liveness(self, rendered: Path) -> None:
        container = _deployment(rendered)["spec"]["template"]["spec"]["containers"][0]
        assert container["startupProbe"]["httpGet"]["path"] == "/readyz"
        assert container["readinessProbe"]["httpGet"]["path"] == "/readyz"
        # Liveness must never depend on the model, or a slow load restarts forever.
        assert container["livenessProbe"]["httpGet"]["path"] == "/healthz"

    def test_read_only_root_has_explicit_writable_volumes(self, rendered: Path) -> None:
        pod = _deployment(rendered)["spec"]["template"]["spec"]
        container = pod["containers"][0]
        assert container["securityContext"]["readOnlyRootFilesystem"] is True
        mounts = {m["mountPath"] for m in container["volumeMounts"]}
        assert {"/models", "/tmp"} <= mounts
        assert all("sizeLimit" in v["emptyDir"] for v in pod["volumes"])

    def test_service_emits_every_metric_the_alerts_select_on(self, rendered: Path) -> None:
        source = (rendered / "services" / NAME / "src" / "app" / "metrics.py").read_text(
            encoding="utf-8"
        )
        for metric in CONTRACT_METRICS:
            assert f'"{metric}"' in source, f"template no longer defines {metric}"

    def test_shared_alerts_still_select_on_the_contract(self) -> None:
        rules = (REPO_ROOT / "observability" / "alerts" / "inference.yaml").read_text(
            encoding="utf-8"
        )
        for metric in ("inference_model_loaded", "inference_duration_seconds_bucket"):
            assert metric in rules


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_generated_service_test_suite_passes(rendered: Path) -> None:
    """The strongest golden assertion: the generated service's own tests pass."""
    service_dir = rendered / "services" / NAME
    result = subprocess.run(
        ["uv", "run", "--extra", "dev", "--project", str(service_dir), "pytest"],
        cwd=service_dir,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


@pytest.mark.parametrize("template", ["fastapi-service", "inference-service"])
def test_description_with_yaml_special_characters_renders_valid_catalog(
    tmp_repo: Path, template: str
) -> None:
    # Regression: an unquoted description containing ": " rendered invalid YAML.
    scaffold.new_service(
        tmp_repo,
        name="colon-check",
        template=template,
        owner="team-ml",
        tier="t3",
        description="Reference service: embeddings, search & more # not a comment",
    )
    entries = catalog.validate(tmp_repo)
    assert entries[0].description == (
        "Reference service: embeddings, search & more # not a comment"
    )
