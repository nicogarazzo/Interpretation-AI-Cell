#!/usr/bin/env python3
"""
benchmark-critics.py — Compute D₃ (Philosopher Verdict Concordance) for Delta Stack.

Runs the three philosopher agents (Wittgenstein, Quine, Frege) via direct API call
on a benchmarked candidate translation, then compares verdicts against the reference run.

Usage:
    python3 scripts/benchmark-critics.py --run 2026-06-02_002 --model claude-sonnet-4-20250514
    python3 scripts/benchmark-critics.py --run 2026-06-02_002 --model claude-sonnet-4-20250514 \\
        --critic-model claude-opus-4-20250514   # use a different model for critics

After this, run eval-delta.py with --include-critics to include D₃ in the composite score.

Reads:
    profiles/{wittgenstein,quine,frege}/SOUL.md
    corpus/runs/<run>/benchmark/<slug>/translation_draft.json
    corpus/runs/<run>/final/{wittgenstein,quine,frege}_critique.md  (reference verdicts)

Writes:
    corpus/runs/<run>/benchmark/<slug>/critics/{philosopher}_critique.json
    corpus/runs/<run>/benchmark/<slug>/critics/concordance.json
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

PHILOSOPHERS = ["wittgenstein", "quine", "frege"]


def model_slug(model: str) -> str:
    return model.replace(".", "-").replace("/", "-")


def load_soul_md(profile: str) -> str:
    return (PROFILES / profile / "SOUL.md").read_text(encoding="utf-8")


def parse_json_response(raw: str) -> dict:
    """Strip markdown fencing and parse JSON. Returns dict with _parse_error on failure."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```$", "", text.strip())
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        return {
            "verdict": "unknown",
            "confidence": 0.0,
            "_parse_error": str(e),
            "_raw_preview": text[:300],
        }


# ── Reference verdict parsing ─────────────────────────────────────────────────

