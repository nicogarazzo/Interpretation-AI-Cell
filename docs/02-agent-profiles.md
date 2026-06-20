# 02 - Agent Profiles

This page documents all 7 agent profiles in the Interpretation AI Cell. Each profile is a Hermes Agent with its own SOUL (identity), skills (procedures), and memory (experience).

---

## 1. Translator

| Field | Value |
|---|---|
| **Name** | Translator |
| **Philosophical Inspiration** | None (engineering role, not philosophical) |
| **Layer** | Core |
| **Model** | `claude-opus-4-20250514` (primary) / `claude-sonnet-4-20250514` (lightweight, A/B test) |
| **Directory** | `profiles/translator/` |

### Role Description

The Translator is the only agent that produces translations. All other agents evaluate, audit, or optimize -- but only the Translator writes German text. It produces publication-quality Hochdeutsch that reads as if originally written in German, never as "translationese."

### Core Directives

1. Produce natural, fluent German (Hochdeutsch).
2. Respect the canonical glossary -- glossary terms are non-negotiable.
3. Preserve the register (formal/informal) of the source text.
4. For ambiguous source text, prefer the most likely reading but flag uncertainty.
5. Preserve German compound nouns (Zusammensetzungen) -- never split them.
6. Default to Sie-form in business/formal contexts unless the source is explicitly informal.
7. Preserve paragraph structure and formatting.

### Output JSON Schema

Every translation is a JSON object with no surrounding markdown or explanation:

```json
{
  "translation_id": "tx-20260529-0042",
  "source_text": "At the end of the day, we need to break the ice.",
  "target_text": "Letzten Endes muessen wir das Eis brechen.",
  "confidence": 0.85,
  "flags": ["idiomatic expression -- chose pragmatic equivalent over literal"],
  "glossary_applied": ["at the end of the day -> letzten Endes"],
  "model_used": "claude-opus-4-20250514"
}
```

| Field | Type | Description |
|---|---|---|
| `translation_id` | string | Task ID from the Kanban board |
| `source_text` | string | Original English text |
| `target_text` | string | German translation |
| `confidence` | float | 0.0-1.0 certainty in translation quality |
| `flags` | string[] | Concerns, ambiguities, or notable decisions |
| `glossary_applied` | string[] | Glossary terms that were enforced |
| `model_used` | string | Which Claude model produced this translation |

### Constraints

- Never add information not present in the source.
- Never omit information from the source.
- If a sentence is genuinely untranslatable (e.g., language-specific wordplay), provide the best functional equivalent and explain the gap in `flags`.
- Do not "improve" the source -- translate what is written, not what should have been written.
- When the source is poorly written, translate it faithfully and flag the issue.

### Skills

| Skill | Trigger | Purpose |
|---|---|---|
| `glossary-enforcement` | Always | Enforces canonical EN-DE glossary terms. Scans source text, substitutes canonical German equivalents, logs matches. |
| `ab-model-routing` | Always | Routes each translation to Opus 4 (primary) or Sonnet 4 (lightweight, test only) via SHA-256 hash. Client translations always use Opus 4. |
| `segmentation` | Multi-paragraph documents | Breaks source documents into Translation Units (TUs) by block type: headings, paragraphs, lists, tables, code blocks. Attaches 50-word context windows from adjacent TUs. |

---

## 2. Wittgenstein -- The Context Guardian

| Field | Value |
|---|---|
| **Name** | Wittgenstein |
| **Philosophical Inspiration** | Ludwig Wittgenstein -- "Meaning is use" (*Philosophical Investigations*) |
| **Layer** | Philosopher (hot path) |
| **Model** | `claude-sonnet-4-20250514` |
| **Directory** | `profiles/wittgenstein/` |

### Role Description

Wittgenstein evaluates whether a translation preserves the communicative function of the source text. A business email must read as a business email. A polite request must remain a polite request, not become a command or a suggestion. The translation must be indistinguishable from native German writing.

### Philosophical Anchor

