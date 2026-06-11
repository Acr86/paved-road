"""The janitor's TTL decision logic.

The most important assertions here are the negative ones: a garbage
collector that deletes the wrong namespace turns a cost-saving feature into
an outage, so 'must NOT delete' cases get first-class coverage.
"""

from __future__ import annotations

from platform_cli.preview import (
    EXPIRES_LABEL,
    PREVIEW_LABEL,
    Namespace,
    select_expired,
    select_orphans,
    select_unlabeled,
)

NOW = 1_750_000_000.0


def ns(name: str, created_at: float | None = None, **labels: str) -> Namespace:
    return Namespace(name=name, labels=labels, created_at=created_at)


def preview_ns(name: str, expires_at: float) -> Namespace:
    return ns(name, **{PREVIEW_LABEL: "true", EXPIRES_LABEL: str(expires_at)})


class TestExpiredSelection:
    def test_expired_preview_is_selected(self) -> None:
        doomed = select_expired([preview_ns("pr-42", NOW - 60)], now=NOW)
        assert [n.name for n in doomed] == ["pr-42"]

    def test_active_preview_is_not_selected(self) -> None:
        assert select_expired([preview_ns("pr-42", NOW + 3600)], now=NOW) == []

    def test_deadline_exactly_now_is_not_expired(self) -> None:
        assert select_expired([preview_ns("pr-42", NOW)], now=NOW) == []

    def test_non_preview_namespace_is_never_selected(self) -> None:
        # Even with a past deadline label, a namespace not labelled as a
        # preview (or not named pr-*) must never be collected.
        candidates = [
            ns("kube-system", **{EXPIRES_LABEL: str(NOW - 999)}),
            ns("production", **{PREVIEW_LABEL: "true", EXPIRES_LABEL: str(NOW - 999)}),
        ]
        assert select_expired(candidates, now=NOW) == []

    def test_missing_deadline_is_not_deleted(self) -> None:
        broken = ns("pr-7", **{PREVIEW_LABEL: "true"})
        assert select_expired([broken], now=NOW) == []

    def test_malformed_deadline_is_not_deleted(self) -> None:
        broken = ns("pr-7", **{PREVIEW_LABEL: "true", EXPIRES_LABEL: "tomorrow"})
        assert select_expired([broken], now=NOW) == []


class TestUnlabeledReporting:
    def test_malformed_deadline_is_reported(self) -> None:
        namespaces = [
            ns("pr-2", **{PREVIEW_LABEL: "true", EXPIRES_LABEL: "not-a-number"}),
            preview_ns("pr-3", NOW + 100),
        ]
        assert [n.name for n in select_unlabeled(namespaces)] == ["pr-2"]

    def test_missing_deadline_is_normal_not_reported(self) -> None:
        # ApplicationSet-created namespaces carry no TTL label: the orphan
        # rule reclaims them, so a missing deadline is not an anomaly.
        assert select_unlabeled([ns("pr-1", **{PREVIEW_LABEL: "true"})]) == []


class TestOrphanSelection:
    GRACE = 1800

    def _orphan(self, name: str, age_seconds: float) -> Namespace:
        return ns(name, created_at=NOW - age_seconds, **{PREVIEW_LABEL: "true"})

    def test_orphan_past_grace_is_selected(self) -> None:
        orphan = self._orphan("pr-9", age_seconds=self.GRACE + 60)
        assert select_orphans([orphan], active_destinations=set(), now=NOW) == [orphan]

    def test_namespace_with_live_application_is_not_an_orphan(self) -> None:
        candidate = self._orphan("pr-9", age_seconds=self.GRACE + 60)
        assert select_orphans([candidate], active_destinations={"pr-9"}, now=NOW) == []

    def test_fresh_namespace_is_protected_by_grace_period(self) -> None:
        # The Application for a brand-new PR may not have synced yet; a
        # transient empty app list must not reap environments born minutes ago.
        fresh = self._orphan("pr-9", age_seconds=60)
        assert select_orphans([fresh], active_destinations=set(), now=NOW) == []

    def test_unknown_creation_time_is_never_reaped(self) -> None:
        unknown = ns("pr-9", **{PREVIEW_LABEL: "true"})
        assert select_orphans([unknown], active_destinations=set(), now=NOW) == []

    def test_non_preview_namespace_is_never_an_orphan(self) -> None:
        system = ns("kube-system", created_at=NOW - 999_999)
        assert select_orphans([system], active_destinations=set(), now=NOW) == []
