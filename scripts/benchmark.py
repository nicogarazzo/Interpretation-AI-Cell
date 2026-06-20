#!/usr/bin/env python3
"""
benchmark.py — Direct-API translation for Delta Stack model benchmarking.

Bypasses Hermes entirely. Reads translator SOUL.md as system prompt, calls the
candidate model's API directly, and captures exact token counts from the API response.

Usage:
    python3 scripts/benchmark.py --run 2026-06-02_002 --model claude-sonnet-4-20250514
    python3 scripts/benchmark.py --run 2026-06-02_002 --model glm-4.6  [uses GLM_API_KEY]

Output:
    corpus/runs/<run>/benchmark/<model-slug>/translation_draft.json
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "corpus" / "runs"
PROFILES = ROOT / "profiles"


def model_slug(model: str) -> str:
    return model.replace(".", "-").replace("/", "-")


def load_soul_md(profile: str) -> str:
    path = PROFILES / profile / "SOUL.md"
    return path.read_text(encoding="utf-8")


def load_segments(run_id: str) -> list[dict]:
    """Load source segments — supports bare list or {segments: [...]} wrapper."""
    path = CORPUS / run_id / "source" / "segments.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("segments", data)


def parse_translation_response(raw: str) -> list[dict]:
    """Parse model response — strips markdown fencing and parses JSON."""
    text = raw.strip()
    # Strip ```json ... ``` or ``` ... ``` fencing
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```$", "", text.strip())
    return json.loads(text.strip())


def translate_anthropic(model: str, soul_md: str, segments: list[dict]) -> dict:
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic SDK not installed. Run: pip install anthropic", file=sys.stderr)
        sys.exit(1)

    segs_text = json.dumps(segments, ensure_ascii=False, indent=2)
    user_msg = (
        "BENCHMARK MODE — direct API call, no Hermes.\n\n"
        "Translate the following JSON segments from English to German following your SOUL.md directives.\n"
        "Return ONLY a valid JSON array. Each element must have exactly two fields: "
        "'id' (same as input) and 'translation' (German text).\n"
        "No preamble, no markdown fencing, no explanation.\n\n"
        f"Segments:\n{segs_text}"
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=soul_md,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text
    translations = parse_translation_response(raw)

    return {
        "translations": translations,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
        "model": response.model,
    }


def translate_glm(model: str, soul_md: str, segments: list[dict]) -> dict:
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai SDK not installed. Run: pip install openai", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("GLM_API_KEY")
    if not api_key:
        print("ERROR: GLM_API_KEY not set in environment", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(
        api_key=api_key,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
    )

    segs_text = json.dumps(segments, ensure_ascii=False, indent=2)
    user_msg = (
        "BENCHMARK MODE. Translate the following JSON segments from English to German. "
        "Return ONLY a valid JSON array with 'id' and 'translation' fields per element. "
        "No preamble or markdown fencing.\n\n"
        f"Segments:\n{segs_text}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": soul_md},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=4096,
    )

    raw = response.choices[0].message.content
    translations = parse_translation_response(raw)

    usage = response.usage
    return {
        "translations": translations,
        "usage": {
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
        },
        "model": model,
    }


def price_per_run(model: str, usage: dict) -> float | None:
    inp, out = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    if "opus" in model:
        return (inp / 1e6 * 15.0) + (out / 1e6 * 75.0)
    if "sonnet" in model:
        return (inp / 1e6 * 3.0) + (out / 1e6 * 15.0)
    if "haiku" in model:
        return (inp / 1e6 * 0.80) + (out / 1e6 * 4.0)
    return None  # GLM: free/unknown


def main():
    parser = argparse.ArgumentParser(
        description="Translate a run's source segments with a candidate model (direct API, no Hermes)"
    )
    parser.add_argument("--run", required=True, help="Reference run ID (e.g. 2026-06-02_002)")
    parser.add_argument("--model", required=True, help="Candidate model ID (e.g. claude-sonnet-4-20250514)")
    args = parser.parse_args()

    run_id = args.run
    model = args.model
    slug = model_slug(model)

    run_dir = CORPUS / run_id
    if not run_dir.exists():
        print(f"ERROR: Run directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    # Load inputs
    print(f"Loading segments from {run_id}/source/segments.json...")
    segments = load_segments(run_id)
    print(f"  {len(segments)} segments")

    print("Loading translator SOUL.md...")
    soul_md = load_soul_md("translator")
    print(f"  {len(soul_md):,} chars")

    # Translate
    is_glm = "glm" in model.lower()
    provider = "GLM / z.ai" if is_glm else "Anthropic"
    print(f"Translating with {model} ({provider})...")

    result = translate_glm(model, soul_md, segments) if is_glm else translate_anthropic(model, soul_md, segments)

    # Load reference to get source texts (in case segments.json is minimal)
    ref_path = run_dir / "final" / "translation_draft.json"
    with open(ref_path, encoding="utf-8") as f:
        ref = json.load(f)

    ref_by_id = {s["id"]: s["source"] for s in ref["segments"]}
    ref_model = ref.get("translator", {}).get("model", "claude-opus-4-20250514")

    trans_by_id = {t["id"]: t["translation"] for t in result["translations"]}

    # Build output preserving source order from reference
    output_segments = [
        {"id": sid, "source": src, "translation": trans_by_id.get(sid, "")}
        for sid, src in ref_by_id.items()
    ]

    usage = result["usage"]
    cost = price_per_run(result["model"], usage)

    output = {
        "_schema": "interpretation-ai-cell/translation-draft/v1",
        "_benchmark": {
            "mode": "direct-api",
            "reference_run": run_id,
            "reference_model": ref_model,
            "candidate_model": result["model"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "exact_token_counts": True,
        },
        "run_id": run_id,
        "translator": {
            "profile": "translator",
            "model": result["model"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "_usage": {
            "model": result["model"],
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "segments_processed": len(output_segments),
            "source": "exact-api-response",
            "cost_usd": cost,
        },
        "segments": output_segments,
    }

    out_dir = run_dir / "benchmark" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "translation_draft.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDone:")
    print(f"  Model:          {result['model']}")
    print(f"  Segments:       {len(output_segments)}")
    print(f"  Input tokens:   {usage['input_tokens']:,}  (exact)")
    print(f"  Output tokens:  {usage['output_tokens']:,}  (exact)")
    if cost is not None:
        print(f"  Cost:           ${cost:.4f}")
    else:
        print(f"  Cost:           ~$0.00 (GLM free tier)")
    print(f"  Output:         {out_path.relative_to(ROOT)}")
    print(f"\nNext: make benchmark-quick RUN={run_id} MODEL={model}")


if __name__ == "__main__":
    main()