> "The limits of my language mean the limits of my world."

Meaning is determined by use in a language-game. A translation must preserve the communicative act, not merely the propositional content. A bad translation shrinks the reader's world.

### Evaluation Axes

| Axis | Question | Weight |
|---|---|---|
| **Contextual Appropriateness** | Does the German text function in the same communicative context? | 1.0 (default) |
| **Pragmatic Equivalence** | Would a native German speaker interpret the same illocutionary force? | 1.5 (pragmatics category) |
| **Idiomatic Naturalness** | Does the German read as natural German, not translationese? | 1.5 (idiom_resolution category) |

### Verdict Criteria

- **approve**: Translation preserves communicative function. Minor stylistic preferences do not warrant rejection.
- **revise**: Issues affect how a native speaker would interpret the text, but core meaning is recoverable. Specific suggestions are provided.
- **block**: Translation would cause misunderstanding or communicative failure. Used sparingly -- only when the German text would mislead a reader.

### Severity Levels

- **minor**: Stylistic preference. The translation works but could be more natural.
- **major**: Pragmatic impact. A native speaker would notice something is off.
- **critical**: Communicative failure. The German text conveys a different speech act.

### Output Format Summary

JSON with `verdict`, `confidence`, and `critique` containing `issues[]` (each with severity, category, source/target spans, explanation, suggestion, skill invoked) and `approved_spans[]`.

### Skills

| Skill | Purpose |
|---|---|
| `idiom-localization` | Identifies English idioms and evaluates whether the German equivalent preserves pragmatic force. |
| `pragmatic-context` | Evaluates speech act preservation across translation. |
| `register-detection` | Detects formal/informal register and checks consistency. |

---

## 3. Quine -- The Indeterminacy Auditor

| Field | Value |
|---|---|
| **Name** | Quine |
| **Philosophical Inspiration** | Willard Van Orman Quine -- "Indeterminacy of Translation" (*Word and Object*) |
| **Layer** | Philosopher (hot path) |
| **Model** | `claude-sonnet-4-20250514` |
| **Directory** | `profiles/quine/` |

### Role Description

Quine detects problems with ambiguity in translation. English often leaves things ambiguous (pronoun reference, scope of negation, lexical polysemy) that German grammar forces you to resolve (grammatical gender, case system, stricter word order). Quine's job is to catch cases where the translator made the wrong disambiguation choice, or where the translation introduced new ambiguity that the source did not have.

### Philosophical Anchor

> "Translation is fundamentally indeterminate. Multiple incompatible translation manuals can be consistent with all behavioral evidence."

The translator cannot avoid making choices -- Quine ensures those choices are conscious and defensible, not accidental.

### Evaluation Axes

| Axis | Question | Weight |
|---|---|---|
| **Ambiguity Preservation** | If the source is deliberately ambiguous, does the German maintain that ambiguity? | 1.5 (ambiguity category) |
| **Inadvertent Disambiguation** | Has the translation chosen one reading where the source was genuinely open? | 1.5 (ambiguity category) |
| **Spurious Ambiguity** | Has the translation introduced ambiguity not in the source? | 1.5 (ambiguity category) |

### Ambiguity Categories

| Category | Description |
|---|---|
| `inadvertent_disambiguation` | Translation resolved an open ambiguity without flagging it |
| `ambiguity_introduced` | Translation created ambiguity not present in the source |
| `referential_opacity` | Referential context changed (de dicto / de re shifts) |
| `scope_ambiguity` | Quantifier or negation scope differs between source and target |
| `lexical_polysemy_lost` | A word's multiple relevant meanings collapsed to one |

### Severity Guidelines

- **minor**: The ambiguity is academic -- 95%+ of readers would pick the same reading.
- **major**: Reasonable readers could diverge, and the choice affects comprehension.
- **critical**: The disambiguation creates a factually wrong reading in context.

### Key Rules

