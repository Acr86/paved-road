from __future__ import annotations

from pathlib import Path

import pytest

from platform_cli import catalog
from tests.conftest import write_entry


def _mkservice(root: Path, name: str) -> None:
    (root / "services" / name).mkdir(parents=True)
    (root / "deploy" / "kustomize" / "services" / name).mkdir(parents=True)


class TestSchema:
    def test_valid_entry_loads(self, tmp_repo: Path) -> None:
        write_entry(tmp_repo, "fx-rates")
        _mkservice(tmp_repo, "fx-rates")
        entries = catalog.validate(tmp_repo)
        assert [e.name for e in entries] == ["fx-rates"]

    def test_rejects_non_kebab_name(self, tmp_repo: Path) -> None:
        write_entry(tmp_repo, "FxRates")
        with pytest.raises(catalog.CatalogError, match="kebab-case"):
            catalog.load_entries(tmp_repo)

    def test_rejects_unknown_fields(self, tmp_repo: Path) -> None:
        write_entry(tmp_repo, "fx-rates", flavor="vanilla")
        with pytest.raises(catalog.CatalogError, match="flavor"):
            catalog.load_entries(tmp_repo)

    def test_entry_name_must_match_file_name(self, tmp_repo: Path) -> None:
        path = write_entry(tmp_repo, "fx-rates")
        path.rename(tmp_repo / "catalog" / "other-name.yaml")
        with pytest.raises(catalog.CatalogError, match="must match the file name"):
            catalog.load_entries(tmp_repo)


class TestCrossChecks:
    def test_service_dir_without_catalog_entry_fails(self, tmp_repo: Path) -> None:
        _mkservice(tmp_repo, "ghost-service")
        with pytest.raises(catalog.CatalogError, match="has no catalog entry"):
            catalog.validate(tmp_repo)

    def test_catalog_entry_without_service_dir_fails(self, tmp_repo: Path) -> None:
        write_entry(tmp_repo, "vapor-service")
        with pytest.raises(catalog.CatalogError, match="services/vapor-service/ is missing"):
            catalog.validate(tmp_repo)

    def test_service_without_deploy_manifests_fails(self, tmp_repo: Path) -> None:
        write_entry(tmp_repo, "fx-rates")
        (tmp_repo / "services" / "fx-rates").mkdir(parents=True)
        with pytest.raises(catalog.CatalogError, match="would never deploy"):
            catalog.validate(tmp_repo)

    def test_tier2_requires_runbook(self, tmp_repo: Path) -> None:
        write_entry(tmp_repo, "fx-rates", tier="t2")
        _mkservice(tmp_repo, "fx-rates")
        with pytest.raises(catalog.CatalogError, match="must link a runbook"):
            catalog.validate(tmp_repo)

    def test_tier1_requires_dashboard(self, tmp_repo: Path) -> None:
        runbook = tmp_repo / "docs" / "runbooks" / "rb.md"
        runbook.parent.mkdir(parents=True)
        runbook.write_text("# rb", encoding="utf-8")
        write_entry(
            tmp_repo, "fx-rates", tier="t1",
            links={"runbook": "docs/runbooks/rb.md"},
        )
        _mkservice(tmp_repo, "fx-rates")
        with pytest.raises(catalog.CatalogError, match="must link a dashboard"):
            catalog.validate(tmp_repo)

    def test_runbook_link_must_exist_on_disk(self, tmp_repo: Path) -> None:
        write_entry(
            tmp_repo, "fx-rates", tier="t2",
            links={"runbook": "docs/runbooks/does-not-exist.md"},
        )
        _mkservice(tmp_repo, "fx-rates")
        with pytest.raises(catalog.CatalogError, match="does not exist in the repository"):
            catalog.validate(tmp_repo)

    def test_tool_entries_need_no_service_dir(self, tmp_repo: Path) -> None:
        write_entry(tmp_repo, "platform-cli", kind="tool")
        entries = catalog.validate(tmp_repo)
        assert entries[0].kind is catalog.Kind.TOOL
