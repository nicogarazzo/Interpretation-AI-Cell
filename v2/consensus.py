"""
consensus.py — Deterministic weighted voting for the philosopher review panel.

Implements the voting protocol from shared/consensus-config.yml.
Pure Python, no LLM calls. Given three philosopher critique JSONs,
computes a weighted consensus verdict.
"""

from datetime import datetime, timezone

from .config import load_consensus_config

# ── Category mapping ────────────────────────────────────────────────────────
# Maps specific issue categories from philosopher output to the weight domains
# defined in consensus-config.yml.

CATEGORY_TO_DOMAIN = {
    # Wittgenstein's domain: idioms + pragmatics
    "idiom_literal": "idiom_resolution",
    "idiom_natural": "idiom_resolution",
    "pragmatic_force": "pragmatics",
    "pragmatic_loss": "pragmatics",
    "pragmatic_shift": "pragmatics",
    "speech_act_mismatch": "pragmatics",
    "contextual_mismatch": "pragmatics",
    # Frege's domain: tone, register, factual accuracy
    "tone_shift": "tone_and_style",
    "register_mismatch": "tone_and_style",
    "formality_error": "tone_and_style",
    "connotation_drift": "tone_and_style",
    "sinn_loss": "tone_and_style",
    "bedeutung_error": "factual_accuracy",
    # Quine's domain: ambiguity
    "inadvertent_disambiguation": "ambiguity",
    "ambiguity_introduced": "ambiguity",
    "scope_ambiguity": "ambiguity",
    "referential_opacity": "ambiguity",
    "lexical_polysemy_lost": "ambiguity",
}

# Verdict severity ordering for tie-breaking (most_conservative)
VERDICT_ORDER = {"approve": 0, "revise": 1, "block": 2}


def _get_dominant_domain(critique: dict) -> str | None:
    """Find the dominant issue domain in a critique (most issues in one domain)."""
    issues = critique.get("critique", {}).get("issues", [])
    if not issues:
        return None

    domain_counts: dict[str, int] = {}
    for issue in issues:
        cat = issue.get("category", "")
        domain = CATEGORY_TO_DOMAIN.get(cat)
        if domain:
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

    if not domain_counts:
        return None

    return max(domain_counts, key=domain_counts.get)


def _get_weight(philosopher: str, domain: str | None, config: dict) -> float:
    """Look up the philosopher's weight for the given domain."""
    if domain is None:
        return 1.0
    weights = config.get("weights", {})
    domain_weights = weights.get(domain, {})
    return domain_weights.get(philosopher, 1.0)


def compute_consensus(
    critiques: dict[str, dict],
    config: dict | None = None,
) -> dict:
    """Compute weighted consensus from philosopher critiques.

    Args:
        critiques: {"frege": {...}, "wittgenstein": {...}, "quine": {...}}
        config: consensus-config.yml content (loaded if None)

    Returns:
        verdict.json structure with result, votes, merged issues, etc.
    """
    if config is None:
        config = load_consensus_config()

    quorum = config.get("quorum", 3)
    max_rounds = config.get("max_rounds", 3)
    tie_breaking = config.get("tie_breaking", "most_conservative")

    # Collect votes with weights
    vote_scores: dict[str, float] = {"approve": 0.0, "revise": 0.0, "block": 0.0}
    votes_detail = {}

    for philosopher, critique in critiques.items():
        verdict = critique.get("verdict", "revise").lower()
        if verdict not in VERDICT_ORDER:
            verdict = "revise"

        confidence = critique.get("confidence", 0.5)
        dominant_domain = _get_dominant_domain(critique)
        weight = _get_weight(philosopher, dominant_domain, config)
        weighted_score = weight * confidence

        vote_scores[verdict] += weighted_score
        votes_detail[philosopher] = {
            "verdict": verdict,
            "confidence": confidence,
            "weight": weight,
            "weighted_score": round(weighted_score, 4),
            "dominant_domain": dominant_domain,
        }

    # Determine result
    if len(critiques) < quorum:
        # Timeout scenario: proceed with available
        on_timeout = config.get("escalation", {}).get("on_timeout", "proceed_with_available")
        if on_timeout == "proceed_with_available" and len(critiques) >= 2:
            pass  # Continue with available votes
        elif len(critiques) == 0:
            return _escalation_verdict(votes_detail, critiques, "no_responses")

    # Find winning verdict
    max_score = max(vote_scores.values())
    winners = [v for v, s in vote_scores.items() if s == max_score]

    if len(winners) == 1:
        result = winners[0]
    else:
        # Tie-breaking: most conservative wins
        if tie_breaking == "most_conservative":
            result = max(winners, key=lambda v: VERDICT_ORDER[v])
        else:
            result = winners[0]

    # Merge all issues from all critiques
    merged_issues = _merge_issues(critiques)

    # Build revision instructions if needed
    revision_instructions = ""
    if result == "revise":
        revision_instructions = _build_revision_instructions(merged_issues)

    # Check for unanimous block
    all_verdicts = [v.get("verdict") for v in votes_detail.values()]
    escalated = (
        all(v == "block" for v in all_verdicts)
        and len(all_verdicts) >= quorum
    )

    return {
        "_schema": "interpretation-ai-cell/consensus-verdict/v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy": config.get("strategy", "weighted"),
        "quorum_met": len(critiques) >= quorum,
        "result": result,
        "vote_scores": {k: round(v, 4) for k, v in vote_scores.items()},
        "votes": votes_detail,
        "merged_issues": merged_issues,
        "revision_instructions": revision_instructions,
        "escalated": escalated,
    }


def _merge_issues(critiques: dict[str, dict]) -> list[dict]:
    """Merge and deduplicate issues from all philosopher critiques."""
    merged = []
    for philosopher, critique in critiques.items():
        issues = critique.get("critique", {}).get("issues", [])
        for issue in issues:
            merged.append({
                "philosopher": philosopher,
                "severity": issue.get("severity", "minor"),
                "category": issue.get("category", ""),
                "explanation": issue.get("explanation", ""),
                "suggestion": issue.get("suggestion", ""),
                "span_source": issue.get("span_source", {}),
                "span_target": issue.get("span_target", {}),
            })

    # Sort: critical first, then major, then minor
    severity_order = {"critical": 0, "major": 1, "minor": 2}
    merged.sort(key=lambda i: severity_order.get(i["severity"], 3))
    return merged


def _build_revision_instructions(merged_issues: list[dict]) -> str:
    """Build structured revision instructions from merged issues."""
    if not merged_issues:
        return "Minor stylistic concerns only. Review philosopher notes."

    lines = ["Apply the following corrections:\n"]
    for i, issue in enumerate(merged_issues, 1):
        sev = issue["severity"].upper()
        cat = issue["category"]
        explanation = issue["explanation"]
        suggestion = issue.get("suggestion", "")

        line = f"{i}. [{sev}] ({cat}) {explanation}"
        if suggestion:
            line += f"\n   Suggestion: {suggestion}"
        lines.append(line)

    return "\n".join(lines)


def _escalation_verdict(votes_detail: dict, critiques: dict, reason: str) -> dict:
    """Return an escalation verdict when consensus cannot be reached."""
    return {
        "_schema": "interpretation-ai-cell/consensus-verdict/v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy": "escalation",
        "quorum_met": False,
        "result": "escalated",
        "vote_scores": {},
        "votes": votes_detail,
        "merged_issues": _merge_issues(critiques),
        "revision_instructions": "",
        "escalated": True,
        "escalation_reason": reason,
    }