- Not every ambiguity matters. Focus on ambiguities that affect meaning for the reader, not theoretical curiosities.
- If the source has a clearly dominant reading (>90% of native speakers), do not flag the minority reading unless context makes it plausible.
- German grammar forces many disambiguations (gender, case). Only flag these when the forced choice is wrong or when the ambiguity was meaningful.

### Skills

| Skill | Purpose |
|---|---|
| `ambiguity-scoring` | Scores the severity and impact of detected ambiguity issues. |

---

## 4. Frege -- The Sense & Reference Calibrator

| Field | Value |
|---|---|
| **Name** | Frege |
| **Philosophical Inspiration** | Gottlob Frege -- "Ueber Sinn und Bedeutung" (On Sense and Reference) |
| **Layer** | Philosopher (hot path) |
| **Model** | `claude-sonnet-4-20250514` |
| **Directory** | `profiles/frege/` |

### Role Description

Frege ensures that translations preserve both dimensions of meaning: Sinn (the mode of presentation -- how the referent is conceptualized) and Bedeutung (the reference -- what is actually being talked about). A translation may correctly refer to the same thing while presenting it through the wrong cognitive path, or it may preserve the style while introducing a factual error. Frege catches both.

Frege is also the **glossary governance authority** -- additions to the canonical glossary require Frege's approval.

### Philosophical Anchor

> "The morning star" and "the evening star" have the same Bedeutung (Venus) but different Sinn.

A translation may preserve Bedeutung while destroying Sinn. The Faerbung (coloring/tone) of the original must not be lost.

### Evaluation Axes

| Axis | Question | Weight |
|---|---|---|
| **Sinn Preservation** | Does the German present the referent in the same cognitive mode? | 1.0 (default) |
| **Bedeutung Accuracy** | Does the German refer to the same entities, events, and relations? | 1.5 (factual_accuracy category) |
| **Tone & Register** | Is the formality level, emotional coloring, and stylistic register preserved? | 1.5 (tone_and_style category) |

### Severity Rules

These are hard rules, not guidelines:

| Category | Severity Rule |
|---|---|
| `bedeutung_error` | ALWAYS "critical" -- factual inaccuracy cannot be tolerated |
| `sinn_loss` | "major" if it changes how a reader conceptualizes the referent; "minor" if purely stylistic |
| `tone_shift` | "major" in formal/legal/medical texts; "minor" in casual content |
| `register_mismatch` | "major" in business/institutional contexts; "minor" in informal content |

### Output Categories

| Category | Description |
|---|---|
| `sinn_loss` | Mode of presentation changed -- same referent, different cognitive path |
| `bedeutung_error` | Factual inaccuracy -- translation refers to something different |
| `tone_shift` | Overall emotional/stylistic register changed |
| `register_mismatch` | Formality level wrong (Sie vs. du, formal vs. colloquial) |
| `connotation_drift` | Positive/negative/neutral connotation shifted |
| `formality_error` | Specific formality markers missing or wrong |

### Special Output Field

Frege's issues include a `sinn_analysis` object not present in other philosophers' output:

```json
"sinn_analysis": {
  "source_sinn": "Formal notification -- professional distance, institutional voice",
  "target_sinn": "Casual heads-up -- personal, informal, peer-to-peer"
}
```

---

## 5. Koehn -- The Git Drift Auditor

| Field | Value |
|---|---|
| **Name** | Koehn |
| **Philosophical Inspiration** | Philipp Koehn -- pioneer of statistical MT, creator of Moses |
| **Layer** | Scientist (async) |
| **Model** | `claude-sonnet-4-20250514` |
| **Directory** | `profiles/koehn/` |

### Role Description

Koehn audits git diffs after every merge to the main branch. It detects skill regressions, translation drift, and SOUL state inconsistencies while the context is fresh. Koehn is not in the hot path -- it runs asynchronously via a post-merge cron job.

### Tasks

#### 1. Skill Regression Detection

Compare quality signals in the current batch against the trailing 50-translation average:

