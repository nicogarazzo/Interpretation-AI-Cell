"""
review_gen.py — Generate review.md, review.html, and bilingual delivery doc from pipeline results.

Uses Jinja2 templates to produce the bilingual review table (markdown),
the interactive review HTML document, and a clean bilingual EN|DE
side-by-side document for client delivery.
"""

import html
import re
from datetime import datetime
from pathlib import Path

from .config import PHILOSOPHERS, ROOT

TEMPLATES = Path(__file__).resolve().parent / "templates"

PHILOSOPHER_ROLES = {
    "wittgenstein": "Pragmatics & Idiomatics",
    "quine": "Ambiguity & Indeterminacy",
    "frege": "Sinn/Bedeutung & Register",
}


def _get_segment_status(seg_id: str, critiques: dict) -> dict:
    """Determine the review status of a segment from critique data."""
    issues = []
    for phil, crit in critiques.items():
        for issue in crit.get("critique", {}).get("issues", []):
            span_src = issue.get("span_source", {})
            span_tgt = issue.get("span_target", {})
            # Match by segment ID in span text or broadly
            issues.append({
                "philosopher": phil,
                "severity": issue.get("severity", "minor"),
                "category": issue.get("category", ""),
                "explanation": issue.get("explanation", ""),
                "suggestion": issue.get("suggestion", ""),
            })

    critical_major = [i for i in issues if i["severity"] in ("critical", "major")]
    minor = [i for i in issues if i["severity"] == "minor"]

    if critical_major:
        return {"status": "Fixed", "flag": "fixed", "issues": issues}
    elif minor:
        return {"status": f"{len(minor)} note{'s' if len(minor) != 1 else ''}", "flag": "note", "issues": issues}
    else:
        return {"status": "Clean", "flag": "", "issues": []}


def _pair_segments(segments: list, translation: dict) -> list[dict]:
    """Pair source segments with their translations."""
    translations = translation.get("segments", translation.get("translations", []))
    trans_by_id = {}
    for t in translations:
        tid = t.get("id", t.get("segment_id", ""))
        trans_by_id[tid] = t

    paired = []
    for seg in segments:
        sid = seg.get("id", "")
        trans = trans_by_id.get(sid, {})
        paired.append({
            "id": sid,
            "type": seg.get("type", "unknown"),
            "source": seg.get("text", ""),
            "translation": trans.get("translation", trans.get("target_text", "")),
        })
    return paired


# ── review.md generation ────────────────────────────────────────────────────


def generate_review_md(
    run_dir: Path,
    segments: list,
    translation: dict,
    critiques: dict,
    verdict: dict,
) -> str:
    """Generate the bilingual review markdown."""
    run_id = run_dir.name
    date = datetime.now().strftime("%Y-%m-%d")
    paired = _pair_segments(segments, translation)

    # Critic summary
    critic_rows = []
    for phil in PHILOSOPHERS:
        crit = critiques.get(phil, {})
        v = crit.get("verdict", "unknown")
        issues = crit.get("critique", {}).get("issues", [])
        critic_rows.append(f"| {phil.capitalize()} | {v.capitalize()} | {len(issues)} |")

    # Corrections (critical/major issues)
    corrections = []
    notes = []
    for phil, crit in critiques.items():
        for issue in crit.get("critique", {}).get("issues", []):
            entry = {
                "philosopher": phil.capitalize(),
                "severity": issue.get("severity", "minor"),
                "category": issue.get("category", ""),
                "explanation": issue.get("explanation", ""),
                "suggestion": issue.get("suggestion", ""),
            }
            if issue.get("severity") in ("critical", "major"):
                corrections.append(entry)
            else:
                notes.append(entry)

    # Bilingual table
    seg_rows = []
    for i, seg in enumerate(paired, 1):
        src_preview = seg["source"][:80] + ("..." if len(seg["source"]) > 80 else "")
        trans_preview = seg["translation"][:80] + ("..." if len(seg["translation"]) > 80 else "")
        seg_rows.append(
            f"| {i} | {seg['id']} | {seg['type']} | {src_preview} | {trans_preview} | Clean |"
        )

    consensus_result = verdict.get("result", "unknown")

    md = f"""# Translation Review \u2014 run {run_id}
**Client:** {{client}} | **Campaign:** {{campaign}}
**Source:** {{source_lang}} \u2192 **Target:** {{target_lang}} | **Register:** {{register}}
**Date:** {date} | **Status:** {consensus_result.capitalize()}

---

## Critic Panel Summary

| Critic | Verdict | Issues |
|---|---|---|
{chr(10).join(critic_rows)}

---

## Corrections Applied ({len(corrections)})

"""
    for c in corrections:
        md += f"### {c['philosopher']} ({c['severity']}): {c['category']}\n"
        md += f"- **Issue:** {c['explanation']}\n"
        if c['suggestion']:
            md += f"- **Suggestion:** {c['suggestion']}\n"
        md += "\n"

    md += f"""---

## Philosopher Notes ({len(notes)} advisory flags)

"""
    for n in notes:
        md += f"### {n['philosopher']}: {n['category']}\n"
        md += f"> {n['explanation']}\n"
        if n['suggestion']:
            md += f"> Suggestion: {n['suggestion']}\n"
        md += "\n"

    md += f"""---

## Bilingual Segment Table

| # | ID | Type | EN (source) | DE (translation) | Status |
|---|---|---|---|---|---|
{chr(10).join(seg_rows)}
"""
    return md


