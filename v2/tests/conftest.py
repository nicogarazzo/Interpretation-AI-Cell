"""Shared fixtures for v2 pipeline tests."""

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def segments():
    with open(FIXTURES / "segments.json", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("segments", [])


@pytest.fixture
def translation_draft():
    with open(FIXTURES / "translation_draft.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def critique_frege():
    with open(FIXTURES / "critique_frege.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def critique_wittgenstein():
    path = FIXTURES / "critique_wittgenstein.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    # Fallback: minimal approve
    return {"verdict": "approve", "confidence": 0.9, "critique": {"issues": []}}


@pytest.fixture
def critique_quine():
    path = FIXTURES / "critique_quine.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"verdict": "approve", "confidence": 0.92, "critique": {"issues": []}}


@pytest.fixture
def all_critiques(critique_frege, critique_wittgenstein, critique_quine):
    return {
        "frege": critique_frege,
        "wittgenstein": critique_wittgenstein,
        "quine": critique_quine,
    }