def parse_verdict_from_md(md: str) -> str:
    """Extract verdict from a markdown critique file."""
    m = re.search(r"Overall\s+verdict\s*[:—]\s*(APPROVE|REVISE|BLOCK)", md, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    # Fallback: scan first 5 lines
    for line in md.split("\n")[:5]:
        for v in ("approve", "revise", "block"):
            if v in line.lower():
                return v
    return "unknown"


def parse_issue_categories_from_md(md: str) -> list[str]:
    """Extract issue category names mentioned in the markdown critique."""
    cats = re.findall(r"\*\*Category\*\*[:\s]+([a-z_]+)", md, re.IGNORECASE)
    cats += re.findall(r"category[:\s]+([a-z_]+)", md, re.IGNORECASE)
    return list({c.lower() for c in cats})


def load_reference_verdicts(run_dir: Path) -> dict[str, dict]:
    """Load reference philosopher verdicts from final/ directory."""
    verdicts = {}
    for phil in PHILOSOPHERS:
        # Try JSON first (run_001 format), then markdown (run_002 format)
        json_path = run_dir / "final" / f"critique_{phil}.json"
        md_path = run_dir / "final" / f"{phil}_critique.md"

        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            verdicts[phil] = {
                "verdict": data.get("verdict", "unknown").lower(),
                "confidence": data.get("confidence"),
                "categories": [
                    i.get("category", "")
                    for i in data.get("critique", {}).get("issues", [])
                ],
                "source": "json",
            }
        elif md_path.exists():
            md = md_path.read_text(encoding="utf-8")
            verdicts[phil] = {
                "verdict": parse_verdict_from_md(md),
                "confidence": None,
                "categories": parse_issue_categories_from_md(md),
                "source": "markdown",
            }
        else:
            verdicts[phil] = {
                "verdict": "unknown",
                "confidence": None,
                "categories": [],
                "source": "missing",
            }
    return verdicts


# ── API calls ─────────────────────────────────────────────────────────────────

def build_user_message(candidate_json: dict) -> str:
    segs = candidate_json.get("segments", [])
    segs_text = json.dumps(segs, ensure_ascii=False, indent=2)
    return (
        "BENCHMARK MODE — review the following candidate translation.\n"
        "The candidate was produced by a model under evaluation.\n"
        "Apply your full critique process exactly as described in your SOUL.md.\n"
        "Output ONLY valid JSON — no preamble, no markdown fencing.\n\n"
        f"Candidate segments:\n{segs_text}"
    )


def call_philosopher_anthropic(model: str, soul_md: str, candidate_json: dict, philosopher: str) -> dict:
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic SDK not installed. Run: pip install anthropic", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=soul_md,
        messages=[{"role": "user", "content": build_user_message(candidate_json)}],
    )

    critique = parse_json_response(response.content[0].text)
    critique["_benchmark"] = {
        "philosopher": philosopher,
        "model_used": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return critique


def call_philosopher_glm(model: str, soul_md: str, candidate_json: dict, philosopher: str) -> dict:
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai SDK not installed. Run: pip install openai", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("GLM_API_KEY")
    if not api_key:
        print("ERROR: GLM_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": soul_md},
            {"role": "user", "content": build_user_message(candidate_json)},
        ],
        max_tokens=2048,
    )

    critique = parse_json_response(response.choices[0].message.content)
    usage = response.usage
    critique["_benchmark"] = {
        "philosopher": philosopher,
        "model_used": model,
        "input_tokens": usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
    }
    return critique


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Compute D₃ philosopher concordance for Delta Stack benchmarking"
    )
    parser.add_argument("--run", required=True, help="Run ID (e.g. 2026-06-02_002)")
    parser.add_argument("--model", required=True, help="Candidate model (used for translation slug lookup)")
    parser.add_argument(
        "--critic-model",
        default=None,
        help="Model to use for running the critics (default: same as --model). "
             "You can use Opus 4 for critics even if testing Sonnet as translator.",
    )
    args = parser.parse_args()

    run_id = args.run
    cand_model = args.model
    critic_model = args.critic_model or cand_model
    slug = model_slug(cand_model)

    run_dir = CORPUS / run_id
    bench_dir = run_dir / "benchmark" / slug
    critics_dir = bench_dir / "critics"
    critics_dir.mkdir(parents=True, exist_ok=True)

    # Load candidate translation
    cand_path = bench_dir / "translation_draft.json"
    if not cand_path.exists():
        print(f"ERROR: Candidate not found: {cand_path}", file=sys.stderr)
        print(f"  Run: make benchmark RUN={run_id} MODEL={cand_model}", file=sys.stderr)
        sys.exit(1)
    with open(cand_path, encoding="utf-8") as f:
        cand_data = json.load(f)

    # Load reference verdicts
    print(f"\nReference verdicts ({run_id}/final/):")
    ref_verdicts = load_reference_verdicts(run_dir)
    for phil, v in ref_verdicts.items():
        print(f"  {phil:<16} {v['verdict'].upper():<8} [{v['source']}]")

    # Run philosophers
    is_glm = "glm" in critic_model.lower()
    provider = "GLM / z.ai" if is_glm else "Anthropic"
    print(f"\nRunning philosophers via {critic_model} ({provider}):")

    cand_critiques: dict[str, dict] = {}
    for phil in PHILOSOPHERS:
        print(f"  {phil}...", end="", flush=True)
        soul_md = load_soul_md(phil)
        try:
            if is_glm:
                critique = call_philosopher_glm(critic_model, soul_md, cand_data, phil)
            else:
                critique = call_philosopher_anthropic(critic_model, soul_md, cand_data, phil)

            verdict = critique.get("verdict", "unknown").lower()
            conf = critique.get("confidence")
            conf_str = f"  conf={conf:.2f}" if conf is not None else ""
            print(f" {verdict.upper()}{conf_str}")
            cand_critiques[phil] = critique

            out = critics_dir / f"{phil}_critique.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(critique, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f" ERROR: {e}", file=sys.stderr)
            cand_critiques[phil] = {"verdict": "error", "_error": str(e)}

    # Concordance
    print(f"\nVerdict concordance:")
    details = []
    matches = 0

    for phil in PHILOSOPHERS:
        ref_v = ref_verdicts.get(phil, {}).get("verdict", "unknown").lower()
        cand_v = cand_critiques.get(phil, {}).get("verdict", "unknown").lower()
        match = ref_v == cand_v
        if match:
            matches += 1

        ref_conf = ref_verdicts.get(phil, {}).get("confidence")
        cand_conf = cand_critiques.get(phil, {}).get("confidence")

        detail: dict = {
            "philosopher": phil,
            "reference_verdict": ref_v,
            "candidate_verdict": cand_v,
            "match": match,
            "reference_confidence": ref_conf,
            "candidate_confidence": cand_conf,
        }
        if ref_conf is not None and cand_conf is not None:
            detail["confidence_delta"] = round(abs(float(ref_conf) - float(cand_conf)), 3)

        details.append(detail)
        icon = "✓" if match else "✗"
        print(f"  {icon} {phil:<16} ref={ref_v.upper():<8} cand={cand_v.upper()}")

    concordance_rate = (matches / len(PHILOSOPHERS)) * 100
    print(f"\n  D₃ = {matches}/{len(PHILOSOPHERS)} matches = {concordance_rate:.1f}%")

    concordance = {
        "_schema": "interpretation-ai-cell/critics-concordance/v1",
        "run_id": run_id,
        "candidate_model": cand_model,
        "critic_model": critic_model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "concordance_rate": concordance_rate,
        "matches": matches,
        "total": len(PHILOSOPHERS),
        "details": details,
    }

    conc_path = critics_dir / "concordance.json"
    with open(conc_path, "w", encoding="utf-8") as f:
        json.dump(concordance, f, ensure_ascii=False, indent=2)

    print(f"\nWrote: {conc_path.relative_to(ROOT)}")
    print(f"\nNext — include D₃ in Delta Score:")
    print(f"  python3 scripts/eval-delta.py --run {run_id} --model {cand_model} --include-critics")
    print(f"  OR: make benchmark-quick RUN={run_id} MODEL={cand_model} EXTRA=--include-critics")


if __name__ == "__main__":
    main()