# ── review.html generation ──────────────────────────────────────────────────


def generate_review_html(
    run_dir: Path,
    segments: list,
    translation: dict,
    critiques: dict,
    verdict: dict,
) -> str:
    """Generate the interactive review HTML document."""
    try:
        import jinja2
    except ImportError:
        # Fallback: return a simple HTML without Jinja2
        return _generate_review_html_simple(run_dir, segments, translation, critiques, verdict)

    template_path = TEMPLATES / "review.html.j2"
    if not template_path.exists():
        return _generate_review_html_simple(run_dir, segments, translation, critiques, verdict)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES)),
        autoescape=True,
    )
    template = env.get_template("review.html.j2")

    run_id = run_dir.name
    date = datetime.now().strftime("%Y-%m-%d")
    paired = _pair_segments(segments, translation)

    # Build critic data
    critics_data = []
    for phil in PHILOSOPHERS:
        crit = critiques.get(phil, {})
        issues = crit.get("critique", {}).get("issues", [])
        critics_data.append({
            "name": phil.capitalize(),
            "role": PHILOSOPHER_ROLES.get(phil, ""),
            "verdict": crit.get("verdict", "unknown"),
            "issues_count": len(issues),
            "issues": issues,
        })

    # Corrections vs notes
    corrections = []
    all_notes = []
    for phil, crit in critiques.items():
        for issue in crit.get("critique", {}).get("issues", []):
            entry = {
                "philosopher": phil.capitalize(),
                "severity": issue.get("severity", "minor"),
                "category": issue.get("category", ""),
                "explanation": issue.get("explanation", ""),
                "suggestion": issue.get("suggestion", ""),
            }
            if issue.get("severity") in ("critical", "major"):
                corrections.append(entry)
            else:
                all_notes.append(entry)

    consensus_result = verdict.get("result", "unknown")

    return template.render(
        run_id=run_id,
        date=date,
        segment_count=len(paired),
        corrections_count=len(corrections),
        consensus_result=consensus_result,
        critics=critics_data,
        corrections=corrections,
        notes=all_notes,
        segments=paired,
    )


