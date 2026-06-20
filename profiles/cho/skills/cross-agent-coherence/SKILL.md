---
name: cross-agent-coherence
description: Detect contradictions between agent memories and skills across all profiles
trigger: weekly scheduled audit (Sunday 03:00 UTC)
---

# Cross-Agent Coherence Audit

Cho ensures that the collective knowledge and rules distributed across all agents remain internally consistent. When agents develop contradictory beliefs or conflicting rules through independent learning, the translation pipeline produces inconsistent output.

## Cross-Reference Matrix

For every unique pair of agents (philosopher x philosopher, philosopher x translator), compare:

1. **Skill rules.** Extract all prescriptive statements from each SKILL.md (lines containing "must", "should", "always", "never", "prefer", "avoid").
2. **Learned patterns.** Extract all patterns from MEMORY.md that encode translation preferences.
3. **State assertions.** Extract active rules from state.db.

Build a contradiction matrix:

```
           Wittgenstein  Frege  Quine  Translator
Wittgenstein     -         ?      ?       ?
Frege            ?         -      ?       ?
Quine            ?         ?      -       ?
Translator       ?         ?      ?       -
```

Each cell is either `OK` (no conflicts), `WARN` (soft tension), or `CONFLICT` (hard contradiction).

## Known Conflict Zones

### Wittgenstein vs Frege on Register

- **Wittgenstein** tends to preserve source-text register and pragmatic tone, even if it means less precise terminology.
- **Frege** insists on terminological precision and formal consistency, even if the source uses informal register.
- **Domain authority:** Wittgenstein prevails on register decisions for general prose; Frege prevails when domain-specific terminology is at stake.

### Quine vs Wittgenstein on Ambiguity Handling

- **Quine** favors disambiguation: if a source term is ambiguous, resolve it to the most determinate translation.
- **Wittgenstein** favors preserving ambiguity: if the source author chose an ambiguous term, the translation should remain equally open.
- **Domain authority:** Quine prevails for technical/legal texts where ambiguity is a defect; Wittgenstein prevails for literary/philosophical texts where ambiguity is a feature.

## Contradiction Detection Protocol

1. **Extract rules** from all SKILL.md files as structured assertions: `(agent, scope, directive, strength)`.
2. **Pairwise comparison.** For each pair of assertions with overlapping scope, check if directives conflict.
3. **Memory cross-check.** For each learned pattern in MEMORY.md, verify it does not contradict an active skill rule in any other agent.
4. **Temporal check.** If two conflicting rules were both updated recently, the conflict is `ACTIVE`. If one is stale (not reinforced in 200+ translations), the conflict is `DORMANT`.

## Severity Classification

| Severity | Condition | Example |
|---|---|---|
| `LOW` | Soft tension, both rules can coexist with context-dependent application | Different preferences for comma usage |
| `MEDIUM` | Rules conflict on a common case, but domain authority resolves it | Register disagreement on technical text |
| `HIGH` | Direct contradiction with no clear domain authority resolution | Two agents mandate opposite translations for the same term |

## Resolution Protocol

1. **Flag** the contradiction with severity, the two agents involved, and the specific rules.
2. **Recommend** which agent's rule should prevail based on domain authority (see Known Conflict Zones).
3. **If no domain authority applies**, escalate to human review with both rules and three example translations where the conflict manifests.
4. **Log** the resolution decision in `coherence-log.md` so future audits can verify compliance.

## Output

Produce `coherence-report.md` with:
- The contradiction matrix (agent x agent)
- Detailed conflict descriptions with severity
- Recommended resolutions
- Overall coherence score: number of conflicts / total rule pairs checked
