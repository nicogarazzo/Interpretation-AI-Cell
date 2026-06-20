# 04 - Consensus Protocol

The philosopher consensus mechanism is the quality gate of the Interpretation AI Cell. No translation reaches the corpus without passing through it. This page documents the complete protocol: voting rules, category weights, revision loops, escalation, safety mechanisms, and a worked example.

---

## The 3-Philosopher Panel

Three philosopher agents evaluate every draft translation in parallel:

| Philosopher | Domain Expertise | Core Question |
|---|---|---|
| **Wittgenstein** | Pragmatics, idioms, context | Does the translation preserve the communicative act? |
| **Quine** | Ambiguity, indeterminacy | Did the translation handle ambiguity correctly? |
| **Frege** | Sinn/Bedeutung, tone, register | Does the translation preserve both sense and reference, with correct tone? |

Each philosopher produces a JSON verdict with:

- `verdict`: one of `approve`, `revise`, or `block`
- `confidence`: float 0.0-1.0
- `critique`: structured object with `issues[]` and `approved_spans[]`

---

## Voting Rules

### Basic Rule: 2-of-3 Weighted Approval

The consensus engine requires **2 out of 3 philosophers to approve** for a translation to pass. However, votes are not equal -- they are weighted by category.

### How Weighted Voting Works

1. Each philosopher evaluates the translation and identifies issues, categorizing each one (e.g., `idiom_literal`, `tone_shift`, `ambiguity_introduced`).
2. The consensus engine maps each issue to a **category** from the weight table.
3. Each philosopher's vote is multiplied by their weight for that category.
4. If the weighted vote count for `approve` meets or exceeds the threshold, the translation passes.

For translations with **no category-specific issues** (clean approvals or general concerns), all weights are 1.0 and the vote is a simple 2-of-3 majority.

### Category-Specific Weights

These weights reflect domain expertise. Each philosopher's vote carries more influence in their area of specialization:

| Category | Wittgenstein | Quine | Frege | Rationale |
|---|---|---|---|---|
| `idiom_resolution` | **1.5** | 1.0 | 0.8 | Wittgenstein is the idiom expert. Frege's opinion on idioms carries less weight. |
| `pragmatics` | **1.5** | 1.0 | 0.8 | Pragmatic equivalence is Wittgenstein's core axis. |
| `ambiguity` | 1.0 | **1.5** | 1.0 | Quine is the ambiguity expert. |
| `tone_and_style` | 0.8 | 0.8 | **1.5** | Frege is the tone/register expert. |
| `factual_accuracy` | 1.0 | 1.0 | **1.5** | Bedeutung errors are Frege's domain. |

### Weight Application Example

Suppose a translation has a `tone_shift` issue (category: `tone_and_style`):

- Wittgenstein votes `approve` (weight 0.8) = 0.8
- Quine votes `approve` (weight 0.8) = 0.8
- Frege votes `revise` (weight 1.5) = 1.5

Approve score: 0.8 + 0.8 = 1.6
Revise score: 1.5

Since `approve` score (1.6) > `revise` score (1.5), the translation passes despite Frege's objection. But if the issue were `factual_accuracy`:

- Wittgenstein votes `approve` (weight 1.0) = 1.0
- Quine votes `approve` (weight 1.0) = 1.0
- Frege votes `block` (weight 1.5) = 1.5

Approve score: 1.0 + 1.0 = 2.0
Block score: 1.5

The translation passes because the combined approve weight exceeds the block weight. However, Frege's block vote is logged and the factual concern is flagged for review even though the translation is approved.

---

## Tie-Breaking: Most Conservative Strategy

When weighted votes result in a tie (or when the outcome is ambiguous), the consensus engine uses the **most_conservative** strategy:

```
approve < revise < block
```

In a tie, the more restrictive verdict wins. This means:

- If `approve` and `revise` are tied, the result is `revise`.
- If `revise` and `block` are tied, the result is `block`.
- If all three verdicts are different (`approve`, `revise`, `block`), the result is `revise` (the middle option).

