# Skills Reference

This document catalogs every skill in the Interpretation AI Cell pipeline, organized by owner profile. Skills are the fundamental units of capability -- each one encodes a specific translation or audit behavior that an agent can invoke during processing.

## How Skills Work

### Skill File Format

Each skill is defined as a `SKILL.md` file with YAML frontmatter followed by Markdown instructions. Skills live in the owning profile's directory:

```
profiles/
  translator/
    skills/
      glossary-enforcement.skill.md
      ab-model-routing.skill.md
      segmentation.skill.md
  wittgenstein/
    skills/
      idiom-localization.skill.md
      pragmatic-context.skill.md
      register-detection.skill.md
  ...
```

### SKILL.md Structure

```markdown
---
name: glossary-enforcement
version: 2
owner: translator
trigger: always                    # always | on-match | on-demand
priority: 100                     # higher = runs first in collision
domain: ["*"]                     # which domains this skill applies to
status: active                    # active | archived
created: 2026-05-15
updated: 2026-05-28
---

# Glossary Enforcement

## Purpose
Ensures all terms present in shared/glossary.yml are translated using
the approved target term. Overrides model preference when a glossary
match exists.

## Behavior
1. Scan source TU for glossary matches (case-insensitive).
2. For each match, enforce the glossary target in the translation.
3. If the model produced a different translation, replace it and log
   the override in the TU metadata.

## Constraints
- Glossary matches are exact phrase matches, not substring.
- If a term appears in a compound word, do not enforce (flag for review).
- Defer to Frege if glossary entry is marked `review_required: true`.
```

### How Hermes Loads and Invokes Skills

The Hermes Agent runtime loads skills at profile initialization:

1. **Profile boot**: When a profile is activated, Hermes reads all `*.skill.md` files from the profile's `skills/` directory.
2. **Frontmatter parsing**: YAML frontmatter is parsed to determine trigger conditions, priority, domain scope, and status. Only `status: active` skills are loaded.
3. **Skill injection**: Active skills are injected into the agent's system prompt as structured instructions. The skill's Markdown body becomes part of the agent's operational context.
4. **Trigger evaluation**: During TU processing, the dispatcher evaluates each skill's trigger:
   - `always`: Skill is active for every TU
   - `on-match`: Skill activates only when its domain matches the TU's domain tag
   - `on-demand`: Skill activates only when explicitly requested by another agent or human
5. **Priority resolution**: When multiple skills are active, they execute in priority order (highest first). Collisions are detected by Vaswani during audits.

### Skill Lifecycle

```
creation → active → archived
```

- **Creation**: A new skill is drafted as a `SKILL.md` file, committed to the profile's `skills/` directory, and set to `status: active`.
- **Active**: The skill is loaded by Hermes and participates in translation processing. It accumulates usage metrics tracked in `logs/skills/`.
- **Archived**: After Vaswani recommends pruning and a human approves, the skill's status is changed to `archived`. It remains in the repository for reference but is no longer loaded by Hermes. Archived skills can be reactivated by changing status back to `active`.

---

## Translator Skills

The Translator is the primary translation agent. It produces the initial EN-to-DE translation and manages model routing.

### glossary-enforcement

| Field | Value |
|-------|-------|
| **Name** | `glossary-enforcement` |
| **Owner** | Translator |
| **Trigger** | `always` |
| **Priority** | 100 |
| **Domain** | `["*"]` (all domains) |

**Purpose**: Ensures all terms present in `shared/glossary.yml` are translated using the approved target term. Overrides model output when a glossary match is found, guaranteeing terminology consistency across all translations.

**Behavior**: Scans the source TU for exact phrase matches against the glossary. When a match is found and the model's translation differs from the glossary entry, the glossary term is substituted and the override is logged in TU metadata. Compound words containing glossary terms are flagged for human review rather than auto-replaced.

---

### ab-model-routing

| Field | Value |
|-------|-------|
| **Name** | `ab-model-routing` |
| **Owner** | Translator |
| **Trigger** | `always` |
| **Priority** | 90 |
| **Domain** | `["*"]` |

**Purpose**: Routes translation units to different model variants (Claude Opus 4 vs Claude Sonnet 4) based on A/B test configuration, enabling data-driven quality/cost comparison.

