---
name: skill-pruning
description: Identify and manage underused or conflicting skills across all agent profiles
trigger: weekly scheduled audit (Sunday 04:00 UTC)
---

# Skill Pruning

Vaswani maintains skill hygiene across the cell by identifying skills that have become dead weight, conflict with other skills, or signal identity drift in an agent.

## Pruning Criteria

| Condition | Threshold | Action |
|---|---|---|
| Zero invocations | 0 invocations in last 100 translations | **Archive** — move to `skills/archived/` |
| Low confidence | Confidence score < 0.5 (from feedback correlation) | **Review** — flag for human evaluation |
| Never invoked after onboarding | 0 invocations after 50+ translations since skill was created | **Delete** — remove entirely with git record |
| Superseded | Another skill in the same agent covers the same trigger with higher confidence | **Merge** — combine into the dominant skill |

## Invocation Tracking

For each skill, track:

- `invocation_count`: total times the skill was triggered in the analysis window.
- `last_invoked`: timestamp of the most recent invocation.
- `contribution_rate`: percentage of invocations where the skill's output influenced the final verdict (cited in feedback or changed the translation).
- `confidence`: `contribution_rate * (invocation_count / expected_invocations)`, clamped to [0, 1].

## Collision Detection

Compare trigger patterns across skills within the same agent:

1. **Extract triggers** from each SKILL.md frontmatter.
2. **Normalize triggers** to a canonical form (lowercase, remove articles, stem verbs).
3. **Pairwise similarity:** if two triggers within the same agent have >70% token overlap, flag as a potential collision.
4. **Functional collision:** if two skills produce contradictory guidance on the same input (tested against the last 10 shared invocations), escalate to `CONFLICT`.

## Archive Protocol

When a skill meets archive criteria:

1. **Add archive metadata** to the SKILL.md YAML frontmatter:
   ```yaml
   archived: true
   archived_date: 2026-05-29
   archived_reason: "0 invocations in last 100 translations"
   archived_by: vaswani/skill-pruning
   ```
2. **Move** the skill directory to `profiles/{agent}/skills/archived/{skill-name}/`.
3. **Update** the agent's skill index if one exists.
4. **Log** the archival in `pruning-log.md`.

Skills can be restored by reversing this process if they become relevant again.

## Identity Drift Detection

Each agent's SOUL.md defines its core identity. Skills and memory should evolve within that identity, not away from it.

1. **Compute SOUL.md hash** (SHA-256 of the file contents, excluding whitespace normalization).
2. **Compare** against the stored baseline in `drift_baseline.json`.
3. **If hash differs**, the SOUL has been modified:
   - Diff the current SOUL.md against the baseline version.
   - Classify changes as `COSMETIC` (formatting, typos), `EVOLUTION` (new capabilities within identity), or `DRIFT` (contradiction with original identity).
   - `DRIFT` triggers an alert for human review.
4. **Skill-SOUL alignment check:** for each active skill, verify that its stated purpose aligns with the agent's SOUL.md role description. Flag skills that serve a purpose outside the agent's declared domain.

## Output

Produce `pruning-report.md` with:
- Per-agent skill inventory table (name, invocations, confidence, last invoked, status)
- Archive candidates with reasons
- Collision report (trigger overlaps and functional conflicts)
- Identity drift assessment per agent (hash match, change classification)
- Recommended actions
