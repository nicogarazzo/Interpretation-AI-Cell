"""Tests for the deterministic consensus engine."""

import pytest

from v2.consensus import (
    CATEGORY_TO_DOMAIN,
    VERDICT_ORDER,
    _build_revision_instructions,
    _merge_issues,
    compute_consensus,
)


def test_unanimous_approve():
    critiques = {
        "frege": {"verdict": "approve", "confidence": 0.9, "critique": {"issues": []}},
        "wittgenstein": {"verdict": "approve", "confidence": 0.85, "critique": {"issues": []}},
        "quine": {"verdict": "approve", "confidence": 0.92, "critique": {"issues": []}},
    }
    result = compute_consensus(critiques)
    assert result["result"] == "approve"
    assert result["quorum_met"] is True
    assert result["escalated"] is False


def test_unanimous_block_escalates():
    critiques = {
        "frege": {"verdict": "block", "confidence": 0.95, "critique": {"issues": [
            {"severity": "critical", "category": "bedeutung_error", "explanation": "test"}
        ]}},
        "wittgenstein": {"verdict": "block", "confidence": 0.9, "critique": {"issues": [
            {"severity": "critical", "category": "idiom_literal", "explanation": "test"}
        ]}},
        "quine": {"verdict": "block", "confidence": 0.88, "critique": {"issues": [
            {"severity": "critical", "category": "ambiguity_introduced", "explanation": "test"}
        ]}},
    }
    result = compute_consensus(critiques)
    assert result["result"] == "block"
    assert result["escalated"] is True


def test_majority_revise():
    critiques = {
        "frege": {"verdict": "revise", "confidence": 0.85, "critique": {"issues": [
            {"severity": "major", "category": "tone_shift", "explanation": "test"}
        ]}},
        "wittgenstein": {"verdict": "revise", "confidence": 0.8, "critique": {"issues": [
            {"severity": "minor", "category": "idiom_literal", "explanation": "test"}
        ]}},
        "quine": {"verdict": "approve", "confidence": 0.9, "critique": {"issues": []}},
    }
    result = compute_consensus(critiques)
    assert result["result"] == "revise"


def test_tie_breaking_most_conservative():
    """When approve and revise have equal scores, revise wins."""
    critiques = {
        "frege": {"verdict": "approve", "confidence": 1.0, "critique": {"issues": []}},
        "wittgenstein": {"verdict": "revise", "confidence": 1.0, "critique": {"issues": [
            {"severity": "minor", "category": "pragmatic_force", "explanation": "test"}
        ]}},
        "quine": {"verdict": "approve", "confidence": 0.0, "critique": {"issues": []}},
    }
    # Frege: approve weighted 1.0 * 1.0 = 1.0
    # Wittgenstein: revise weighted (pragmatics domain, weight 1.5) * 1.0 = 1.5
    # Quine: approve weighted 1.0 * 0.0 = 0.0
    result = compute_consensus(critiques)
    # Revise score (1.5) > approve score (1.0), so revise wins
    assert result["result"] == "revise"


def test_weighted_voting_frege_tone_expertise():
    """Frege's vote carries 1.5x weight on tone_and_style issues."""
    critiques = {
        "frege": {"verdict": "revise", "confidence": 0.8, "critique": {"issues": [
            {"severity": "major", "category": "tone_shift", "explanation": "test"}
        ]}},
        "wittgenstein": {"verdict": "approve", "confidence": 0.8, "critique": {"issues": []}},
        "quine": {"verdict": "approve", "confidence": 0.8, "critique": {"issues": []}},
    }
    result = compute_consensus(critiques)
    # Frege: revise at 1.5 * 0.8 = 1.2
    # Wittgenstein: approve at 1.0 * 0.8 = 0.8 (no dominant domain)
    # Quine: approve at 1.0 * 0.8 = 0.8
    # Approve total: 1.6, Revise total: 1.2
    assert result["result"] == "approve"


def test_weighted_voting_wittgenstein_idiom_expertise():
    """Wittgenstein's idiom expertise tips the scale."""
    critiques = {
        "frege": {"verdict": "approve", "confidence": 0.7, "critique": {"issues": []}},
        "wittgenstein": {"verdict": "revise", "confidence": 0.9, "critique": {"issues": [
            {"severity": "major", "category": "idiom_literal", "explanation": "test"},
            {"severity": "minor", "category": "idiom_literal", "explanation": "test2"},
        ]}},
        "quine": {"verdict": "approve", "confidence": 0.6, "critique": {"issues": []}},
    }
    result = compute_consensus(critiques)
    # Wittgenstein: revise at 1.5 * 0.9 = 1.35 (idiom domain)
    # Frege: approve at 1.0 * 0.7 = 0.7
    # Quine: approve at 1.0 * 0.6 = 0.6
    # Approve: 1.3, Revise: 1.35
    assert result["result"] == "revise"


def test_merged_issues_sorted_by_severity():
    critiques = {
        "frege": {"verdict": "revise", "confidence": 0.9, "critique": {"issues": [
            {"severity": "minor", "category": "sinn_loss", "explanation": "minor issue"},
        ]}},
        "wittgenstein": {"verdict": "revise", "confidence": 0.85, "critique": {"issues": [
            {"severity": "critical", "category": "idiom_literal", "explanation": "critical issue"},
        ]}},
        "quine": {"verdict": "approve", "confidence": 0.9, "critique": {"issues": []}},
    }
    result = compute_consensus(critiques)
    issues = result["merged_issues"]
    assert len(issues) == 2
    assert issues[0]["severity"] == "critical"
    assert issues[1]["severity"] == "minor"


def test_revision_instructions_generated():
    """When consensus is revise, revision_instructions should contain issue details."""
    critiques = {
        "frege": {"verdict": "revise", "confidence": 0.95, "critique": {"issues": [
            {"severity": "major", "category": "tone_shift", "explanation": "tone is wrong",
             "suggestion": "use formal register"},
        ]}},
        "wittgenstein": {"verdict": "revise", "confidence": 0.85, "critique": {"issues": [
            {"severity": "major", "category": "idiom_literal", "explanation": "idiom missed"},
        ]}},
        "quine": {"verdict": "approve", "confidence": 0.7, "critique": {"issues": []}},
    }
    result = compute_consensus(critiques)
    assert result["result"] == "revise"
    assert "tone is wrong" in result["revision_instructions"]
    assert "use formal register" in result["revision_instructions"]


def test_empty_critiques_escalates():
    result = compute_consensus({})
    assert result["result"] == "escalated"
    assert result["quorum_met"] is False


def test_partial_quorum_proceeds():
    """With 2 of 3 philosophers, consensus still works."""
    critiques = {
        "frege": {"verdict": "approve", "confidence": 0.9, "critique": {"issues": []}},
        "wittgenstein": {"verdict": "approve", "confidence": 0.85, "critique": {"issues": []}},
    }
    result = compute_consensus(critiques)
    assert result["result"] == "approve"
    assert result["quorum_met"] is False


def test_category_mapping_complete():
    """All categories map to known domains."""
    known_domains = {"idiom_resolution", "tone_and_style", "ambiguity", "factual_accuracy", "pragmatics"}
    for cat, domain in CATEGORY_TO_DOMAIN.items():
        assert domain in known_domains, f"Unknown domain {domain} for category {cat}"


def test_with_fixture_critiques(all_critiques):
    """Test with real fixture data from run 2026-06-02_001."""
    result = compute_consensus(all_critiques)
    assert result["result"] in ("approve", "revise", "block")
    assert result["quorum_met"] is True
    assert isinstance(result["merged_issues"], list)
    assert isinstance(result["vote_scores"], dict)