**Behavior**: Reads the current A/B test configuration from `shared/ab-config.yml`. Assigns each incoming TU to a variant based on the configured split ratio (e.g., 70/30). Tags the TU with the assigned variant for downstream quality tracking. Vaswani's weekly audit analyzes the accumulated results.

---

### segmentation

| Field | Value |
|-------|-------|
| **Name** | `segmentation` |
| **Owner** | Translator |
| **Trigger** | `always` |
| **Priority** | 110 |
| **Domain** | `["*"]` |

**Purpose**: Splits incoming text into translation units (TUs) at appropriate boundaries -- sentence-level by default, with adjustments for lists, headings, and code blocks.

**Behavior**: Processes raw input text before translation begins. Uses sentence boundary detection with special handling for abbreviations (e.g., "e.g.", "Dr.", "Nr."), numbered lists, and markdown structures. Each segment becomes an independent TU that flows through the pipeline. Segments that are too short (< 3 words) are merged with adjacent segments to avoid fragmentation.

---

## Wittgenstein Skills

Wittgenstein handles pragmatic and contextual aspects of translation -- the "meaning in use" layer.

### idiom-localization

| Field | Value |
|-------|-------|
| **Name** | `idiom-localization` |
| **Owner** | Wittgenstein |
| **Trigger** | `on-match` |
| **Priority** | 80 |
| **Domain** | `["general", "business", "marketing"]` |

**Purpose**: Detects English idiomatic expressions and replaces them with culturally equivalent German idioms rather than literal translations.

**Behavior**: Maintains an internal catalog of EN idioms mapped to DE equivalents (e.g., "break the ice" -> "das Eis brechen", "kick the bucket" -> "den Loffel abgeben"). When an idiom is detected in the source TU, Wittgenstein checks whether the Translator's output used a literal translation and suggests the idiomatic equivalent. For idioms without a direct DE equivalent, Wittgenstein proposes a natural paraphrase.

---

### pragmatic-context

| Field | Value |
|-------|-------|
| **Name** | `pragmatic-context` |
| **Owner** | Wittgenstein |
| **Trigger** | `always` |
| **Priority** | 70 |
| **Domain** | `["*"]` |

**Purpose**: Analyzes the broader communicative intent of a TU -- not just what it says, but what it does (informing, persuading, instructing, warning) -- and ensures the German translation preserves that pragmatic function.

**Behavior**: Classifies each TU by speech act type (assertive, directive, commissive, expressive, declarative). Verifies that the translation preserves the illocutionary force. For example, a polite English request ("Could you please...") should map to the appropriate German politeness level ("Konnten Sie bitte...") rather than a literal conditional.

---

### register-detection

| Field | Value |
|-------|-------|
| **Name** | `register-detection` |
| **Owner** | Wittgenstein |
| **Trigger** | `always` |
| **Priority** | 75 |
| **Domain** | `["*"]` |

**Purpose**: Identifies the formality register of the source text (formal, neutral, informal, colloquial) and ensures the German translation maintains the same register, including appropriate use of "Sie" vs "du."

**Behavior**: Analyzes lexical and syntactic cues in the source TU to determine register. Checks the translation for register consistency. Flags mismatches such as formal source text translated with informal German constructions. Works in conjunction with Frege's `formality-calibration` skill -- register-detection identifies the register; formality-calibration enforces the rules.

---

## Quine Skills

Quine handles semantic ambiguity and indeterminacy -- the philosophical edge cases of translation.

### ambiguity-scoring

| Field | Value |
|-------|-------|
| **Name** | `ambiguity-scoring` |
| **Owner** | Quine |
| **Trigger** | `always` |
| **Priority** | 60 |
| **Domain** | `["*"]` |

**Purpose**: Assigns an ambiguity score (0.0-1.0) to each TU, indicating how many valid alternative translations exist. High-ambiguity TUs are flagged for additional review or human intervention.

**Behavior**: Analyzes the source TU for lexical ambiguity (polysemous words), structural ambiguity (attachment, scope), and referential ambiguity (pronoun resolution). Produces a numeric score and a list of ambiguity sources. TUs scoring above 0.7 are automatically routed for human review. TUs between 0.4-0.7 receive additional context from Wittgenstein's pragmatic-context skill.

