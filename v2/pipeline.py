#!/usr/bin/env python3
"""
pipeline.py — Main orchestration for Interpretation AI Cell v2.

Replaces Hermes Kanban with direct Anthropic SDK calls.
Uses profiles/*/SOUL.md as system prompts, runs philosophers in parallel,
computes deterministic consensus, and generates review outputs.

Usage:
    python3 v2/pipeline.py --source path/to/source.txt --client example-client
    python3 v2/pipeline.py --run 2026-06-18_001
    python3 v2/pipeline.py --run 2026-06-18_001 --audit
    python3 v2/pipeline.py --run 2026-06-18_001 --dry-run
"""

import argparse
import json
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Allow running as script or module
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from v2.agents import build_system_prompt
from v2.config import (
    ALL_AGENTS,
    CORPUS,
    PHILOSOPHERS,
    ROOT,
    SCIENTISTS,
    TEMPLATE,
    get_max_tokens,
    get_model_for_agent,
    load_consensus_config,
    load_environment,
)
from v2.consensus import compute_consensus

# ── JSON response parsing ───────────────────────────────────────────────────
# Reused pattern from scripts/benchmark-critics.py:48-61


def parse_json_response(raw: str) -> dict | list:
    """Strip markdown fencing (with optional preamble) and parse JSON."""
    text = raw.strip()
    # Extract content from ```json ... ``` blocks (with possible preamble text before)
    fenced = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    else:
        # Try stripping fencing at start/end
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?\s*```$", "", text.strip())
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        return {
            "verdict": "unknown",
            "confidence": 0.0,
            "_parse_error": str(e),
            "_raw_preview": text[:500],
        }


# ── Run directory management ────────────────────────────────────────────────


def create_run_dir(run_id: str | None = None) -> tuple[str, Path]:
    """Create a new run directory from the template.

    Returns (run_id, run_dir_path).
    """
    if run_id is None:
        today = datetime.now().strftime("%Y-%m-%d")
        existing = list(CORPUS.glob(f"{today}_*"))
        seq = len(existing) + 1
        run_id = f"{today}_{seq:03d}"

    run_dir = CORPUS / run_id
    if run_dir.exists():
        return run_id, run_dir

    shutil.copytree(TEMPLATE, run_dir)

    # Fill manifest
    manifest_path = run_dir / "manifest.yml"
    text = manifest_path.read_text(encoding="utf-8")
    text = text.replace('run_id: ""', f'run_id: "{run_id}"')
    text = text.replace(
        'created_at: ""',
        f'created_at: "{datetime.now(timezone.utc).isoformat()}"',
    )
    manifest_path.write_text(text, encoding="utf-8")

    return run_id, run_dir


def load_segments(run_dir: Path) -> list[dict]:
    """Load source segments from run directory."""
    path = run_dir / "source" / "segments.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("segments", data)


# ── API call wrappers ───────────────────────────────────────────────────────


def _call_anthropic(model: str, system_prompt: str, user_message: str, max_tokens: int) -> dict:
    """Call the Anthropic API and return parsed response + usage."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = response.content[0].text
    parsed = parse_json_response(raw)
    return {
        "parsed": parsed,
        "raw": raw,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
        "model": response.model,
    }


def _call_glm(model: str, system_prompt: str, user_message: str, max_tokens: int) -> dict:
    """Call the z.ai GLM API (OpenAI-compatible) and return parsed response + usage."""
    from openai import OpenAI

    api_key = os.environ.get("GLM_API_KEY")
    if not api_key:
        raise RuntimeError("GLM_API_KEY not set in environment")

    client = OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=max_tokens,
    )
    raw = response.choices[0].message.content
    parsed = parse_json_response(raw)
    usage = response.usage
    return {
        "parsed": parsed,
        "raw": raw,
        "usage": {
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
        },
        "model": model,
    }


def call_agent(agent_name: str, user_message: str) -> dict:
    """Call an agent via the appropriate API based on environment."""
    env = load_environment()
    model = get_model_for_agent(agent_name)
    max_tokens = get_max_tokens(agent_name)
    system_prompt = build_system_prompt(agent_name)

    if env["_active"] == "production" or env.get("provider") == "anthropic":
        return _call_anthropic(model, system_prompt, user_message, max_tokens)
    else:
        return _call_glm(model, system_prompt, user_message, max_tokens)


# ── Pipeline steps ──────────────────────────────────────────────────────────


def step_translate(segments: list[dict], run_dir: Path) -> dict:
    """Step 3: Run the translator agent."""
    segs_text = json.dumps(segments, ensure_ascii=False, indent=2)
    user_msg = (
        "Translate the following JSON segments from English to German "
        "following your SOUL.md directives.\n"
        "Return a valid JSON object with the schema described in your Output Format section.\n"
        "Include all segment IDs from the input.\n"
        "No preamble, no markdown fencing, no explanation.\n\n"
        f"Segments:\n{segs_text}"
    )

    result = call_agent("translator", user_msg)

    # Write outputs
    _write_json(run_dir / "agents" / "translator" / "output.json", result["parsed"])
    _write_json(run_dir / "final" / "translation_draft.json", result["parsed"])

    print(f"  Translator: {result['usage']['input_tokens']}+{result['usage']['output_tokens']} tokens ({result['model']})")
    return result


def step_review(translation: dict, segments: list[dict], run_dir: Path) -> dict[str, dict]:
    """Step 4: Run philosopher review in parallel."""
    # Build candidate segments for review
    candidate = {
        "segments": _build_review_segments(translation, segments),
    }
    candidate_text = json.dumps(candidate, ensure_ascii=False, indent=2)

    user_msg = (
        "Review the following candidate EN-to-DE translation.\n"
        "Apply your full critique process exactly as described in your SOUL.md.\n"
        "Output ONLY valid JSON matching your output format.\n"
        "No preamble, no markdown fencing.\n\n"
        f"Candidate segments:\n{candidate_text}"
    )

    critiques = {}

    def _review_one(philosopher: str) -> tuple[str, dict]:
        result = call_agent(philosopher, user_msg)
        # Write to both agent dir and final dir
        _write_json(run_dir / "agents" / philosopher / "review.json", result["parsed"])
        _write_json(run_dir / "final" / f"critique_{philosopher}.json", result["parsed"])
        print(f"  {philosopher.capitalize()}: verdict={result['parsed'].get('verdict', '?')} "
              f"({result['usage']['input_tokens']}+{result['usage']['output_tokens']} tokens)")
        return philosopher, result["parsed"]

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_review_one, p): p for p in PHILOSOPHERS}
        for future in as_completed(futures):
            philosopher, critique = future.result()
            critiques[philosopher] = critique

    return critiques


def step_revise(
    segments: list[dict],
    previous_draft: dict,
    merged_issues: list[dict],
    revision_instructions: str,
    round_num: int,
    run_dir: Path,
) -> dict:
    """Revision round: re-translate with philosopher feedback."""
    draft_text = json.dumps(previous_draft, ensure_ascii=False, indent=2)
    feedback_text = revision_instructions

    user_msg = (
        f"REVISION ROUND {round_num}: The previous translation was reviewed by the philosopher panel.\n"
        f"Verdict: REVISE. Incorporate the following feedback and produce a corrected translation.\n\n"
        f"Previous translation:\n{draft_text}\n\n"
        f"Philosopher feedback:\n{feedback_text}\n\n"
        "Produce a corrected translation following the same output format.\n"
        "Return ONLY valid JSON. No preamble, no markdown fencing."
    )

    result = call_agent("translator", user_msg)

    _write_json(run_dir / "final" / "translation_draft.json", result["parsed"])
    print(f"  Translator (revision {round_num}): {result['usage']['input_tokens']}+{result['usage']['output_tokens']} tokens")
    return result


def step_audit(run_dir: Path) -> dict[str, dict]:
    """Optional: Run scientist audits sequentially."""
    results = {}
    for scientist in SCIENTISTS:
        print(f"  Running {scientist} audit...")
        # Build context based on the scientist's specialty
        audit_context = _build_audit_context(scientist, run_dir)
        result = call_agent(scientist, audit_context)
        _write_json(run_dir / "agents" / scientist / "audit.json", result["parsed"])
        print(f"  {scientist.capitalize()}: result={result['parsed'].get('audit_result', '?')} "
              f"({result['usage']['input_tokens']}+{result['usage']['output_tokens']} tokens)")
        results[scientist] = result["parsed"]
    return results


# ── Helper functions ────────────────────────────────────────────────────────


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _build_review_segments(translation: dict, segments: list[dict]) -> list[dict]:
    """Pair source and translated segments for philosopher review."""
    # Handle different translation output formats
    translations = translation.get("segments", translation.get("translations", []))
    if isinstance(translations, dict):
        translations = [translations]

    # Index translations by ID
    trans_by_id = {}
    for t in translations:
        tid = t.get("id", t.get("segment_id", ""))
        trans_by_id[tid] = t

    result = []
    for seg in segments:
        seg_id = seg.get("id", "")
        trans = trans_by_id.get(seg_id, {})
        result.append({
            "id": seg_id,
            "type": seg.get("type", ""),
            "source": seg.get("text", ""),
            "translation": trans.get("translation", trans.get("target_text", "")),
            "context": seg.get("context", {}),
        })
    return result


def _build_audit_context(scientist: str, run_dir: Path) -> str:
    """Build the user message for a scientist audit."""
    # Load translation and critiques
    draft_path = run_dir / "final" / "translation_draft.json"
    draft = {}
    if draft_path.exists():
        with open(draft_path, encoding="utf-8") as f:
            draft = json.load(f)

    critiques = {}
    for phil in PHILOSOPHERS:
        crit_path = run_dir / "final" / f"critique_{phil}.json"
        if crit_path.exists():
            with open(crit_path, encoding="utf-8") as f:
                critiques[phil] = json.load(f)

    verdict_path = run_dir / "consensus" / "verdict.json"
    verdict = {}
    if verdict_path.exists():
        with open(verdict_path, encoding="utf-8") as f:
            verdict = json.load(f)

    context = {
        "run_dir": str(run_dir),
        "translation_draft": draft,
        "philosopher_critiques": critiques,
        "consensus_verdict": verdict,
    }

    return (
        f"Perform your {scientist} audit on the following translation run.\n"
        "Apply your full audit process as described in your SOUL.md.\n"
        "Output ONLY valid JSON matching your output format.\n\n"
        f"Run data:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def _update_manifest(run_dir: Path, activity: dict) -> None:
    """Update manifest.yml with pipeline activity."""
    import yaml

    manifest_path = run_dir / "manifest.yml"
    with open(manifest_path, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    manifest["status"] = activity.get("status", manifest.get("status", "pending"))

    if "translator" in activity:
        manifest.setdefault("agent_activity", {}).setdefault("translator", {})
        manifest["agent_activity"]["translator"].update(activity["translator"])

    for phil in PHILOSOPHERS:
        if phil in activity:
            manifest.setdefault("agent_activity", {}).setdefault(phil, {})
            manifest["agent_activity"][phil].update(activity[phil])

    if "consensus" in activity:
        manifest.setdefault("agent_activity", {}).setdefault("consensus", {})
        manifest["agent_activity"]["consensus"].update(activity["consensus"])

    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True)


# ── Main pipeline ───────────────────────────────────────────────────────────


def run_pipeline(
    run_id: str | None = None,
    source_path: str | None = None,
    client: str = "example-client",
    audit: bool = False,
    dry_run: bool = False,
    max_rounds: int | None = None,
) -> dict:
    """Execute the full translation pipeline.

    Returns a summary dict with run_id, verdict, rounds, token usage.
    """
    env = load_environment()
    consensus_config = load_consensus_config()
    if max_rounds is None:
        max_rounds = consensus_config.get("max_rounds", 3)

    # Step 1: Create or locate run directory
    print(f"\n{'='*60}")
    print(f"Interpretation AI Cell v2 Pipeline")
    print(f"Environment: {env['_active']} ({env.get('provider', 'unknown')})")
    print(f"{'='*60}\n")

    run_id, run_dir = create_run_dir(run_id)
    print(f"[1/7] Run directory: {run_dir.relative_to(ROOT)}")

    # Step 2: Ingest source
    if source_path:
        src = Path(source_path)
        if src.suffix == ".json":
            shutil.copy2(src, run_dir / "source" / "segments.json")
        else:
            # Copy raw text
            shutil.copy2(src, run_dir / "source" / "raw.txt")
            # For now, expect segments.json to exist or be created separately
            if not (run_dir / "source" / "segments.json").exists():
                print(f"  WARNING: segments.json not found. Copy segmented JSON to {run_dir}/source/segments.json")
                return {"run_id": run_id, "status": "needs_segmentation"}

    segments = load_segments(run_dir)
    seg_count = len(segments) if isinstance(segments, list) else 0
    print(f"[2/7] Source loaded: {seg_count} segments")

    if dry_run:
        return _dry_run(run_dir, segments)

    # Step 3: Translate
    print(f"\n[3/7] Translating...")
    activity = {"status": "in_progress"}

    trans_result = step_translate(segments, run_dir)
    translation = trans_result["parsed"]
    activity["translator"] = {
        "model_used": trans_result["model"],
        "tokens_used": trans_result["usage"]["input_tokens"] + trans_result["usage"]["output_tokens"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Step 4-6: Review + Consensus loop
    round_num = 0
    final_verdict = None

    while round_num < max_rounds:
        round_num += 1
        print(f"\n[4/7] Philosopher review (round {round_num}/{max_rounds})...")

        critiques = step_review(translation, segments, run_dir)

        print(f"\n[5/7] Computing consensus...")
        verdict = compute_consensus(critiques, consensus_config)
        _write_json(run_dir / "consensus" / "verdict.json", verdict)
        final_verdict = verdict["result"]

        print(f"  Consensus: {final_verdict.upper()} "
              f"(scores: {verdict['vote_scores']})")

        for phil in PHILOSOPHERS:
            phil_verdict = critiques.get(phil, {}).get("verdict", "unknown")
            issues_count = len(critiques.get(phil, {}).get("critique", {}).get("issues", []))
            activity[phil] = {
                "verdict": phil_verdict,
                "issues_count": issues_count,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

        activity["consensus"] = {
            "result": final_verdict,
            "rounds": round_num,
        }

        if final_verdict == "approve":
            print(f"  Translation APPROVED after {round_num} round(s).")
            break
        elif final_verdict == "block":
            print(f"  Translation BLOCKED. Escalating to human review.")
            break
        elif final_verdict == "revise" and round_num < max_rounds:
            print(f"\n[6/7] Revision round {round_num + 1}...")
            rev_result = step_revise(
                segments, translation,
                verdict["merged_issues"],
                verdict["revision_instructions"],
                round_num + 1, run_dir,
            )
            translation = rev_result["parsed"]
        else:
            print(f"  Max rounds ({max_rounds}) reached. Final verdict: {final_verdict}")
            break

    # Step 7: Generate outputs
    print(f"\n[7/7] Generating review outputs...")

    try:
        from v2.review_gen import generate_bilingual_doc, generate_review_html, generate_review_md
        review_md = generate_review_md(run_dir, segments, translation, critiques, verdict)
        (run_dir / "final" / "review.md").write_text(review_md, encoding="utf-8")
        print(f"  review.md written")

        review_html = generate_review_html(run_dir, segments, translation, critiques, verdict)
        (run_dir / "final" / "review.html").write_text(review_html, encoding="utf-8")
        print(f"  review.html written")

        bilingual_html = generate_bilingual_doc(run_dir, segments, translation)
        (run_dir / "final" / "translation_bilingual.html").write_text(bilingual_html, encoding="utf-8")
        print(f"  translation_bilingual.html written")
    except ImportError:
        print(f"  review_gen not available yet, skipping output generation")
    except Exception as e:
        print(f"  WARNING: Output generation failed: {e}")

    # Update manifest
    activity["status"] = "approved" if final_verdict == "approve" else "review"
    _update_manifest(run_dir, activity)

    # Optional: scientist audits
    if audit:
        print(f"\n[AUDIT] Running scientist audits...")
        step_audit(run_dir)

    # Summary
    total_tokens = sum(
        activity.get(a, {}).get("tokens_used", 0) for a in ALL_AGENTS
    )
    summary = {
        "run_id": run_id,
        "status": final_verdict,
        "rounds": round_num,
        "total_tokens": total_tokens,
        "run_dir": str(run_dir),
    }

    print(f"\n{'='*60}")
    print(f"Pipeline complete: {run_id}")
    print(f"  Verdict: {final_verdict}")
    print(f"  Rounds:  {round_num}")
    print(f"  Output:  {run_dir.relative_to(ROOT)}/final/")
    print(f"{'='*60}\n")

    return summary


def _dry_run(run_dir: Path, segments: list[dict]) -> dict:
    """Dry run: show prompts and token estimates without API calls."""
    print(f"\n[DRY RUN] Assembling prompts...\n")

    for agent_name in ["translator"] + PHILOSOPHERS:
        prompt = build_system_prompt(agent_name)
        # Rough token estimate: ~4 chars per token
        est_tokens = len(prompt) // 4
        model = get_model_for_agent(agent_name)
        print(f"  {agent_name}: ~{est_tokens:,} system tokens, model={model}")
        print(f"    Prompt length: {len(prompt):,} chars")
        print(f"    Skills included: {_count_skills_in_prompt(prompt)}")

    segs_text = json.dumps(segments, ensure_ascii=False, indent=2)
    est_seg_tokens = len(segs_text) // 4
    print(f"\n  Segments payload: ~{est_seg_tokens:,} tokens ({len(segments)} segments)")
    print(f"\n[DRY RUN] No API calls made.")

    return {"run_id": run_dir.name, "status": "dry_run"}


def _count_skills_in_prompt(prompt: str) -> int:
    return prompt.count("## SKILL:")


# ── CLI ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Interpretation AI Cell v2 — Translation Pipeline",
    )
    parser.add_argument("--source", help="Path to source file (raw text or segments.json)")
    parser.add_argument("--run", help="Existing run ID (e.g., 2026-06-18_001)")
    parser.add_argument("--client", default="example-client", help="Client identifier")
    parser.add_argument("--audit", action="store_true", help="Run scientist audits after pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Show prompts without API calls")
    parser.add_argument("--max-rounds", type=int, help="Override max revision rounds")
    parser.add_argument("--preflight", action="store_true", help="Verify API key and environment")

    args = parser.parse_args()

    if args.preflight:
        env = load_environment()
        print(f"Environment: {env['_active']}")
        print(f"Provider:    {env.get('provider', 'unknown')}")
        if env["_active"] == "production":
            try:
                import anthropic
                client = anthropic.Anthropic()
                # Quick validation
                print(f"API key:     {'set' if os.environ.get('ANTHROPIC_API_KEY') else 'MISSING'}")
                print(f"SDK:         anthropic {anthropic.__version__}")
            except ImportError:
                print("ERROR: anthropic SDK not installed")
        else:
            print(f"API key:     {'set' if os.environ.get('GLM_API_KEY') else 'MISSING'}")
        return

    if not args.source and not args.run:
        parser.error("Either --source or --run is required")

    run_pipeline(
        run_id=args.run,
        source_path=args.source,
        client=args.client,
        audit=args.audit,
        dry_run=args.dry_run,
        max_rounds=args.max_rounds,
    )


if __name__ == "__main__":
    main()
