"""Preview environment lifecycle.

Preview environments are namespaces named ``pr-<number>`` labelled
``andamio.dev/preview=true``. Two independent rules reclaim them:

- **TTL**: an ``andamio.dev/expires-at=<unix epoch>`` label in the past.
  Set by ``platform preview create``; an absolute deadline, never sliding.
- **Orphan**: the ApplicationSet pruned the PR's Application (the PR was
  closed or unlabelled) but the namespace it deployed into remains — ArgoCD
  does not delete namespaces it created. Orphans are reclaimed only after a
  grace period, measured from namespace creation.

The janitor CronJob runs this exact module (same container image as the
CLI), so the decision logic is unit-tested without a cluster — including the
cases that matter most: namespaces that must NOT be deleted.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime

PREVIEW_LABEL = "andamio.dev/preview"
EXPIRES_LABEL = "andamio.dev/expires-at"
ORPHAN_GRACE_SECONDS = 1800


@dataclass(frozen=True)
class Namespace:
    name: str
    labels: dict[str, str]
    created_at: float | None = field(default=None)


def is_preview(ns: Namespace) -> bool:
    return ns.labels.get(PREVIEW_LABEL) == "true" and ns.name.startswith("pr-")


def expired(ns: Namespace, now: float) -> bool:
    """A preview namespace is expired only when its deadline is in the past.

    A namespace without a parseable deadline is NOT expired: deleting on
    missing metadata turns a labeling bug into an outage. The janitor reports
    those instead.
    """
    if not is_preview(ns):
        return False
    raw = ns.labels.get(EXPIRES_LABEL)
    if raw is None:
        return False
    try:
        deadline = float(raw)
    except ValueError:
        return False
    return deadline < now


def select_expired(namespaces: list[Namespace], now: float | None = None) -> list[Namespace]:
    moment = time.time() if now is None else now
    return [ns for ns in namespaces if expired(ns, moment)]


def select_unlabeled(namespaces: list[Namespace]) -> list[Namespace]:
    """Preview namespaces carrying a malformed deadline — report, never auto-delete."""
    out: list[Namespace] = []
    for ns in namespaces:
        if not is_preview(ns):
            continue
        raw = ns.labels.get(EXPIRES_LABEL)
        if raw is None:
            continue
        try:
            float(raw)
        except ValueError:
            out.append(ns)
    return out


def select_orphans(
    namespaces: list[Namespace],
    active_destinations: set[str],
    now: float | None = None,
    grace_seconds: int = ORPHAN_GRACE_SECONDS,
) -> list[Namespace]:
    """Preview namespaces no Application deploys into anymore.

    ``active_destinations`` is the set of destination namespaces of the
    currently existing ArgoCD Applications. The grace period prevents a race
    against a namespace that was just created and whose Application has not
    synced yet — and means a transient ArgoCD outage (empty app list) cannot
    mass-delete fresh environments.
    """
    moment = time.time() if now is None else now
    orphans: list[Namespace] = []
    for ns in namespaces:
        if not is_preview(ns):
            continue
        if ns.name in active_destinations:
            continue
        if ns.created_at is None or (moment - ns.created_at) < grace_seconds:
            continue
        orphans.append(ns)
    return orphans


# --- kubectl integration (thin, replaceable) -------------------------------


def _kubectl(*args: str) -> str:
    result = subprocess.run(
        ["kubectl", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def list_preview_namespaces() -> list[Namespace]:
    raw = _kubectl(
        "get", "namespaces",
        "-l", f"{PREVIEW_LABEL}=true",
        "-o", "json",
    )
    items = json.loads(raw).get("items", [])
    return [
        Namespace(
            name=item["metadata"]["name"],
            labels=item["metadata"].get("labels", {}) or {},
            created_at=_parse_k8s_timestamp(item["metadata"].get("creationTimestamp")),
        )
        for item in items
    ]


def _parse_k8s_timestamp(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def list_application_destinations(argocd_namespace: str = "argocd") -> set[str]:
    """Destination namespaces of every existing ArgoCD Application."""
    raw = _kubectl(
        "get", "applications.argoproj.io",
        "-n", argocd_namespace,
        "-o", "json",
    )
    items = json.loads(raw).get("items", [])
    return {
        item.get("spec", {}).get("destination", {}).get("namespace", "")
        for item in items
    }


def create_preview_namespace(pr_number: int, ttl_seconds: int) -> str:
    name = f"pr-{pr_number}"
    deadline = int(time.time()) + ttl_seconds
    _kubectl("create", "namespace", name)
    _kubectl(
        "label", "namespace", name,
        f"{PREVIEW_LABEL}=true",
        f"{EXPIRES_LABEL}={deadline}",
        "--overwrite",
    )
    return name


def delete_namespace(name: str) -> None:
    _kubectl("delete", "namespace", name, "--wait=false")
