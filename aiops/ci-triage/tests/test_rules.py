"""The taxonomy is tested against committed log fixtures.

Every fixture is a (trimmed) real-shaped GitHub Actions log. When a new
failure mode shows up in production, the fix is: add the fixture, add the
rule, watch the test go green — the classifier never regresses silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ci_triage.rules import classify

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestTaxonomy:
    @pytest.mark.parametrize(
        ("fixture", "category"),
        [
            ("pytest-failure.log", "test-failure"),
            ("trivy-gate.log", "vulnerability-gate"),
            ("network-flake.log", "infra-flake"),
            ("conftest-policy.log", "policy-violation"),
        ],
    )
    def test_fixture_classifies_as(self, fixture: str, category: str) -> None:
        result = classify(load(fixture))
        assert result.category == category
        assert result.evidence, "a classification without evidence is a guess"

    def test_priority_specific_beats_generic(self) -> None:
        # A pytest failure that ALSO contains a stray network line must
        # classify by the higher-priority specific category ordering:
        # vulnerability/policy/test rules outrank the flake rule.
        mixed = load("pytest-failure.log") + "\nconnection reset by peer\n"
        assert classify(mixed).category == "test-failure"

    def test_unknown_logs_admit_ignorance(self) -> None:
        result = classify(load("unknown.log"))
        assert result.category == "unclassified"
        assert result.confidence == "none"
        # It must still hand the human the tail of the log to start from.
        assert result.evidence

    def test_two_evidence_lines_mean_high_confidence(self) -> None:
        result = classify(load("pytest-failure.log"))
        assert result.confidence == "high"

    def test_empty_log_does_not_crash(self) -> None:
        result = classify("")
        assert result.category == "unclassified"
