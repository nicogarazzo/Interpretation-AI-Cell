"""
agents.py — Assemble agent system prompts from SOUL.md + skills.

Reads profiles/<agent>/SOUL.md and profiles/<agent>/skills/*/SKILL.md,
strips Hermes-specific Kanban protocol sections, and appends v2 output
instructions. Produces a single system prompt string per agent.
"""

import re
from pathlib import Path

from .config import PROFILES, SHARED, load_glossary

# ── Kanban stripping ────────────────────────────────────────────────────────

_KANBAN_HEADING = re.compile(
    r"^##\s+Kanban\s+Worker\s+Protocol.*",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

# References to kanban tools that appear in other sections (e.g., Output Format)
_KANBAN_REFS = re.compile(
    r",?\s*then\s+call\s+`kanban_complete`\.?",
    re.IGNORECASE,
)

_V2_OUTPUT_TRANSLATOR = """
## Output Protocol (v2)

Return a valid JSON object matching the schema described in your Output Format section above.
Do NOT use any external tools. Do NOT print preamble or markdown fencing.
Output ONLY the JSON object.
""".strip()

_V2_OUTPUT_PHILOSOPHER = """
## Output Protocol (v2)

Return a valid JSON object with your verdict, confidence, and critique.
The `verdict` field MUST be exactly one of: "approve", "revise", or "block".
Do NOT use any external tools. Do NOT print preamble or markdown fencing.
Output ONLY the JSON object.
""".strip()

_V2_OUTPUT_SCIENTIST = """
## Output Protocol (v2)

Return a valid JSON object matching the output format described above.
Do NOT use any external tools. Do NOT print preamble or markdown fencing.
Output ONLY the JSON object.
""".strip()


def _strip_kanban_protocol(soul_md: str) -> str:
    """Remove the '## Kanban Worker Protocol' section and inline kanban references."""
    result = _KANBAN_HEADING.sub("", soul_md)
    result = _KANBAN_REFS.sub(".", result)
    # Clean up any remaining kanban tool mentions
    result = re.sub(r"`kanban_complete`", "", result)
    result = re.sub(r"`kanban_block`", "", result)
    result = re.sub(r"`kanban_show`", "", result)
    return result.rstrip()


def _get_v2_output_instructions(agent_name: str) -> str:
    if agent_name == "translator":
        return _V2_OUTPUT_TRANSLATOR
    elif agent_name in ("wittgenstein", "quine", "frege"):
        return _V2_OUTPUT_PHILOSOPHER
    else:
        return _V2_OUTPUT_SCIENTIST


def _load_soul_md(agent_name: str) -> str:
    """Read profiles/<agent>/SOUL.md."""
    path = PROFILES / agent_name / "SOUL.md"
    return path.read_text(encoding="utf-8")


def _load_skills(agent_name: str) -> list[tuple[str, str]]:
    """Read all profiles/<agent>/skills/*/SKILL.md files.

    Returns list of (skill_name, content) tuples.
    """
    skills_dir = PROFILES / agent_name / "skills"
    if not skills_dir.exists():
        return []

    result = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            content = skill_file.read_text(encoding="utf-8")
            result.append((skill_dir.name, content))
    return result


def _format_glossary_section() -> str:
    """Format the shared glossary as a prompt section."""
    glossary = load_glossary()
    terms = glossary.get("terms", [])
    if not terms:
        return ""

    lines = [
        "\n\n---\n## REFERENCE: Canonical EN-DE Glossary\n",
        "Use these canonical translations. Deviating from this glossary is a blocking error.\n",
        "| English | German | Domain | Notes |",
        "|---|---|---|---|",
    ]
    for t in terms:
        en = t.get("en", "")
        de = t.get("de", "")
        domain = t.get("domain", "")
        notes = t.get("notes", "")
        lines.append(f"| {en} | {de} | {domain} | {notes} |")

    return "\n".join(lines)


def build_system_prompt(agent_name: str) -> str:
    """Build the complete system prompt for an agent.

    Assembles: SOUL.md (stripped of Kanban protocol) + v2 output instructions
    + all skills + glossary (translator only).
    """
    # Load and strip SOUL.md
    soul_md = _load_soul_md(agent_name)
    soul_md = _strip_kanban_protocol(soul_md)

    # Append v2 output instructions
    soul_md += "\n\n" + _get_v2_output_instructions(agent_name)

    # Append skills
    skills = _load_skills(agent_name)
    for skill_name, content in skills:
        soul_md += f"\n\n---\n## SKILL: {skill_name}\n\n{content}"

    # Translator gets the glossary too
    if agent_name == "translator":
        soul_md += _format_glossary_section()

    return soul_md


def list_agents() -> list[str]:
    """List all agent profile names from the profiles/ directory."""
    return [
        d.name
        for d in sorted(PROFILES.iterdir())
        if d.is_dir() and (d / "SOUL.md").exists()
    ]