---

### indeterminacy-detection

| Field | Value |
|-------|-------|
| **Name** | `indeterminacy-detection` |
| **Owner** | Quine |
| **Trigger** | `on-match` |
| **Priority** | 55 |
| **Domain** | `["legal", "medical", "technical"]` |

**Purpose**: Detects cases of genuine translation indeterminacy -- where no single German translation can fully capture the source meaning -- and documents the trade-offs of each alternative.

**Behavior**: Inspired by Quine's thesis of the indeterminacy of translation, this skill identifies TUs where multiple valid translations exist with meaningfully different implications. For each such case, Quine produces an indeterminacy report listing alternatives, their semantic differences, and a recommended choice with justification. This is particularly critical in legal and medical domains where word choice has material consequences.

---

## Frege Skills

Frege handles semantic precision and tone -- the "sense and reference" layer.

### sinn-bedeutung

| Field | Value |
|-------|-------|
| **Name** | `sinn-bedeutung` |
| **Owner** | Frege |
| **Trigger** | `always` |
| **Priority** | 85 |
| **Domain** | `["*"]` |

**Purpose**: Ensures that translations preserve both the sense (Sinn -- the mode of presentation) and the reference (Bedeutung -- what is being referred to) of the source text, catching cases where a translation is referentially correct but semantically misleading.

**Behavior**: Analyzes whether the German translation, while denoting the same referent as the English source, might convey a different connotation or framing. For example, "employee" and "Mitarbeiter" refer to the same concept but carry different connotations (hierarchical vs collaborative). Frege flags these differences and, when significant, suggests alternatives or adds translator notes.

---

### tone-preservation

| Field | Value |
|-------|-------|
| **Name** | `tone-preservation` |
| **Owner** | Frege |
| **Trigger** | `always` |
| **Priority** | 78 |
| **Domain** | `["*"]` |

**Purpose**: Preserves the emotional tone and attitude of the source text in the German translation -- urgency, enthusiasm, caution, authority, empathy, etc.

**Behavior**: Classifies the source TU's tone along multiple dimensions (urgency, formality, warmth, authority). Compares the tone profile of the translation against the source. Flags significant tone shifts (e.g., an urgent English warning translated into a neutral German statement). Recommends specific lexical or syntactic adjustments to restore tone alignment.

---

### formality-calibration

| Field | Value |
|-------|-------|
| **Name** | `formality-calibration` |
| **Owner** | Frege |
| **Trigger** | `always` |
| **Priority** | 76 |
| **Domain** | `["*"]` |

**Purpose**: Enforces consistent formality rules in German output, particularly the Sie/du distinction, sentence structure formality, and vocabulary register.

**Behavior**: Works with Wittgenstein's register-detection output. Applies domain-specific formality rules: legal and medical always use Sie; marketing may use du if the source is informal; technical documentation uses Sie unless the source explicitly uses second-person informal. Checks for formality inconsistencies within a single document (mixing Sie and du). Frege has final authority on formality decisions.

---

## Koehn Skills (Scientist)

Koehn's skills are audit-focused, not translation-producing.

### diff-audit

| Field | Value |
|-------|-------|
| **Name** | `diff-audit` |
| **Owner** | Koehn |
| **Trigger** | `on-demand` (per-merge) |
| **Priority** | N/A (audit) |
| **Domain** | `["*"]` |

**Purpose**: Compares the merged translation against the initial Translator output to quantify how much the review pipeline changed the translation, identifying patterns in correction types.

**Behavior**: Generates a structured diff between the Translator's initial output and the final merged version. Categorizes changes (terminology, grammar, tone, register, idiom). Tracks change frequency by category over time. Feeds into regression-detection to identify whether correction rates are increasing (suggesting Translator quality degradation).

---

### regression-detection

| Field | Value |
|-------|-------|
| **Name** | `regression-detection` |
| **Owner** | Koehn |
| **Trigger** | `on-demand` (per-merge) |
| **Priority** | N/A (audit) |
| **Domain** | `["*"]` |

**Purpose**: Detects when translation quality is declining over time by analyzing correction rates, error patterns, and quality score trends.

