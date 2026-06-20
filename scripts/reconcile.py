#!/usr/bin/env python3
"""
reconcile.py — Merge client feedback + translation draft + critic notes → approved.json

Usage:
    python3 scripts/reconcile.py <run_id>

Reads:
    corpus/runs/<run_id>/feedback/client_review.json
    corpus/runs/<run_id>/final/translation_draft.json
    corpus/runs/<run_id>/final/critique_wittgenstein.json
    corpus/runs/<run_id>/final/critique_quine.json
    corpus/runs/<run_id>/final/critique_frege.json

Writes:
    corpus/runs/<run_id>/final/approved.json       (approved + client-revised segments)
    corpus/runs/<run_id>/final/rejected.json        (rejected segments needing re-translation)
    corpus/runs/<run_id>/manifest.yml               (updates status + human_review fields)

Logic:
    - "ok" → segment goes to approved.json as-is
    - "suggest" → segment goes to approved.json with client's suggested text applied
    - "reject" → segment goes to rejected.json for re-translation dispatch
    - no decision → segment goes to approved.json (implicit approval)
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: reconcile.py <run_id>")
        sys.exit(1)

    run_id = sys.argv[1]
    project = Path(__file__).resolve().parent.parent
    run_dir = project / "corpus" / "runs" / run_id

    # ── Load inputs ──────────────────────────────────────────────
    feedback_path = run_dir / "feedback" / "client_review.json"
    draft_path = run_dir / "final" / "translation_draft.json"

    if not feedback_path.exists():
        print(f"ERROR: No client feedback found at {feedback_path}")
        print(f"Run ingestion first: ./scripts/ingest-feedback.sh {run_id} <input_file>")
        sys.exit(1)

    if not draft_path.exists():
        print(f"ERROR: No translation draft found at {draft_path}")
        sys.exit(1)

    feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
    draft = json.loads(draft_path.read_text(encoding="utf-8"))

    # Load critic notes for quality signals
    critics = {}
    for name in ["wittgenstein", "quine", "frege"]:
        cpath = run_dir / "final" / f"critique_{name}.json"
        if cpath.exists():
            critics[name] = json.loads(cpath.read_text(encoding="utf-8"))

    decisions = feedback.get("decisions", {})
    notes = feedback.get("notes", {})
    segments = draft.get("segments", [])

    # ── Reconcile ────────────────────────────────────────────────
    approved_translations = []
    rejected_segments = []
    stats = {"ok": 0, "suggest": 0, "reject": 0, "implicit_ok": 0}

    for seg in segments:
        seg_id = seg["id"]
        seg_num = seg_id.replace("seg_", "")

        decision = decisions.get(seg_num, "").lower()
        client_note = notes.get(seg_num, "")

        # Get critic confidence scores
        quality = get_quality_signals(seg_id, critics)

        if decision == "reject":
            stats["reject"] += 1
            rejected_segments.append({
                "segment_id": seg_id,
                "source_text": seg["source"],
                "rejected_translation": seg["translation"],
                "client_reason": client_note,
                "critic_notes": get_critic_issues_for_segment(seg_id, critics),
            })
        else:
            # ok, suggest, or no decision (implicit ok)
            final_text = seg["translation"]
            revision_history = []

            if decision == "suggest" and client_note:
                stats["suggest"] += 1
                # Check if the client provided a replacement text
                replacement = extract_replacement(client_note)
                if replacement:
                    revision_history.append({
                        "round": "client_review",
                        "action": "client_override",
                        "previous": seg["translation"],
                        "change": replacement,
                        "reason": client_note,
                    })
                    final_text = replacement
                else:
                    revision_history.append({
                        "round": "client_review",
                        "action": "client_note",
                        "note": client_note,
                    })
            elif decision == "ok":
                stats["ok"] += 1
            else:
                stats["implicit_ok"] += 1

            approved_translations.append({
                "segment_id": seg_id,
                "source_text": seg["source"],
                "final_text": final_text,
                "revision_history": revision_history,
                "quality_signals": quality,
                "glossary_terms_used": [f.get("detail", "") for f in seg.get("flags", []) if f.get("type") == "client_term"],
                "client_patterns_applied": [f.get("detail", "") for f in seg.get("flags", []) if f.get("type") == "client_pattern"],
            })

    # ── Write approved.json ──────────────────────────────────────
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    approved_output = {
        "_schema": "interpretation-ai-cell/approved-translation/v1",
        "run_id": run_id,
        "approved_at": now,
        "approval_method": "client_review",
        "consensus_rounds": 1,
        "reviewer": feedback.get("reviewer", ""),
        "summary": {
            "total": len(segments),
            "approved": stats["ok"] + stats["implicit_ok"],
            "revised_by_client": stats["suggest"],
            "rejected": stats["reject"],
        },
        "translations": approved_translations,
    }

    approved_path = run_dir / "final" / "approved.json"
    approved_path.write_text(json.dumps(approved_output, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Write rejected.json (if any) ─────────────────────────────
    if rejected_segments:
        rejected_output = {
            "_schema": "interpretation-ai-cell/rejected-segments/v1",
            "run_id": run_id,
            "created_at": now,
            "segments": rejected_segments,
            "action_required": "re-translate",
            "instructions": "Dispatch these segments to the translator with the client's feedback as context. "
                           "Then re-run through the critic panel.",
        }
        rejected_path = run_dir / "final" / "rejected.json"
        rejected_path.write_text(json.dumps(rejected_output, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Update manifest.yml ──────────────────────────────────────
    manifest_path = run_dir / "manifest.yml"
    if manifest_path.exists():
        manifest = manifest_path.read_text(encoding="utf-8")

        # Update status
        if stats["reject"] > 0:
            new_status = "review"  # still needs work
        else:
            new_status = "approved"

        manifest = re.sub(r'status: ".*?"', f'status: "{new_status}"', manifest)
        manifest = re.sub(r'approved: \d+', f'approved: {stats["ok"] + stats["implicit_ok"] + stats["suggest"]}', manifest)
        manifest = re.sub(r'blocked: \d+', f'blocked: {stats["reject"]}', manifest)

        # Update human_review section
        manifest = re.sub(r'required: false', 'required: true', manifest)
        manifest = re.sub(r'reviewer: ""', f'reviewer: "{feedback.get("reviewer", "")}"', manifest)
        manifest = re.sub(r'reviewed_at: ""', f'reviewed_at: "{now}"', manifest)

        if stats["reject"] > 0:
            manifest = re.sub(r'decision: ""', 'decision: "revised"', manifest)
        else:
            manifest = re.sub(r'decision: ""', 'decision: "approved"', manifest)

        manifest_path.write_text(manifest, encoding="utf-8")

    # ── Report ───────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  RECONCILIATION COMPLETE — Run {run_id}")
    print(f"{'='*60}")
    print(f"  Total segments:       {len(segments)}")
    print(f"  Approved (explicit):  {stats['ok']}")
    print(f"  Approved (implicit):  {stats['implicit_ok']}")
    print(f"  Revised by client:    {stats['suggest']}")
    print(f"  Rejected:             {stats['reject']}")
    print(f"")
    print(f"  Output files:")
    print(f"    {approved_path}")
    if rejected_segments:
        print(f"    {run_dir / 'final' / 'rejected.json'}")
    print(f"    {manifest_path} (updated)")
    print(f"")

    if rejected_segments:
        print(f"  ⚠️  {stats['reject']} segment(s) rejected — re-translation required.")
        print(f"  Next: dispatch rejected segments to translator with client context.")
        print(f"")
        for r in rejected_segments:
            print(f"    {r['segment_id']}: {r['client_reason'][:80]}...")
    else:
        print(f"  ✅ All segments approved. Translation ready for delivery.")
        print(f"  Next: merge to main to trigger scientist audits (Koehn, Cho, Vaswani).")


def get_quality_signals(seg_id: str, critics: dict) -> dict:
    """Extract confidence scores from critic outputs."""
    signals = {
        "wittgenstein_confidence": 0.0,
        "quine_confidence": 0.0,
        "frege_confidence": 0.0,
        "consensus_score": 0.0,
    }

    for name, critic_data in critics.items():
        confidence = critic_data.get("confidence", 0.0)
        signals[f"{name}_confidence"] = confidence

        # Check if this segment had issues
        issues = critic_data.get("critique", {}).get("issues", [])
        seg_num = seg_id.replace("seg_", "")
        for issue in issues:
            src = issue.get("span_source", {})
            if src:  # has span data — critic flagged something
                pass  # confidence already captured at critique level

    # Consensus = average of all critics
    confs = [v for k, v in signals.items() if k.endswith("_confidence") and v > 0]
    signals["consensus_score"] = round(sum(confs) / len(confs), 2) if confs else 0.0

    return signals


def get_critic_issues_for_segment(seg_id: str, critics: dict) -> list:
    """Collect all critic notes relevant to a segment for rejected re-translation context."""
    all_issues = []
    seg_num = int(seg_id.replace("seg_", ""))

    for name, critic_data in critics.items():
        issues = critic_data.get("critique", {}).get("issues", [])
        for issue in issues:
            all_issues.append({
                "critic": name,
                "severity": issue.get("severity", ""),
                "category": issue.get("category", ""),
                "explanation": issue.get("explanation", ""),
                "suggestion": issue.get("suggestion", ""),
            })

    return all_issues


def extract_replacement(note: str) -> str:
    """Try to extract a replacement translation from the client note.

    Patterns:
        "Change to: Aus Herausforderungen werden Chancen"
        "Prefer: Aus Herausforderungen werden Chancen"
        "→ Aus Herausforderungen werden Chancen"
        "Use instead: Aus Herausforderungen werden Chancen"
    """
    patterns = [
        r"(?:change\s*to|prefer|use\s*instead|replace\s*with|should\s*be|korrektur|ändern\s*zu|besser)\s*:\s*[\"']?(.+?)[\"']?\s*$",
        r"→\s*(.+)$",
        r"[\"'](.+?)[\"']\s*$",  # quoted text at end
    ]
    for pattern in patterns:
        m = re.search(pattern, note, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return ""


if __name__ == "__main__":
    main()