The rationale: it is better to send a translation through an extra revision round than to release a flawed translation. False negatives (unnecessary revision) waste compute; false positives (releasing bad translations) damage quality.

---

## The Revision Loop

When the consensus verdict is `revise`, the translation enters a revision loop:

```
+-------------------+
| Translator        |
| produces draft    |
+--------+----------+
         |
         v
+--------+----------+
| Philosophers      |
| evaluate          |
+--------+----------+
         |
    verdict?
    /    |    \
approve revise  block
   |      |       |
   v      v       v
  done   Round   Escalate
         +1      (if max
         |        rounds)
         v
  Back to Translator
  with feedback
```

### Feedback Content

When the consensus returns `revise`, the following is sent back to the Translator:

1. **All philosopher critiques** -- the full JSON from each philosopher, including issues with severity, category, source/target spans, explanations, and suggestions.
2. **Consensus summary** -- which philosopher voted how, which categories were contested.
3. **Specific revision instructions** -- aggregated suggestions from all philosophers, deduplicated.

The Translator then produces a new draft incorporating the feedback, and the cycle repeats.

### Revision Round Tracking

Each review task carries a `round` counter:

- Round 1: initial translation
- Round 2: first revision (incorporating Round 1 feedback)
- Round 3: second revision (incorporating Round 2 feedback)

The Kanban board labels tasks with `round-1`, `round-2`, `round-3` for visibility.

---

## Max Rounds (3) and Escalation Protocol

The maximum number of revision rounds is **3** (configurable in `shared/consensus-config.yml`):

```yaml
consensus:
  max_rounds: 3
  cooldown_between_rounds_seconds: 2
```

### What Happens After 3 Rounds

If a translation still does not achieve consensus after 3 rounds, it is **escalated**:

1. The task moves from `review` to `blocked`.
2. A new Kanban task is created with label `human-review-required`.
3. The escalation task includes:
   - Source text
   - All draft translations (from all 3 rounds)
   - All philosopher critiques (from all 3 rounds)
   - Recommended action (typically the last translator draft, since it incorporated the most feedback)

### Human Resolution Commands

A human reviewer can resolve escalated tasks with:

| Command | Effect |
|---|---|
| `/approve <translation>` | Accept a specific version (from any round) |
| `/override <text>` | Provide a manual German translation |
| `/skip` | Skip this translation unit entirely |

### Other Escalation Triggers

| Trigger | Action |
|---|---|
| Max rounds exhausted | Create `human-review-required` Kanban task |
| Unanimous block (all 3 philosophers vote `block`) | Create `human-review-required` Kanban task |
| All agents timeout | Create `human-review-required` Kanban task |

---

## Timeout Handling

Each philosopher has 30 seconds to respond:

```yaml
consensus:
  timeout_per_agent_seconds: 30
```

### Timeout Scenarios

| Scenario | Handling |
|---|---|
| 1 philosopher times out | Proceed with 2-of-2 vote using available responses. Weights are recalculated for 2 voters. |
| 2 philosophers time out | Proceed with the single available response as an advisory. If it is `approve`, the translation passes with a `limited_consensus` flag. If it is `revise` or `block`, escalate. |
| All 3 philosophers time out | Escalate to human review. Create `human-review-required` Kanban task. |

### Why "Proceed with Available"

The `on_timeout: proceed_with_available` strategy (from `consensus-config.yml`) favors progress over perfection. A timeout typically means a transient API issue, not a fundamental problem with the translation. Blocking the entire pipeline because one agent is slow would be counterproductive.

However, the `limited_consensus` flag ensures that scientist agents (especially Koehn) can later audit these translations with extra scrutiny.

---

## Human Escalation

When a translation is escalated, the system creates a structured Kanban task:

```yaml
task:
  type: human-review
  label: human-review-required
  include:
    - source_text
    - all_draft_translations     # From all rounds
    - all_philosopher_critiques  # From all rounds
    - recommended_action         # Usually the last draft
```