**Behavior**: Maintains a rolling window of quality metrics. Computes trend lines for key indicators: correction rate, glossary override frequency, tone mismatch rate, ambiguity scores. When any metric shows a statistically significant downward trend (p < 0.05 over 50+ TUs), triggers a `warn` or `block` depending on severity.

---

## Cho Skills (Scientist)

Cho's skills focus on memory integrity and cross-agent consistency.

### memory-integrity

| Field | Value |
|-------|-------|
| **Name** | `memory-integrity` |
| **Owner** | Cho |
| **Trigger** | `on-demand` (weekly) |
| **Priority** | N/A (audit) |
| **Domain** | `["*"]` |

**Purpose**: Validates the structural and semantic integrity of all shared memory stores -- glossary, corpus, reflections, and configuration files.

**Behavior**: Parses all YAML and configuration files for syntax errors. Checks referential integrity (TU IDs referenced in reflections exist in corpus). Validates glossary entries have all required fields. Checks for duplicate entries, orphaned files, and inconsistent state between the Kanban board and file system.

---

### cross-agent-coherence

| Field | Value |
|-------|-------|
| **Name** | `cross-agent-coherence` |
| **Owner** | Cho |
| **Trigger** | `on-demand` (weekly) |
| **Priority** | N/A (audit) |
| **Domain** | `["*"]` |

**Purpose**: Ensures all agents are operating from a consistent view of shared state and not producing contradictory decisions.

**Behavior**: Compares terminology decisions across agents for the same TUs. Checks that glossary version referenced by each agent matches the current canonical version. Identifies cases where agent reflections contain conflicting conclusions. Validates that Frege's governance decisions are being respected by downstream agents.

---

## Vaswani Skills (Scientist)

Vaswani's skills focus on optimization and system efficiency.

### context-optimization

| Field | Value |
|-------|-------|
| **Name** | `context-optimization` |
| **Owner** | Vaswani |
| **Trigger** | `on-demand` (weekly) |
| **Priority** | N/A (audit) |
| **Domain** | `["*"]` |

**Purpose**: Analyzes token usage across the pipeline and identifies opportunities to reduce context window consumption without degrading translation quality.

**Behavior**: Measures token consumption per pipeline stage (segmentation, translation, review, merge). Identifies stages where context can be compressed (e.g., truncating long reflection histories). Recommends context window allocation adjustments. Monitors for context window saturation events and their causes.

---

### skill-pruning

| Field | Value |
|-------|-------|
| **Name** | `skill-pruning` |
| **Owner** | Vaswani |
| **Trigger** | `on-demand` (weekly) |
| **Priority** | N/A (audit) |
| **Domain** | `["*"]` |

**Purpose**: Identifies skills that are no longer providing value and recommends their archival to reduce system complexity and token overhead.

**Behavior**: Analyzes skill invocation frequency, impact on translation output, and token cost. Skills that have not been invoked in 60+ days are flagged. Skills that are invoked but never change the output are flagged as low-impact. Produces a pruning recommendation report. All pruning requires human approval before execution.

---

## Skill Summary Table

| Skill | Owner | Trigger | Priority | Domain |
|-------|-------|---------|----------|--------|
| segmentation | Translator | always | 110 | * |
| glossary-enforcement | Translator | always | 100 | * |
| ab-model-routing | Translator | always | 90 | * |
| sinn-bedeutung | Frege | always | 85 | * |
| idiom-localization | Wittgenstein | on-match | 80 | general, business, marketing |
| tone-preservation | Frege | always | 78 | * |
| formality-calibration | Frege | always | 76 | * |
| register-detection | Wittgenstein | always | 75 | * |
| pragmatic-context | Wittgenstein | always | 70 | * |
| ambiguity-scoring | Quine | always | 60 | * |
| indeterminacy-detection | Quine | on-match | 55 | legal, medical, technical |
| diff-audit | Koehn | on-demand | -- | * |
| regression-detection | Koehn | on-demand | -- | * |
| memory-integrity | Cho | on-demand | -- | * |
| cross-agent-coherence | Cho | on-demand | -- | * |
| context-optimization | Vaswani | on-demand | -- | * |
| skill-pruning | Vaswani | on-demand | -- | * |
