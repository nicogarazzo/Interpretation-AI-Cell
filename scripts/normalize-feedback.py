#!/usr/bin/env python3
"""
normalize-feedback.py — Convert any client feedback format to standard schema.

Handles:
  1. Direct JSON matching client_review schema (passthrough)
  2. Tally JSON export (field mapping)
  3. Plain text (parsed from clipboard/email format)

Output schema: interpretation-ai-cell/client-review/v1
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_segment_count(run_id: str) -> int:
    """Read total segments from translation_draft.json."""
    project = Path(__file__).resolve().parent.parent
    draft = project / "corpus" / "runs" / run_id / "final" / "translation_draft.json"
    if draft.exists():
        data = json.loads(draft.read_text())
        return len(data.get("segments", []))
    return 32  # fallback


def normalize_json(run_id: str, data: dict) -> dict:
    """Normalize a JSON input to the standard schema."""
    # Case 1: Already in our schema
    if data.get("_schema") == "interpretation-ai-cell/client-review/v1":
        data["run_id"] = run_id
        return data

    # Case 2: Tally export (array of submissions or single object with field labels)
    if isinstance(data, list):
        # Tally exports submissions as array — take the latest
        data = data[-1] if data else {}

    # Try to find fields by label patterns
    decisions = {}
    notes = {}
    reviewer = ""
    reviewed_at = ""
    general_feedback = ""

    for key, val in data.items():
        kl = key.lower().strip()
        if not val:
            continue
        val_str = str(val).strip()

        if "reviewer" in kl or kl == "name":
            reviewer = val_str
        elif "date" in kl:
            reviewed_at = val_str
        elif "approved" in kl or "segments_approved" in kl or "ok" in kl:
            # Parse comma-separated segment numbers or checkbox selections
            segs = parse_segment_list(val_str)
            for s in segs:
                decisions[s] = "ok"
        elif "revise" in kl or "change" in kl or "suggest" in kl:
            parsed = parse_segment_notes(val_str)
            for seg, note in parsed.items():
                decisions[seg] = "suggest"
                notes[seg] = note
        elif "reject" in kl:
            parsed = parse_segment_notes(val_str)
            for seg, note in parsed.items():
                decisions[seg] = "reject"
                notes[seg] = note
        elif "general" in kl or "overall" in kl or "feedback" in kl:
            general_feedback = val_str
        elif "decisions" in kl and isinstance(val, dict):
            decisions.update(val)
        elif "notes" in kl and isinstance(val, dict):
            notes.update(val)

    return build_output(run_id, reviewer, reviewed_at, decisions, notes, general_feedback)


def normalize_text(run_id: str, text: str) -> dict:
    """Parse plain text feedback (email/clipboard format)."""
    decisions = {}
    notes = {}
    reviewer = ""
    reviewed_at = ""
    general_feedback = ""

    lines = text.strip().split("\n")
    in_general = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Reviewer line
        m = re.match(r"[Rr]eviewer:\s*(.+)", line)
        if m:
            reviewer = m.group(1).strip()
            continue

        # Date line
        m = re.match(r"[Dd]ate:\s*(.+)", line)
        if m:
            reviewed_at = m.group(1).strip()
            continue

        # General feedback marker
        if re.match(r"(?i)general\s*feedback:", line):
            in_general = True
            rest = re.sub(r"(?i)general\s*feedback:\s*", "", line).strip()
            if rest:
                general_feedback = rest
            continue

        if in_general:
            general_feedback += (" " + line) if general_feedback else line
            continue

        # Segment decision line: seg_001: OK -- some note
        m = re.match(r"seg[_\s]*(\d+)\s*:\s*(OK|APPROVE[D]?|SUGGEST|REVISE|REJECT(?:ED)?)\s*(?:--\s*(.+))?", line, re.IGNORECASE)
        if m:
            seg = m.group(1).zfill(3)
            raw_decision = m.group(2).upper()
            note = (m.group(3) or "").strip()

            if raw_decision in ("OK", "APPROVED", "APPROVE"):
                decisions[seg] = "ok"
            elif raw_decision in ("SUGGEST", "REVISE"):
                decisions[seg] = "suggest"
            elif raw_decision in ("REJECT", "REJECTED"):
                decisions[seg] = "reject"

            if note:
                notes[seg] = note
            continue

        # SUMMARY line (skip it)
        if line.startswith("SUMMARY:") or line.startswith("==="):
            continue

    return build_output(run_id, reviewer, reviewed_at, decisions, notes, general_feedback)


def parse_segment_list(text: str) -> list:
    """Extract segment numbers from text like 'Seg 1, Seg 2, ...' or '1,2,3,...' or checkbox labels."""
    numbers = re.findall(r"(?:seg(?:ment)?\s*)?(\d+)", text, re.IGNORECASE)
    return [n.zfill(3) for n in numbers]


def parse_segment_notes(text: str) -> dict:
    """Parse 'Seg 9: change to X\nSeg 25: keep Y' into {009: 'change to X', 025: 'keep Y'}."""
    result = {}
    # Split by segment markers
    parts = re.split(r"(?:^|\n)\s*[Ss]eg(?:ment)?\s*(\d+)\s*:\s*", text)
    # parts = ['', '9', 'change to X', '25', 'keep Y']
    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            seg = parts[i].zfill(3)
            note = parts[i + 1].strip()
            if note:
                result[seg] = note
    # If no structured format found, treat entire text as note for unknown segment
    if not result and text.strip():
        result["000"] = text.strip()
    return result


def build_output(run_id, reviewer, reviewed_at, decisions, notes, general_feedback):
    if not reviewed_at:
        reviewed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "_schema": "interpretation-ai-cell/client-review/v1",
        "run_id": run_id,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "decisions": decisions,
        "notes": notes,
        "general_feedback": general_feedback,
    }


def main():
    if len(sys.argv) < 4:
        print("Usage: normalize-feedback.py <run_id> <input_file> <output_file> [--text]")
        sys.exit(1)

    run_id = sys.argv[1]
    input_file = Path(sys.argv[2])
    output_file = Path(sys.argv[3])
    is_text = "--text" in sys.argv

    content = input_file.read_text(encoding="utf-8")

    if is_text:
        result = normalize_text(run_id, content)
    else:
        data = json.loads(content)
        result = normalize_json(run_id, data)

    # Report
    n_decisions = len(result["decisions"])
    n_notes = len(result["notes"])
    print(f"  Reviewer:  {result['reviewer'] or '(not provided)'}")
    print(f"  Decisions: {n_decisions}")
    print(f"  Notes:     {n_notes}")
    print(f"  Feedback:  {'yes' if result['general_feedback'] else 'none'}")

    output_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