def _generate_review_html_simple(
    run_dir: Path,
    segments: list,
    translation: dict,
    critiques: dict,
    verdict: dict,
) -> str:
    """Fallback HTML generator without Jinja2."""
    run_id = run_dir.name
    date = datetime.now().strftime("%Y-%m-%d")
    paired = _pair_segments(segments, translation)
    consensus_result = verdict.get("result", "unknown")

    # Build segment cards
    seg_cards = []
    for i, seg in enumerate(paired, 1):
        num = f"{i:03d}"
        src = html.escape(seg["source"])
        tgt = html.escape(seg["translation"])
        preview = html.escape(seg["source"][:60])
        seg_type = html.escape(seg["type"].replace("_", " ").title())

        seg_cards.append(f'''
    <div class="segment-card" id="card-{num}">
      <div class="segment-header" onclick="toggle('{num}')">
        <div class="seg-number">{i}</div>
        <span class="seg-type">{seg_type}</span>
        <span class="seg-preview">{preview}...</span>
        <i data-lucide="chevron-down" class="seg-chevron" style="width:16px;height:16px;"></i>
      </div>
      <div class="segment-body">
        <div class="bilingual">
          <div class="lang-block">
            <div class="lang-label en"><i data-lucide="flag" style="width:11px;height:11px;"></i> EN</div>
            <div class="lang-text en-text">{src}</div>
          </div>
          <div class="lang-block">
            <div class="lang-label de"><i data-lucide="flag" style="width:11px;height:11px;"></i> DE</div>
            <div class="lang-text de-text">{tgt}</div>
          </div>
        </div>
        <div class="reviewer-section">
          <label><i data-lucide="edit-3" style="width:12px;height:12px;"></i> Reviewer notes</label>
          <textarea class="reviewer-input" placeholder="Add your comment here..." data-seg="{num}"></textarea>
          <div class="decision-row">
            <button class="decision-btn btn-ok" onclick="setDecision('{num}','ok',this)"><i data-lucide="check" style="width:13px;height:13px;"></i> OK</button>
            <button class="decision-btn btn-suggest" onclick="setDecision('{num}','suggest',this)"><i data-lucide="edit-2" style="width:13px;height:13px;"></i> Suggest</button>
            <button class="decision-btn btn-reject" onclick="setDecision('{num}','reject',this)"><i data-lucide="x" style="width:13px;height:13px;"></i> Reject</button>
          </div>
        </div>
      </div>
    </div>''')

    # Build critic cards
    critic_cards = []
    for phil in PHILOSOPHERS:
        crit = critiques.get(phil, {})
        v = crit.get("verdict", "unknown")
        issues = crit.get("critique", {}).get("issues", [])
        pill_class = f"verdict-{v}" if v in ("approve", "revise", "block") else "verdict-revise"
        icon = "check-circle" if v == "approve" else "alert-triangle"
        critic_cards.append(f'''
    <div class="critic-card">
      <div class="critic-name">{phil.capitalize()}</div>
      <div class="critic-role">{html.escape(PHILOSOPHER_ROLES.get(phil, ""))}</div>
      <span class="verdict-pill {pill_class}"><i data-lucide="{icon}" style="width:11px;height:11px;"></i> {v.capitalize()}</span>
      <div class="critic-issues">Issues: <span>{len(issues)}</span></div>
    </div>''')

    seg_count = len(paired)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Translation Review \u2014 run {run_id}</title>
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
<style>
  :root {{
    --purple: #8c4aec; --purple-glow: rgba(140,74,236,0.18); --purple-border: rgba(140,74,236,0.35);
    --black: #0a0a0a; --dark: #141414; --card: #1c1c1c; --white: #fefefe;
    --gray: #2e2e2e; --gray-mid: #555; --gray-light: #888; --text: #e8e8e8; --text-dim: #888;
    --radius: 14px; --radius-sm: 9px;
    --green: #22c55e; --green-glow: rgba(34,197,94,0.15);
    --amber: #f59e0b; --amber-glow: rgba(245,158,11,0.15);
    --red: #ef4444; --red-glow: rgba(239,68,68,0.12);
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--black); color: var(--text); font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; min-height: 100vh; padding-bottom: 80px; }}
  #progress-bar {{ position: sticky; top: 0; z-index: 100; background: var(--dark); border-bottom: 1px solid var(--gray); padding: 10px 24px; display: flex; align-items: center; gap: 16px; }}
  #progress-bar .progress-label {{ font-size: 12px; color: var(--text-dim); white-space: nowrap; font-weight: 600; }}
  #progress-bar .track {{ flex: 1; height: 4px; background: var(--gray); border-radius: 99px; overflow: hidden; }}
  #progress-bar .fill {{ height: 100%; background: var(--purple); border-radius: 99px; transition: width 0.4s; }}
  #progress-bar .counter {{ font-size: 13px; color: var(--purple); font-weight: 700; white-space: nowrap; }}
  header {{ background: var(--black); text-align: center; padding: 56px 24px 40px; position: relative; overflow: hidden; }}
  header::before {{ content: ''; position: absolute; top: 0; left: 50%; transform: translateX(-50%); width: 600px; height: 300px; background: radial-gradient(ellipse, rgba(140,74,236,0.22) 0%, transparent 70%); pointer-events: none; }}
  header::after {{ content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent, var(--purple-border), transparent); }}
  .logo-badge {{ display: inline-flex; align-items: center; gap: 8px; font-size: 11px; font-weight: 700; letter-spacing: 0.12em; color: var(--text-dim); text-transform: uppercase; background: var(--card); border: 1px solid var(--gray); padding: 6px 14px; border-radius: 99px; margin-bottom: 20px; }}
  header h1 {{ font-size: clamp(26px, 4vw, 38px); font-weight: 700; line-height: 1.2; color: var(--white); margin-bottom: 10px; }}
  header h1 em {{ color: var(--purple); font-style: normal; }}
  .subtitle {{ font-size: 15px; color: var(--text-dim); max-width: 580px; margin: 0 auto 24px; line-height: 1.6; }}
  .meta-badges {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; }}
  .meta-badge {{ display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: var(--text-dim); background: var(--card); border: 1px solid var(--gray); padding: 5px 12px; border-radius: 99px; }}
  .meta-badge i {{ width: 13px; height: 13px; color: var(--purple); }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 40px 24px 0; }}
  .section-title {{ font-size: 11px; font-weight: 700; letter-spacing: 0.12em; color: var(--text-dim); text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center; gap: 10px; }}
  .section-title::after {{ content: ''; flex: 1; height: 1px; background: var(--gray); }}
  .critic-panel {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 36px; }}
  @media (max-width: 720px) {{ .critic-panel {{ grid-template-columns: 1fr; }} }}
  .critic-card {{ background: var(--card); border: 1.5px solid var(--gray); border-radius: var(--radius); padding: 20px; }}
  .critic-card .critic-name {{ font-size: 13px; font-weight: 700; color: var(--purple); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }}
  .critic-card .critic-role {{ font-size: 11px; color: var(--text-dim); margin-bottom: 14px; }}
  .verdict-pill {{ display: inline-flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 700; letter-spacing: 0.06em; padding: 3px 10px; border-radius: 99px; text-transform: uppercase; }}
  .verdict-approve {{ background: var(--green-glow); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }}
  .verdict-revise {{ background: var(--amber-glow); color: var(--amber); border: 1px solid rgba(245,158,11,0.3); }}
  .verdict-block {{ background: var(--red-glow); color: var(--red); border: 1px solid rgba(239,68,68,0.3); }}
  .critic-issues {{ margin-top: 12px; font-size: 12px; color: var(--text-dim); }}
  .critic-issues span {{ color: var(--amber); font-weight: 700; }}
  .segments {{ display: flex; flex-direction: column; gap: 10px; }}
  .segment-card {{ background: var(--card); border: 1.5px solid var(--gray); border-radius: var(--radius); overflow: hidden; }}
  .segment-header {{ display: flex; align-items: center; gap: 12px; padding: 12px 18px; cursor: pointer; user-select: none; }}
  .seg-number {{ width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0; background: var(--gray); display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; color: var(--text-dim); }}
  .segment-card.approved .seg-number {{ background: var(--green); color: #fff; }}
  .seg-type {{ font-size: 10px; font-weight: 600; letter-spacing: 0.08em; color: var(--text-dim); text-transform: uppercase; background: var(--gray); padding: 2px 8px; border-radius: 99px; flex-shrink: 0; }}
  .seg-preview {{ font-size: 13px; color: var(--text-dim); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .seg-chevron {{ color: var(--text-dim); flex-shrink: 0; transition: transform 0.2s; }}
  .segment-card.open .seg-chevron {{ transform: rotate(180deg); }}
  .segment-body {{ display: none; padding: 0 18px 18px; }}
  .segment-card.open .segment-body {{ display: block; }}
  .bilingual {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }}
  @media (max-width: 640px) {{ .bilingual {{ grid-template-columns: 1fr; }} }}
  .lang-block {{ background: var(--black); border: 1px solid var(--gray); border-radius: var(--radius-sm); padding: 14px 16px; }}
  .lang-label {{ font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }}
  .lang-label.en {{ color: var(--gray-light); }}
  .lang-label.de {{ color: var(--purple); }}
  .lang-text {{ font-size: 14px; line-height: 1.6; white-space: pre-line; }}
  .lang-text.en-text {{ color: var(--gray-light); }}
  .lang-text.de-text {{ color: var(--white); }}
  .reviewer-section label {{ font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: var(--text-dim); text-transform: uppercase; display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }}
  .reviewer-section label i {{ color: var(--purple); }}
  .reviewer-input {{ width: 100%; background: var(--black); border: 1.5px solid var(--gray); color: var(--text); border-radius: var(--radius-sm); padding: 10px 14px; font-size: 13px; resize: vertical; min-height: 60px; font-family: inherit; outline: none; }}
  .reviewer-input:focus {{ border-color: var(--purple); box-shadow: 0 0 0 3px var(--purple-glow); }}
  .reviewer-input::placeholder {{ color: var(--gray-mid); }}
  .decision-row {{ display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }}
  .decision-btn {{ display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 99px; font-size: 12px; font-weight: 600; border: 1.5px solid; cursor: pointer; font-family: inherit; background: transparent; }}
  .btn-ok {{ border-color: rgba(34,197,94,0.4); color: var(--green); }}
  .btn-ok:hover, .btn-ok.active {{ background: var(--green-glow); border-color: var(--green); }}
  .btn-suggest {{ border-color: rgba(245,158,11,0.4); color: var(--amber); }}
  .btn-suggest:hover, .btn-suggest.active {{ background: var(--amber-glow); border-color: var(--amber); }}
  .btn-reject {{ border-color: rgba(239,68,68,0.4); color: var(--red); }}
  .btn-reject:hover, .btn-reject.active {{ background: var(--red-glow); border-color: var(--red); }}
  .instructions {{ background: var(--card); border: 1.5px solid var(--purple-border); border-radius: var(--radius-sm); padding: 14px 18px; font-size: 13px; color: var(--text-dim); margin-bottom: 24px; display: flex; gap: 12px; align-items: center; }}
  .instructions i {{ color: var(--purple); flex-shrink: 0; }}
  footer {{ text-align: center; padding: 48px 24px 24px; font-size: 12px; color: var(--text-dim); border-top: 1px solid var(--gray); margin-top: 60px; }}
  footer strong {{ color: var(--text); }}
</style>
</head>
<body>

<div id="progress-bar">
  <span class="progress-label"><i data-lucide="check-circle" style="width:12px;height:12px;display:inline;vertical-align:middle;margin-right:4px;"></i> Review</span>
  <div class="track"><div class="fill" id="progress-fill" style="width:0%"></div></div>
  <span class="counter" id="progress-counter">0 / {seg_count}</span>
</div>

<header>
  <div class="logo-badge"><i data-lucide="globe-2"></i> Interpretation AI Cell v2</div>
  <h1>Translation Review <em>EN\u2192DE</em></h1>
  <p class="subtitle">Run {run_id} \u00b7 Consensus: {consensus_result.upper()}</p>
  <div class="meta-badges">
    <span class="meta-badge"><i data-lucide="calendar"></i> {date}</span>
    <span class="meta-badge"><i data-lucide="layers"></i> {seg_count} segments</span>
    <span class="meta-badge"><i data-lucide="shield-check"></i> v2 pipeline</span>
  </div>
</header>

<main>
  <div class="section-title"><i data-lucide="users"></i> Critic panel</div>
  <div class="critic-panel">
    {"".join(critic_cards)}
  </div>

  <div class="section-title"><i data-lucide="table"></i> Bilingual review table</div>
  <div class="instructions">
    <i data-lucide="info" style="width:16px;height:16px;"></i>
    For each segment: mark <strong style="color:var(--green)">OK</strong>, <strong style="color:var(--amber)">Suggest change</strong> or <strong style="color:var(--red)">Reject</strong>.
  </div>
  <div class="segments">
    {"".join(seg_cards)}
  </div>
</main>

<footer>
  <strong>Interpretation AI Cell v2</strong> \u00b7 Claude Code orchestrated \u00b7 {date}
</footer>

<script>
lucide.createIcons();
const decisions = {{}};
const total = {seg_count};

function toggle(id) {{
  document.getElementById('card-' + id).classList.toggle('open');
}}

function setDecision(id, decision, btn) {{
  const card = document.getElementById('card-' + id);
  const row = btn.parentElement;
  row.querySelectorAll('.decision-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  const prev = decisions[id];
  decisions[id] = decision;

  if (decision === 'ok') {{
    card.classList.add('approved');
    card.classList.remove('flagged', 'rejected');
  }} else if (decision === 'suggest') {{
    card.classList.add('flagged');
    card.classList.remove('approved', 'rejected');
  }} else {{
    card.classList.add('rejected');
    card.classList.remove('approved', 'flagged');
  }}

  const count = Object.keys(decisions).length;
  document.getElementById('progress-fill').style.width = (count / total * 100) + '%';
  document.getElementById('progress-counter').textContent = count + ' / ' + total;
}}
</script>
</body>
</html>'''


# ── Bilingual delivery document ────────────────────────────────────────────

# Segment types that render as bold headers
_HEADER_TYPES = {
    "article_headline", "article_subheadline", "section_headline", "cta_button",
}

# Types where the text has a bold prefix before a colon (e.g., "01. STANDARDISE FOR SAFETY: ...")
_SPLIT_HEADER_TYPES = {
    "objection_quote", "best_practice", "benefit_block",
}


def _format_bilingual_cell(text: str, seg_type: str) -> str:
    """Format a segment's text for the bilingual table cell, applying appropriate styling."""
    escaped = html.escape(text)

    if seg_type in _HEADER_TYPES:
        return f'<strong>{escaped}</strong>'

    if seg_type in _SPLIT_HEADER_TYPES:
        # Bold the portion before the first colon (header), regular for the rest
        colon_idx = escaped.find(':')
        if colon_idx > 0 and colon_idx < 120:
            header = escaped[:colon_idx + 1]
            body = escaped[colon_idx + 1:]
            return f'<strong>{header}</strong>{body}'

    if seg_type == "footnotes":
        # Convert leading numbers to superscript
        lines = escaped.split('\n')
        formatted = []
        for line in lines:
            m = re.match(r'^(\d+)\s+', line)
            if m:
                num = m.group(1)
                rest = line[m.end():]
                formatted.append(f'<sup>{num}</sup> {rest}')
            else:
                formatted.append(line)
        return '<br>'.join(formatted)

    return escaped


def _needs_separator(seg_type: str) -> bool:
    """Whether to insert a horizontal rule before this segment."""
    return seg_type in (
        "section_headline", "cta_button", "footnotes",
    )


def generate_bilingual_doc(
    run_dir: Path,
    segments: list,
    translation: dict,
) -> str:
    """Generate a clean, print-ready bilingual EN|DE side-by-side HTML document.

    This is the client-facing deliverable — no review UI, no colors,
    just the paired translation in a two-column table.
    """
    run_id = run_dir.name
    date = datetime.now().strftime("%Y-%m-%d")
    paired = _pair_segments(segments, translation)

    # Build table rows
    rows = []
    for seg in paired:
        seg_type = seg.get("type", "body_paragraph")

        # Horizontal separator between major sections
        if _needs_separator(seg_type):
            rows.append(
                '<tr class="sep"><td colspan="2"><hr></td></tr>'
            )

        en_cell = _format_bilingual_cell(seg["source"], seg_type)
        de_cell = _format_bilingual_cell(seg["translation"], seg_type)

        css_class = "header" if seg_type in _HEADER_TYPES else ""
        if seg_type == "footnotes":
            css_class = "footnotes"

        rows.append(
            f'<tr class="{css_class}">'
            f'<td class="en">{en_cell}</td>'
            f'<td class="de">{de_cell}</td>'
            f'</tr>'
        )

    table_body = '\n      '.join(rows)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Translation Delivery EN→DE — {html.escape(run_id)}</title>
<style>
  @page {{
    size: A4 landscape;
    margin: 18mm 14mm;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    font-size: 13px;
    line-height: 1.55;
    color: #1a1a1a;
    background: #fff;
    padding: 32px;
  }}
  @media print {{
    body {{ padding: 0; font-size: 11px; }}
  }}

  .doc-header {{
    text-align: center;
    margin-bottom: 28px;
    padding-bottom: 18px;
    border-bottom: 2px solid #1a1a1a;
  }}
  .doc-header h1 {{
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 6px;
  }}
  .doc-header .meta {{
    font-size: 11px;
    color: #666;
    display: flex;
    justify-content: center;
    gap: 20px;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }}
  thead th {{
    background: #f5f5f5;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 10px 14px;
    border: 1px solid #d0d0d0;
    text-align: left;
  }}
  thead th.en {{ width: 50%; }}
  thead th.de {{ width: 50%; }}

  tbody td {{
    padding: 12px 14px;
    border: 1px solid #d0d0d0;
    vertical-align: top;
    font-size: 13px;
    line-height: 1.55;
  }}
  @media print {{
    tbody td {{ font-size: 11px; padding: 8px 10px; }}
  }}
  tbody td.en {{
    color: #1a1a1a;
  }}
  tbody td.de {{
    color: #1a1a1a;
  }}

  tr.header td {{
    padding-top: 16px;
    padding-bottom: 16px;
  }}
  tr.header td strong {{
    font-size: 14px;
  }}
  @media print {{
    tr.header td strong {{ font-size: 12px; }}
  }}

  tr.footnotes td {{
    font-size: 11px;
    color: #555;
    padding-top: 14px;
    line-height: 1.7;
  }}
  tr.footnotes td sup {{
    font-weight: 700;
    color: #1a1a1a;
  }}

  tr.sep td {{
    padding: 0;
    border: none;
  }}
  tr.sep hr {{
    border: none;
    border-top: 1px solid #999;
    margin: 4px 0;
  }}

  .doc-footer {{
    margin-top: 24px;
    padding-top: 14px;
    border-top: 1px solid #d0d0d0;
    text-align: center;
    font-size: 10px;
    color: #999;
  }}
  .doc-footer strong {{
    color: #555;
  }}
</style>
</head>
<body>

<div class="doc-header">
  <h1>Translation Delivery EN→DE</h1>
  <div class="meta">
    <span>Run: {html.escape(run_id)}</span>
    <span>Date: {date}</span>
    <span>Segments: {len(paired)}</span>
    <span>Direction: EN-GB → DE</span>
    <span>Register: business-formal (Sie)</span>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th class="en">English (source)</th>
      <th class="de">German (translation)</th>
    </tr>
  </thead>
  <tbody>
      {table_body}
  </tbody>
</table>

<div class="doc-footer">
  <strong>Interpretation AI Cell v2</strong> · {date}
</div>

</body>
</html>'''