### Escalation Channels

The primary escalation channel is the Kanban board itself (the `blocked` column). In the future, escalation may also create GitHub Issues for tracking.

### When Escalation Happens

1. **After max rounds (3)**: The most common case. The translator and philosophers could not agree.
2. **Unanimous block**: All 3 philosophers voted `block` on the same round. This is rare and suggests a fundamental problem with the source text or a systematic translator failure.
3. **All timeouts**: All 3 philosophers failed to respond. This suggests an infrastructure problem (API outage, rate limiting).

---

## Safety Mechanisms

The consensus protocol includes several safety valves to prevent runaway loops and excessive resource consumption:

### Consecutive Block Limit

```yaml
safety:
  max_consecutive_blocks: 2
```

If 2 Translation Units **in a row** are blocked after exhausting max rounds, the dispatcher pauses and creates an alert. This catches systematic failures (e.g., a broken skill, a model regression) that would otherwise produce a stream of blocked tasks.

### Token Budget Per Translation Unit

```yaml
safety:
  max_tokens_per_translation: 50000
```

The total token budget across **all agents** for a single TU is 50,000 tokens. This includes the Translator's prompt/completion, all 3 philosopher evaluations, and any revision round overhead. If this budget is exhausted, the TU is escalated regardless of the current consensus state.

Budget accounting:

- Translator invocation: ~4,000 tokens
- Each philosopher invocation: ~2,000 tokens
- Per round: ~4,000 (translator) + 3 x ~2,000 (philosophers) = ~10,000 tokens
- 3 rounds: ~30,000 tokens
- Remaining headroom: ~20,000 tokens (for retries, context injection, etc.)

### Wall-Clock Timeout

```yaml
safety:
  max_wall_clock_seconds: 120
```

A hard 2-minute timeout per TU. If the TU has not reached `done` within 2 minutes from the start of its first `in_progress` state, it is escalated. This prevents indefinite hangs from API issues, infinite revision loops, or deadlocks.

---

## Worked Example: Translation Through 2 Rounds of Consensus

### Source Text

> "At the end of the day, the CEO realized that their actual revenue was not sensible enough to break the ice with investors."

This sentence is rich in false friends and idioms -- a stress test for the pipeline.

### Round 1: Initial Translation

**Translator** produces:

```json
{
  "translation_id": "tx-20260529-0042",
  "source_text": "At the end of the day, the CEO realized that their actual revenue was not sensible enough to break the ice with investors.",
  "target_text": "Am Ende des Tages erkannte der CEO, dass ihr aktueller Umsatz nicht sensibel genug war, um das Eis mit Investoren zu brechen.",
  "confidence": 0.72,
  "flags": ["multiple potential false friends detected"],
  "glossary_applied": ["revenue -> Umsatz"],
  "model_used": "claude-opus-4-20250514"
}
```

**Wittgenstein** (verdict: `revise`, confidence: 0.91):

```json
{
  "issues": [
    {
      "severity": "major",
      "category": "idiom_literal",
      "span_source": {"start": 0, "end": 22, "text": "At the end of the day"},
      "span_target": {"start": 0, "end": 18, "text": "Am Ende des Tages"},
      "explanation": "Idiomatic expression meaning 'ultimately', not a temporal reference. Literal translation loses pragmatic force.",
      "suggestion": "Letzten Endes"
    }
  ]
}
```

**Quine** (verdict: `approve`, confidence: 0.85):

```json
{
  "issues": [],
  "approved_spans": [
    {"text": "das Eis mit Investoren zu brechen", "note": "Idiom preserves ambiguity appropriately"}
  ]
}
```

**Frege** (verdict: `revise`, confidence: 0.95):