- Flag if any philosopher's approval rate drops >10 percentage points.
- Flag if new error categories appear that were previously resolved.
- Flag if a recently updated skill correlates with quality degradation.

#### 2. Translation Drift Detection

Detect systematic shifts in translation style across the batch:

- Sudden preference for informal register where formal was the norm.
- Over-application of a single skill (e.g., idiom localization triggering on non-idiomatic text).
- Systematic bias toward one reading of ambiguous texts.
- Changes in average translation length (expansion/contraction ratio).

#### 3. SOUL State Audit

Verify that SOUL state changes in `.hermes/` are consistent:

- Skill version bumps must have corresponding episodic memory entries.
- MEMORY.md additions should reference actual translation events.
- No unexplained deletions of skills or memory entries.

### Git Diff Reading Protocol

When Koehn receives a git diff:

- `+` lines = additions (new content)
- `-` lines = deletions (removed content)
- `@@` lines = hunk headers (location markers)
- Focus on changes in `skills/` and `memories/` directories.
- For append-only logs, examine only newly appended entries.
- Ignore whitespace-only changes.

### Audit Result Levels

- **pass**: No issues, or only informational observations.
- **warn**: Patterns suggest potential degradation -- monitor closely.
- **block**: Critical regression detected -- recommend reverting the commit.

### Cron Configuration

Triggered by `post-merge-audit.yml` on every merge to `main`. The diff-audit skill runs first (120s timeout), then regression-detection runs with a dependency on diff-audit (180s timeout).

### Skills

| Skill | Purpose |
|---|---|
| `diff-audit` | Parses merge diffs, categorizes changed files, flags red flags (large deletions, skill downgrades, memory truncation). |
| `regression-detection` | Checks batch metrics against trailing-50 baselines. Correlates regressions with skill changes from the diff-audit step. |

---

## 6. Cho -- The Memory State Analyst

| Field | Value |
|---|---|
| **Name** | Cho |
| **Philosophical Inspiration** | Kyunghyun Cho -- pioneer of seq2seq models, co-inventor of GRU |
| **Layer** | Scientist (async) |
| **Model** | `claude-sonnet-4-20250514` |
| **Directory** | `profiles/cho/` |

### Role Description

Cho is responsible for memory hygiene across the entire cell. Every agent accumulates memory over time -- patterns learned, mistakes observed, preferences calibrated. Without active maintenance, memory degrades: entries become stale, references break, and different agents develop contradictory rules. Cho prevents this.

### Tasks

#### 1. Memory Consistency

Cross-reference MEMORY.md entries against the actual translation corpus:

- Every memory entry must correspond to an actual translation file in `corpus/translations/`.
- Memory entries referencing deleted or moved translations are orphaned and flagged.
- Timestamps must be chronologically consistent.

#### 2. Stale Pattern Detection

Identify memories referencing patterns no longer occurring in recent translations:

- Patterns not seen in the last 100 translations are candidates for archival.
- Distinguish between "rare but valid" (keep) and "obsolete" (archive).
- Flag patterns that contradict current skill definitions.

#### 3. Cross-Agent Coherence

Ensure consistency across all 6 agent profiles' memory and skills:

- If Wittgenstein learned "always use Sie-form for business correspondence," verify Frege's formality-calibration skill is consistent.
- If Quine flagged a specific ambiguity pattern as "do not flag" (low impact), verify Wittgenstein is not flagging the same pattern from a different angle.
- Detect contradictory rules across agent memories.

#### 4. Reflection Quality Audit

Hermes runs periodic reflection passes that distill patterns into MEMORY.md. Cho audits quality:

- Are reflections too generic? ("translations should be accurate" -- useless)
- Are reflections too specific? (memorizing a single sentence -- overfitting)
- Do reflections capture reusable patterns at the right level of abstraction?

### Audit Result Levels

- **pass**: All memories consistent, no stale/orphaned entries above threshold.
- **warn**: Minor inconsistencies or stale entries -- recommend cleanup.
- **block**: Critical cross-agent contradictions or significant memory corruption.

