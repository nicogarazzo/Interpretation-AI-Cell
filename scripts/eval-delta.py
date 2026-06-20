#!/usr/bin/env python3
"""
eval-delta.py — Compute Delta Stack quality metrics (D₁ + D₂ + optional D₃).

Compares a benchmarked candidate translation against the reference (Opus 4 gold standard).

Usage:
    python3 scripts/eval-delta.py --run 2026-06-02_002 --model claude-sonnet-4-20250514
    python3 scripts/eval-delta.py --run 2026-06-02_002 --model claude-sonnet-4-20250514 --include-critics

Metrics:
    D₁  chrF2      character n-gram F2-score (sacrebleu) — lexical fidelity
    D₂  Glossary   Client term compliance rate — domain adherence
    D₃  Critics    Philosopher verdict concordance — loaded from benchmark-critics output

    ΔScore = 0.40×D₁ + 0.25×D₂ + 0.35×D₃   (with critics)
    ΔScore = 0.62×D₁ + 0.38×D₂              (without critics)

Thresholds:
    ≥ 85   GREEN  — Equivalent quality. Suitable for client deliverables.
    70–84  YELLOW — Mild degradation. Internal drafts only + human review.
    55–69  ORANGE — Moderate degradation. Not suitable for this client.
    < 55   RED    — Significant degradation. Discard.
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from sacrebleu.metrics import CHRF
except ImportError:
    print("ERROR: sacrebleu not installed. Run: pip install sacrebleu", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "corpus" / "runs"
SHARED = ROOT / "shared"


def model_slug(model: str) -> str:
    return model.replace(".", "-").replace("/", "-")


# ── Umlaut normalization ─────────────────────────────────────────────────────

def normalize_de(text: str) -> str:
    """Lowercase + convert umlauts to ASCII for fuzzy matching."""
    t = text.lower()
    t = t.replace("ü", "ue").replace("ä", "ae").replace("ö", "oe").replace("ß", "ss")
    return t


# ── Glossary compliance (D₂) ─────────────────────────────────────────────────

def load_glossary() -> list[dict]:
    with open(SHARED / "glossary.yml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("terms", [])


def term_in_source(en: str, source_lower: str) -> bool:
    """Check if an EN term (or its singular/plural variant) appears in the source."""
    en_lower = en.lower()
    # Exact match
    if en_lower in source_lower:
        return True
    # Singular (strip trailing 's')
    if en_lower.endswith("s") and en_lower[:-1] in source_lower:
        return True
    # Plural (add 's')
    if (en_lower + "s") in source_lower:
        return True
    return False


def is_brand_term(en: str) -> bool:
    # Brand terms are loaded from the active client skill's glossary.
    # These are example placeholders — override per client engagement.
    brands = []
    return any(b.lower() in en.lower() for b in brands)


def check_glossary_compliance(segments: list[dict], glossary: list[dict]) -> dict:
    """
    For each segment: find applicable glossary terms in source, verify canonical DE
    appears in candidate translation. Returns per-segment results and overall rate.

    Actively checks:
        - Client-specific domain terms (all)
        - False friends (ensuring correct DE, not the false friend)
    """
    active_terms = [
        t for t in glossary
        if t.get("domain", "").endswith("-manufacturing")
        or "FALSE FRIEND" in t.get("notes", "")
    ]

    per_segment = []
    total_applicable = 0
    total_correct = 0

    for seg in segments:
        source_lower = seg["source"].lower()
        translation = seg.get("translation", "")
        trans_norm = normalize_de(translation)

        checks = []
        for term in active_terms:
            en = term["en"]
            if not term_in_source(en, source_lower):
                continue

            de_canonical = term["de"]

            if is_brand_term(en):
                # Brand names must appear verbatim (strip ®/™ for matching)
                base = re.sub(r"[®™]", "", en).lower()
                correct = base in translation.lower()
            else:
                de_norm = normalize_de(de_canonical)
                correct = de_norm in trans_norm

            checks.append({
                "term_en": en,
                "term_de": de_canonical,
                "correct": correct,
                "domain": term.get("domain", ""),
            })
            total_applicable += 1
            if correct:
                total_correct += 1

        per_segment.append({
            "id": seg["id"],
            "applicable_terms": len(checks),
            "checks": checks,
        })

    compliance_rate = (total_correct / total_applicable * 100) if total_applicable > 0 else 100.0
    return {
        "compliance_rate": round(compliance_rate, 1),
        "total_applicable": total_applicable,
        "total_correct": total_correct,
        "per_segment": per_segment,
    }


# ── chrF2 (D₁) ───────────────────────────────────────────────────────────────

def compute_chrf2(ref_segs: list[dict], hyp_segs: list[dict]) -> dict:
    """Corpus-level + per-segment chrF2 (beta=2 → recall-weighted)."""
    chrf = CHRF(beta=2)

    ref_map = {s["id"]: s["translation"] for s in ref_segs}
    hyp_map = {s["id"]: s["translation"] for s in hyp_segs}
    ids = [s["id"] for s in ref_segs]

    per_seg = []
    for sid in ids:
        r = ref_map.get(sid, "")
        h = hyp_map.get(sid, "")
        if r and h:
            score = chrf.sentence_score(h, [r]).score
            per_seg.append({"id": sid, "chrf2": round(score, 2)})
        else:
            per_seg.append({"id": sid, "chrf2": None})

    refs = [ref_map.get(sid, "") for sid in ids]
    hyps = [hyp_map.get(sid, "") for sid in ids]
    corpus = chrf.corpus_score(hyps, [refs]).score

    return {
        "corpus_chrf2": round(corpus, 2),
        "per_segment": per_seg,
    }


# ── Delta Score ───────────────────────────────────────────────────────────────

def compute_delta(d1: float, d2: float, d3: float | None) -> tuple[float, str]:
    if d3 is not None:
        score = 0.40 * d1 + 0.25 * d2 + 0.35 * d3
        formula = f"0.40×{d1:.1f} + 0.25×{d2:.1f} + 0.35×{d3:.1f}"
    else:
        # Redistribute 0.35 proportionally between D₁ and D₂
        score = 0.615 * d1 + 0.385 * d2
        formula = f"0.615×{d1:.1f} + 0.385×{d2:.1f}  [D₃ absent]"
    return round(score, 1), formula


def score_label(s: float) -> str:
    if s >= 85:
        return "🟢 GREEN"
    if s >= 70:
        return "🟡 YELLOW"
    if s >= 55:
        return "🟠 ORANGE"
    return "🔴 RED"


def score_verdict(s: float) -> str:
    if s >= 85:
        return "Equivalent quality — suitable for client deliverables."
    if s >= 70:
        return "Mild degradation — internal drafts only, requires human review."
    if s >= 55:
        return "Moderate degradation — not suitable for this client."
    return "Significant degradation — discard."


# ── Cost helpers ─────────────────────────────────────────────────────────────

def estimate_cost(model: str, usage: dict) -> float | None:
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    if "opus" in model:
        return (inp / 1e6 * 15.0) + (out / 1e6 * 75.0)
    if "sonnet" in model:
        return (inp / 1e6 * 3.0) + (out / 1e6 * 15.0)
    if "haiku" in model:
        return (inp / 1e6 * 0.80) + (out / 1e6 * 4.0)
    return None


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Compute Delta Stack quality metrics")
    parser.add_argument("--run", required=True, help="Run ID (e.g. 2026-06-02_002)")
    parser.add_argument("--model", required=True, help="Candidate model or slug")
    parser.add_argument(
        "--include-critics",
        action="store_true",
        help="Include D₃ from benchmark-critics output (requires benchmark-critics to have run first)",
    )
    args = parser.parse_args()

    run_id = args.run
    model = args.model
    slug = model_slug(model)

    run_dir = CORPUS / run_id
    bench_dir = run_dir / "benchmark" / slug

    # Load reference
    ref_path = run_dir / "final" / "translation_draft.json"
    if not ref_path.exists():
        print(f"ERROR: Reference not found: {ref_path}", file=sys.stderr)
        sys.exit(1)
    with open(ref_path, encoding="utf-8") as f:
        ref_data = json.load(f)
    ref_model = ref_data.get("translator", {}).get("model", "claude-opus-4-20250514")
    ref_segs = ref_data["segments"]

    # Load candidate
    cand_path = bench_dir / "translation_draft.json"
    if not cand_path.exists():
        print(f"ERROR: Candidate not found: {cand_path}", file=sys.stderr)
        print(f"  Run first: make benchmark RUN={run_id} MODEL={model}", file=sys.stderr)
        sys.exit(1)
    with open(cand_path, encoding="utf-8") as f:
        cand_data = json.load(f)
    cand_segs = cand_data["segments"]
    cand_usage = cand_data.get("_usage", {})
    cand_model = cand_data.get("_benchmark", {}).get("candidate_model", model)

    # Load glossary
    glossary = load_glossary()

    print(f"\n{'═'*60}")
    print(f"  DELTA STACK — Quality Benchmark")
    print(f"{'═'*60}")
    print(f"  Run:       {run_id}")
    print(f"  Reference: {ref_model}")
    print(f"  Candidate: {cand_model}")
    print(f"{'═'*60}\n")

    # D₁ — chrF2
    print("Computing D₁ — chrF2...")
    chrf = compute_chrf2(ref_segs, cand_segs)
    d1 = chrf["corpus_chrf2"]
    print(f"  Corpus chrF2: {d1:.2f}\n")

    # D₂ — Glossary
    print("Computing D₂ — Glossary compliance...")
    gloss = check_glossary_compliance(cand_segs, glossary)
    d2 = gloss["compliance_rate"]
    print(f"  {gloss['total_correct']}/{gloss['total_applicable']} terms correct = {d2:.1f}%\n")

    # D₃ — Critics (optional)
    d3 = None
    critics_data = None
    if args.include_critics:
        conc_path = bench_dir / "critics" / "concordance.json"
        if conc_path.exists():
            with open(conc_path, encoding="utf-8") as f:
                critics_data = json.load(f)
            d3 = critics_data.get("concordance_rate")
            print(f"Loading D₃ — Philosopher concordance: {d3:.1f}%\n")
        else:
            print("  WARNING: critics/concordance.json not found.")
            print(f"  Run: make benchmark-critics RUN={run_id} MODEL={model}\n")

    # Per-segment table
    chrf_map = {r["id"]: r["chrf2"] for r in chrf["per_segment"]}
    gloss_map = {r["id"]: r for r in gloss["per_segment"]}

    print(f"{'─'*74}")
    print(f"{'SEG':<8} {'SOURCE (truncated)':<32} {'chrF2':>6}  {'GLOSS':>6}  {'ΔSEG':>5}")
    print(f"{'─'*74}")

    for seg in ref_segs:
        sid = seg["id"]
        src_trunc = seg["source"].replace("\n", " ")[:32]

        chrf_val = chrf_map.get(sid)
        chrf_str = f"{chrf_val:5.1f}" if chrf_val is not None else "  N/A"

        gseg = gloss_map.get(sid, {})
        checks = gseg.get("checks", [])
        if not checks:
            gloss_str = "   —"
        else:
            fails = [c for c in checks if not c["correct"]]
            gloss_str = "  ✓" if not fails else f"✗ {fails[0]['term_en'][:5]}"

        # Per-row mini delta (always D₁+D₂ only, no critics per row)
        if chrf_val is not None:
            seg_d2 = 100.0 if not checks else (
                sum(1 for c in checks if c["correct"]) / len(checks) * 100
            )
            seg_delta, _ = compute_delta(chrf_val, seg_d2, None)
            delta_str = f"{seg_delta:4.0f}"
        else:
            delta_str = " N/A"

        print(f"{sid:<8} {src_trunc:<32} {chrf_str}  {gloss_str:>6}  {delta_str:>5}")

    print(f"{'─'*74}")

    # Delta Score
    score, formula = compute_delta(d1, d2, d3)
    label = score_label(score)
    verdict = score_verdict(score)

    # Cost comparison
    ref_cost = None
    ref_report = run_dir / "final" / "cost-report.json"
    if ref_report.exists():
        with open(ref_report, encoding="utf-8") as f:
            rr = json.load(f)
        ref_cost = rr.get("total_estimated_cost_usd")

    cand_cost = estimate_cost(cand_model, cand_usage)

    print(f"\n{'═'*60}")
    print(f"  RESULTS")
    print(f"{'═'*60}")
    print(f"  D₁  chrF2:    {d1:.2f} / 100")
    print(f"  D₂  Glossary: {d2:.1f}%  ({gloss['total_correct']}/{gloss['total_applicable']} terms)")
    if d3 is not None:
        print(f"  D₃  Critics:  {d3:.1f}%")
    else:
        print(f"  D₃  Critics:  (not computed — run benchmark-critics)")
    print(f"  {'─'*46}")
    print(f"  ΔScore:       {score:.1f}")
    print(f"  Formula:      {formula}")
    print(f"  Level:        {label}")
    print(f"  Verdict:      {verdict}")
    print(f"  {'─'*46}")
    if ref_cost:
        print(f"  Ref cost:     ${ref_cost:.4f}  ({ref_model})")
    if cand_cost is not None:
        print(f"  Cand cost:    ${cand_cost:.4f}  ({cand_model})")
        if ref_cost and ref_cost > 0:
            savings = (1 - cand_cost / ref_cost) * 100
            print(f"  Savings:      {savings:.1f}%")
    elif "glm" in cand_model.lower():
        print(f"  Cand cost:    ~$0.00 (GLM free tier)")
    if cand_usage.get("input_tokens"):
        print(f"  {'─'*46}")
        print(f"  Input tokens:  {cand_usage['input_tokens']:,}  (exact from API)")
        print(f"  Output tokens: {cand_usage['output_tokens']:,}  (exact from API)")
    print(f"{'═'*60}\n")

    # Write report
    report = {
        "_schema": "interpretation-ai-cell/delta-report/v1",
        "run_id": run_id,
        "reference_model": ref_model,
        "candidate_model": cand_model,
        "d1_chrf2": {
            "corpus_score": d1,
            "per_segment": chrf["per_segment"],
        },
        "d2_glossary": {
            "compliance_rate": d2,
            "total_applicable": gloss["total_applicable"],
            "total_correct": gloss["total_correct"],
            "per_segment": gloss["per_segment"],
        },
        "d3_critics": critics_data,
        "delta_score": score,
        "delta_formula": formula,
        "level": label.split(" ")[1] if " " in label else label,
        "verdict": verdict,
        "cost": {
            "reference_cost_usd": ref_cost,
            "candidate_cost_usd": cand_cost,
            "candidate_input_tokens": cand_usage.get("input_tokens"),
            "candidate_output_tokens": cand_usage.get("output_tokens"),
            "token_count_source": cand_usage.get("source", "unknown"),
        },
    }

    out_path = bench_dir / "delta_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Report: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
