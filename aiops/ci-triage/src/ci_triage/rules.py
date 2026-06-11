"""Deterministic failure taxonomy.

Rules run in priority order and the first category with evidence wins.
Determinism is the point: the same log always classifies the same way, the
rules are unit-tested against committed log fixtures, and there is no model
in the loop for the 90% of failures that pattern-match cleanly. The LLM
(optional, see llm.py) only ever summarizes — it never overrides a rule.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_EVIDENCE_LINES = 8


@dataclass(frozen=True)
class Rule:
    category: str
    owner_hint: str
    action: str
    patterns: tuple[re.Pattern[str], ...]


def _compile(*patterns: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p, re.IGNORECASE) for p in patterns)


# Priority order matters: a pytest assertion inside a docker build log is a
# test failure, not a build failure — the more specific category goes first.
RULES: tuple[Rule, ...] = (
    Rule(
        category="vulnerability-gate",
        owner_hint="service owner (security gate)",
        action="A scanner blocked the pipeline. Check the CVE table in the Trivy step; "
        "bump the base image or the vulnerable dependency. Do not suppress the gate.",
        patterns=_compile(
            r"Total: \d+ \((HIGH|CRITICAL): [1-9]",
            r"vulnerab\w+ .* exceeded .* severity",
        ),
    ),
    Rule(
        category="policy-violation",
        owner_hint="change author (policy gate)",
        action="A rendered manifest or Terraform plan violates policy-as-code. The deny "
        "message names the rule; fix the resource, not the policy.",
        patterns=_compile(
            r"FAIL - .*\.yaml - main - ",
            r"Failed checks: [1-9]",
            r"\d+ tests?, \d+ passed, .*[1-9] failures?",
        ),
    ),
    Rule(
        category="test-failure",
        owner_hint="change author",
        action="A test asserts the new behavior is wrong (or the test is stale). "
        "Reproduce locally with the same command the job ran.",
        patterns=_compile(
            r"^FAILED .+::",
            r"\bAssertionError\b",
            r"=+ .*\d+ failed.* =+",
            r"^E\s+assert ",
        ),
    ),
    Rule(
        category="dependency-resolution",
        owner_hint="change author",
        action="The resolver cannot satisfy the dependency set. Check the lockfile is "
        "committed and consistent; pin or relax the conflicting constraint.",
        patterns=_compile(
            r"No solution found when resolving",
            r"ResolutionImpossible",
            r"Could not find a version that satisfies",
            r"failed to resolve dependencies",
        ),
    ),
    Rule(
        category="docker-build",
        owner_hint="change author",
        action="The image build failed before any test ran. Reproduce with "
        "`docker build` locally; the failing Dockerfile line is in the evidence.",
        patterns=_compile(
            r"failed to solve",
            r"dockerfile parse error",
            r"executor failed running",
            r"ERROR: failed to build",
        ),
    ),
    Rule(
        category="kubernetes-rollout",
        owner_hint="platform team",
        action="The workload deployed but never became ready. Look for image pull "
        "errors or crash loops; `kubectl describe pod` output usually follows.",
        patterns=_compile(
            r"ImagePullBackOff",
            r"CrashLoopBackOff",
            r"error: timed out waiting for the condition",
            r"rollout status.*deadline exceeded",
        ),
    ),
    Rule(
        category="infra-flake",
        owner_hint="platform team (retry first)",
        action="Network or runner turbulence, not your change. Retry the job once; "
        "if it recurs at this step, open an infra issue with both run links.",
        patterns=_compile(
            r"connection reset by peer",
            r"TLS handshake timeout",
            r"temporary failure in name resolution",
            r"Could not resolve host",
            r"503 Service Unavailable",
            r"i/o timeout",
            r"rate limit exceeded",
        ),
    ),
    Rule(
        category="timeout",
        owner_hint="change author or platform team",
        action="The job hit its time budget. If the work grew legitimately, raise the "
        "timeout in the workflow; if not, something hung — check the last line of output.",
        patterns=_compile(
            r"exceeded the maximum execution time",
            r"The operation was canceled",
            r"timeout-minutes",
        ),
    ),
    Rule(
        category="lint",
        owner_hint="change author",
        action="Mechanical: run the formatter/linter locally and commit the result.",
        patterns=_compile(
            r"would reformat",
            r"ruff check.*error",
            r"\bSC\d{4}\b",
            r"actionlint",
        ),
    ),
)

UNCLASSIFIED = Rule(
    category="unclassified",
    owner_hint="change author",
    action="No rule matched. Read the last failing step's output; if a pattern emerges, "
    "teach it to the taxonomy in aiops/ci-triage/src/ci_triage/rules.py.",
    patterns=(),
)


@dataclass(frozen=True)
class Classification:
    category: str
    owner_hint: str
    action: str
    evidence: list[str] = field(default_factory=list)

    @property
    def confidence(self) -> str:
        if self.category == "unclassified":
            return "none"
        return "high" if len(self.evidence) >= 2 else "medium"


def classify(log_text: str) -> Classification:
    """First rule (in priority order) with evidence wins."""
    lines = log_text.splitlines()
    for rule in RULES:
        evidence: list[str] = []
        for line in lines:
            if any(p.search(line) for p in rule.patterns):
                evidence.append(line.strip()[:300])
                if len(evidence) >= MAX_EVIDENCE_LINES:
                    break
        if evidence:
            return Classification(
                category=rule.category,
                owner_hint=rule.owner_hint,
                action=rule.action,
                evidence=evidence,
            )
    return Classification(
        category=UNCLASSIFIED.category,
        owner_hint=UNCLASSIFIED.owner_hint,
        action=UNCLASSIFIED.action,
        evidence=lines[-5:] if lines else [],
    )