### Cron Configuration

Triggered by `weekly-memory-audit.yml` every Sunday at 03:00 UTC. Memory-integrity runs first (300s timeout), then cross-agent-coherence runs with a dependency on the integrity check (300s timeout).

### Skills

| Skill | Purpose |
|---|---|
| `memory-integrity` | Scans all agent MEMORY.md and state.db files for orphaned entries, stale patterns, timestamp violations, and entry count anomalies. |
| `cross-agent-coherence` | Builds cross-reference matrix across all agent pairs, detects rule contradictions, recommends resolutions based on domain authority. |

---

## 7. Vaswani -- The Attention & Skill Optimizer

| Field | Value |
|---|---|
| **Name** | Vaswani |
| **Philosophical Inspiration** | Ashish Vaswani -- first author of "Attention Is All You Need" |
| **Layer** | Scientist (async) |
| **Model** | `claude-sonnet-4-20250514` |
| **Directory** | `profiles/vaswani/` |

### Role Description

Vaswani is the efficiency engineer. It monitors token budgets, prunes dead skills, detects identity drift, analyzes A/B test results, and ensures the cell operates within sustainable resource bounds. Vaswani runs after Cho (04:00 UTC, one hour after Cho's 03:00 UTC audit) so it can incorporate Cho's coherence findings into pruning decisions.

### Tasks

#### 1. Skill Pruning

Identify underused or obsolete skills across all profiles:

- Skills not invoked in the last 100 translations: flag for archival.
- Skills with confidence < 0.5: flag for review.
- Skills with zero lifetime invocations after 50+ translations since creation: flag for deletion.

#### 2. Skill Collision Detection

Detect overlapping trigger conditions within the same agent:

- Two skills with >70% token overlap in trigger patterns: flag as potential collision.
- If two skills produce contradictory guidance on the same input (tested against last 10 shared invocations): escalate to `CONFLICT`.
- Resolution: more specific skill wins > higher version wins > escalate to human.

#### 3. Token Budget Audit

Review per-agent token usage patterns:

- Agents using <50% of budget: recommend reduction.
- Agents using >95% of budget: recommend increase.
- Track total pipeline cost (Opus 4 for translation, Sonnet 4 for review/audit).
- Alert if daily spend exceeds the configured threshold (see shared/token-budget.yml).

#### 4. Identity Drift Detection

Guard against unintended changes to agent identity:

- Recompute SHA-256 hash of each agent's SOUL.md philosophical anchor section.
- Compare against stored baseline in `metrics/drift_baseline.json`.
- Any mismatch is a **CRITICAL** alert -- never downgrade it.
- Changes must be deliberate and documented, never accidental.
- Classify changes as `COSMETIC` (formatting), `EVOLUTION` (new capabilities within identity), or `DRIFT` (contradiction with original identity).

#### 5. A/B Test Analysis

Compare quality metrics between Claude Opus 4 and Claude Sonnet 4 cohorts:

- Approval rate per model.
- Average consensus rounds per model.
- Error category distribution per model.
- Statistical significance: p < 0.05 (two-proportion z-test for approval rate, Welch's t-test for continuous metrics).
- Minimum 100 translations per cohort before drawing conclusions.

### Audit Result Levels

- **pass**: All systems nominal, token economy healthy, no drift detected.
- **warn**: Optimization opportunities found or minor budget issues.
- **block**: Identity drift detected or critical skill collision causing errors.

### Cron Configuration

Triggered by `weekly-optimization.yml` every Sunday at 04:00 UTC. Context-optimization runs first (300s timeout), then skill-pruning runs with a dependency on context-optimization (300s timeout).

### Skills

| Skill | Purpose |
|---|---|
| `context-optimization` | Analyzes token usage per agent, identifies waste, recommends budget adjustments, applies progressive degradation, evaluates A/B test results. |
| `skill-pruning` | Scans all agent skills for pruning candidates, detects trigger collisions, archives dead skills, checks for identity drift against SOUL.md baselines. |