```json
{
  "issues": [
    {
      "severity": "critical",
      "category": "bedeutung_error",
      "span_source": {"start": 57, "end": 71, "text": "actual revenue"},
      "span_target": {"start": 48, "end": 66, "text": "aktueller Umsatz"},
      "explanation": "FALSE FRIEND: 'aktuell' means 'current', not 'actual'. The source means 'tatsaechlicher Umsatz' (real/genuine revenue).",
      "suggestion": "tatsaechlicher Umsatz"
    },
    {
      "severity": "major",
      "category": "bedeutung_error",
      "span_source": {"start": 80, "end": 88, "text": "sensible"},
      "span_target": {"start": 72, "end": 80, "text": "sensibel"},
      "explanation": "FALSE FRIEND: 'sensibel' means 'emotionally sensitive'. 'Sensible' means 'vernuenftig' (reasonable/prudent).",
      "suggestion": "vernuenftig"
    }
  ]
}
```

**Consensus Engine** evaluates:

- Wittgenstein: `revise` (weight 1.0 default)
- Quine: `approve` (weight 1.0 default)
- Frege: `revise` (weight 1.5 for factual_accuracy on the bedeutung_errors)

Approve: 1.0 (Quine)
Revise: 1.0 (Wittgenstein) + 1.5 (Frege) = 2.5

**Result: `revise`**. Feedback sent to Translator with all three critiques.

### Round 2: Revision

**Translator** incorporates feedback and produces:

```json
{
  "translation_id": "tx-20260529-0042",
  "source_text": "At the end of the day, the CEO realized that their actual revenue was not sensible enough to break the ice with investors.",
  "target_text": "Letzten Endes erkannte der CEO, dass ihr tatsaechlicher Umsatz nicht vernuenftig genug war, um das Eis mit den Investoren zu brechen.",
  "confidence": 0.91,
  "flags": [
    "Round 2: incorporated Wittgenstein feedback on idiom",
    "Round 2: incorporated Frege feedback on false friends (aktuell->tatsaechlich, sensibel->vernuenftig)"
  ],
  "glossary_applied": ["revenue -> Umsatz", "at the end of the day -> letzten Endes"],
  "model_used": "claude-opus-4-20250514"
}
```

**Wittgenstein** (verdict: `approve`, confidence: 0.96):

```json
{
  "issues": [],
  "approved_spans": [
    {"text": "Letzten Endes", "note": "Correct pragmatic equivalent for idiomatic 'at the end of the day'"},
    {"text": "das Eis mit den Investoren zu brechen", "note": "Natural idiom preserved with correct article"}
  ]
}
```

**Quine** (verdict: `approve`, confidence: 0.92):

```json
{
  "issues": [],
  "approved_spans": [
    {"text": "tatsaechlicher Umsatz", "note": "Correctly disambiguated false friend"}
  ]
}
```

**Frege** (verdict: `approve`, confidence: 0.94):

```json
{
  "issues": [],
  "approved_spans": [
    {"text": "tatsaechlicher Umsatz", "note": "Bedeutung now correct -- refers to actual revenue"},
    {"text": "vernuenftig genug", "note": "Correct Sinn -- reasonable/prudent, not emotionally sensitive"}
  ]
}
```

**Consensus Engine** evaluates:

- Wittgenstein: `approve`
- Quine: `approve`
- Frege: `approve`

**Result: `approve` (unanimous)**. Translation is committed to `corpus/translations/` and the task moves to `done`.

### Summary of the Example

| Round | Translator Confidence | Wittgenstein | Quine | Frege | Result |
|---|---|---|---|---|---|
| 1 | 0.72 | revise | approve | revise | **revise** |
| 2 | 0.91 | approve | approve | approve | **approve** |

The pipeline caught two false friends (`actual` -> `aktuell`, `sensible` -> `sensibel`) and one literal idiom translation (`at the end of the day` -> `am Ende des Tages`), all of which would have produced misleading German text. The revision loop corrected all three issues in a single round.

Total tokens consumed (approximate): Round 1 (~10,000) + Round 2 (~10,000) = ~20,000 tokens, well within the 50,000 per-TU budget.

Wall-clock time (approximate): Round 1 (~8 seconds) + cooldown (2 seconds) + Round 2 (~8 seconds) = ~18 seconds, well within the 120-second limit.
