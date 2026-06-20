"""Tests for review output generation."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from v2.review_gen import generate_review_html, generate_review_md


@pytest.fixture
def mock_run_dir(tmp_path):
    return tmp_path / "test-run"


@pytest.fixture
def mock_verdict():
    return {
        "result": "revise",
        "vote_scores": {"approve": 1.6, "revise": 1.2, "block": 0.0},
        "merged_issues": [],
    }


def test_generate_review_md_structure(
    mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
):
    md = generate_review_md(
        mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
    )
    assert isinstance(md, str)
    assert "# Translation Review" in md
    assert "Critic Panel Summary" in md
    assert "Bilingual Segment Table" in md
    assert "| Critic | Verdict | Issues |" in md


def test_review_md_contains_all_philosophers(
    mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
):
    md = generate_review_md(
        mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
    )
    assert "Frege" in md
    assert "Wittgenstein" in md
    assert "Quine" in md


def test_review_md_contains_segment_ids(
    mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
):
    md = generate_review_md(
        mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
    )
    assert "seg_001" in md
    assert "seg_002" in md


def test_generate_review_html_produces_valid_html(
    mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
):
    html = generate_review_html(
        mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
    )
    assert isinstance(html, str)
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html
    assert "lucide" in html


def test_review_html_contains_segment_data(
    mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
):
    html = generate_review_html(
        mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
    )
    # Should contain EN source text
    assert "UNSEEN GUARDIANS" in html or "unseen guardians" in html.lower()


def test_review_html_contains_critic_panel(
    mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
):
    html = generate_review_html(
        mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
    )
    assert "critic-panel" in html
    assert "Wittgenstein" in html
    assert "Frege" in html
    assert "Quine" in html


def test_review_html_has_progress_bar(
    mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
):
    html = generate_review_html(
        mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
    )
    assert "progress-bar" in html
    assert "progress-fill" in html


def test_review_html_has_decision_buttons(
    mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
):
    html = generate_review_html(
        mock_run_dir, segments, translation_draft, all_critiques, mock_verdict
    )
    assert "btn-ok" in html
    assert "btn-suggest" in html
    assert "btn-reject" in html
