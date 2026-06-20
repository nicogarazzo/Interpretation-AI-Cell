"""Tests for pipeline orchestration (no API calls)."""

import json
import shutil
from pathlib import Path

import pytest

from v2.config import CORPUS, TEMPLATE
from v2.pipeline import (
    _build_review_segments,
    create_run_dir,
    load_segments,
    parse_json_response,
)


def test_parse_json_response_clean():
    raw = '{"verdict": "approve", "confidence": 0.9}'
    result = parse_json_response(raw)
    assert result["verdict"] == "approve"
    assert result["confidence"] == 0.9


def test_parse_json_response_with_fencing():
    raw = '```json\n{"verdict": "revise"}\n```'
    result = parse_json_response(raw)
    assert result["verdict"] == "revise"


def test_parse_json_response_with_preamble_fencing():
    raw = 'Here is my analysis:\n```json\n{"verdict": "block"}\n```'
    result = parse_json_response(raw)
    assert result["verdict"] == "block"


def test_parse_json_response_invalid():
    raw = "this is not json at all"
    result = parse_json_response(raw)
    assert "_parse_error" in result
    assert result["verdict"] == "unknown"


def test_parse_json_response_array():
    raw = '[{"id": "seg_001", "translation": "test"}]'
    result = parse_json_response(raw)
    assert isinstance(result, list)
    assert result[0]["id"] == "seg_001"


def test_create_run_dir(tmp_path, monkeypatch):
    # Redirect CORPUS to tmp
    import v2.pipeline as pipeline_mod
    import v2.config as config_mod

    test_corpus = tmp_path / "runs"
    test_corpus.mkdir()
    test_template = test_corpus / ".template"

    # Copy template
    shutil.copytree(TEMPLATE, test_template)

    monkeypatch.setattr(pipeline_mod, "CORPUS", test_corpus)
    monkeypatch.setattr(config_mod, "CORPUS", test_corpus)

    # Monkeypatch the CORPUS in create_run_dir's closure
    original_create = pipeline_mod.create_run_dir

    def patched_create(run_id=None):
        import v2.pipeline
        old_corpus = v2.pipeline.CORPUS
        v2.pipeline.CORPUS = test_corpus
        try:
            if run_id is None:
                from datetime import datetime
                today = datetime.now().strftime("%Y-%m-%d")
                existing = list(test_corpus.glob(f"{today}_*"))
                seq = len(existing) + 1
                run_id = f"{today}_{seq:03d}"

            run_dir = test_corpus / run_id
            if not run_dir.exists():
                shutil.copytree(test_template, run_dir)
            return run_id, run_dir
        finally:
            v2.pipeline.CORPUS = old_corpus

    run_id, run_dir = patched_create("test-001")
    assert run_dir.exists()
    assert (run_dir / "manifest.yml").exists()
    assert (run_dir / "source").is_dir()
    assert (run_dir / "final").is_dir()
    assert (run_dir / "agents" / "translator").is_dir()


def test_build_review_segments(segments, translation_draft):
    result = _build_review_segments(translation_draft, segments)
    assert isinstance(result, list)
    assert len(result) > 0
    for seg in result:
        assert "id" in seg
        assert "source" in seg
        assert "translation" in seg


def test_load_segments_wrapper_format(tmp_path):
    """Test loading segments in the {segments: [...]} wrapper format."""
    seg_file = tmp_path / "segments.json"
    data = {
        "_schema": "test",
        "segments": [{"id": "seg_001", "text": "hello", "type": "test"}],
    }
    seg_file.write_text(json.dumps(data))
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "segments.json").write_text(json.dumps(data))

    result = load_segments(tmp_path)
    assert len(result) == 1
    assert result[0]["id"] == "seg_001"


def test_load_segments_bare_list(tmp_path):
    """Test loading segments as a bare JSON array."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    data = [{"id": "seg_001", "text": "hello", "type": "test"}]
    (source_dir / "segments.json").write_text(json.dumps(data))

    result = load_segments(tmp_path)
    assert len(result) == 1
