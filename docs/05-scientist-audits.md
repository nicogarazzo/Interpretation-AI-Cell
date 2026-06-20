# Scientist Audits

The scientist layer provides quality assurance for the Interpretation AI Cell pipeline. Three scientist profiles -- Koehn, Cho, and Vaswani -- run audits at different frequencies and scopes to ensure translation quality, memory integrity, and system optimization.

## Overview

Scientists are non-translating agents. They do not produce translations; instead they inspect the work of the translating agents (Translator, Wittgenstein, Quine, Frege) and the state of the system. Their findings are advisory (pass/warn) or blocking (block), and they feed back into the pipeline via Kanban cards.

| Scientist | Domain | Trigger | Frequency |
|-----------|--------|---------|-----------|
| Koehn | Translation quality | Per-merge | After every merge to `main` corpus |
| Cho | Memory & coherence | Weekly | Cron: Sunday 02:00 UTC |
| Vaswani | Optimization | Weekly | Cron: Sunday 04:00 UTC (after Cho) |

## Execution Order

The scientists have a deliberate execution order:

1. **Cho runs first** -- validates memory consistency and cross-agent coherence. If memory is corrupt, optimization audits would produce misleading results.
2. **Vaswani runs second** -- performs optimization analysis, skill pruning recommendations, and token budget audits. Depends on Cho's memory validation being clean.
3. **Koehn runs per-merge** -- triggered asynchronously whenever a translation unit (TU) is merged into the corpus. Does not wait for the weekly cycle.

This ordering ensures that memory integrity is confirmed before optimization decisions are made, and that translation quality is checked continuously rather than in batches.

---

## Koehn's Audit Protocol

Koehn is the translation quality scientist, named after Philipp Koehn (statistical MT pioneer). Koehn runs after every merge event -- when a translated TU passes through the review pipeline and is committed to the corpus.

### Trigger

A git hook or Kanban transition fires when a TU moves to the `merged` column. The dispatcher invokes Koehn's audit profile against the merged TU and its surrounding context.

### Audit Checks

#### 1. Skill Regression Detection

Koehn compares the current translation output against historical baselines for the same skill set. For each skill that was active during translation:

- Retrieves the last N translations (default: 20) where the same skill was invoked
- Computes a quality delta using the skill's own evaluation criteria
- Flags regression if quality drops below a configurable threshold (default: 5% degradation)

Regression is measured per-skill, not per-translation. This means Koehn can identify that `glossary-enforcement` is performing well while `idiom-localization` has degraded -- allowing targeted remediation.

#### 2. Translation Drift

Translation drift occurs when the system's output style or terminology gradually shifts away from established patterns without an explicit decision to change. Koehn detects drift by:

- Comparing terminology consistency across a sliding window of recent translations
- Checking register stability (formal/informal) against the source document's profile
- Measuring lexical diversity changes that might indicate model behavior shifts

When drift is detected, Koehn generates a drift report that includes:
- Direction of drift (e.g., "increasingly informal register")
- Magnitude (minor / moderate / significant)
- Affected translation units
- Recommended corrective action

#### 3. SOUL State Audit

Koehn verifies that each agent's SOUL.md file has not been corrupted or inadvertently modified:

- Computes SHA-256 hash of each profile's SOUL.md
- Compares against the last known-good hash stored in `shared/soul-hashes.yml`
- If a mismatch is found, triggers a `CRITICAL` alert and pauses the pipeline

This check is a safety net against identity drift -- ensuring that the agents' core instructions haven't been altered by model behavior or file corruption.

### Output

Koehn produces a structured audit report:

```yaml
audit:
  type: merge
  tu_id: "TU-2026-05-29-0042"
  timestamp: "2026-05-29T14:32:00Z"
  checks:
    skill_regression:
      status: pass    # pass | warn | block
      details: "All skills within baseline tolerance"
    translation_drift:
      status: warn
      details: "Minor formality drift detected over last 15 TUs"
      magnitude: minor
      recommendation: "Review register-detection skill parameters"
    soul_state:
      status: pass
      details: "All SOUL.md hashes match"
```

---

## Cho's Audit Protocol

Cho is the memory and coherence scientist, named after Kyunghyun Cho (sequence-to-sequence learning). Cho runs weekly and examines the shared memory layer that all agents read from and write to.

### Trigger

Cron job: `0 2 * * 0` (Sunday 02:00 UTC)

### Audit Checks

#### 1. Memory Consistency

Cho validates the structural integrity of the shared memory stores:

- **Glossary integrity**: Verifies `shared/glossary.yml` parses without errors, all entries have required fields (source, target, domain, approved_by), no duplicate keys
- **Corpus consistency**: Checks that all TUs in the corpus have matching source-target pairs, no orphaned entries
- **Reflection log integrity**: Validates that agent reflection logs (`profiles/{agent}/reflections/`) are well-formed and reference valid TU IDs

#### 2. Stale Pattern Detection

Over time, agents accumulate learned patterns that may become outdated. Cho identifies:

- Skills that haven't been invoked in the last 30 days
- Glossary entries that haven't matched any source text in 60+ days
- Reflection entries that reference deprecated skills or removed TUs
- Cached model routing decisions that predate the current model configuration

Stale patterns are flagged for review, not automatically removed. Removal is Vaswani's domain.

#### 3. Cross-Agent Coherence

Cho checks that agents are working from consistent shared state:

- All agents reference the same glossary version
- No conflicting terminology decisions exist between agents (e.g., Frege approved "Datenschutz" but Translator is using "Privatsphare")
- Agent reflections don't contain contradictory conclusions about the same TU
- The Kanban board state matches the actual file system state (no cards stuck in limbo)

#### 4. Reflection Quality

Cho evaluates whether agent reflections are actually useful:

- Reflections should reference specific decisions, not generic statements
- Each reflection should be tied to a TU ID
- Reflections older than 90 days are flagged for archival review
- Checks for "echo chamber" patterns where agents repeatedly reinforce the same conclusion without new evidence

### Output

```yaml
audit:
  type: weekly_memory
  timestamp: "2026-05-29T02:00:00Z"
  checks:
    memory_consistency:
      status: pass
      glossary_entries: 127
      corpus_tus: 1842
    stale_patterns:
      status: warn
      stale_skills: ["register-detection-v1"]
      stale_glossary_entries: 3
    cross_agent_coherence:
      status: pass
      conflicts: 0
    reflection_quality:
      status: warn
      low_quality_reflections: 7
      recommendation: "Archive 4 reflections older than 90 days"
```

---

## Vaswani's Audit Protocol

Vaswani is the optimization scientist, named after Ashish Vaswani (Transformer architecture / "Attention Is All You Need"). Vaswani runs weekly after Cho and focuses on system efficiency and resource optimization.

### Trigger

Cron job: `0 4 * * 0` (Sunday 04:00 UTC)

### Audit Checks

#### 1. Skill Pruning

Vaswani analyzes skill usage patterns and recommends pruning:

- Skills with zero invocations in 60+ days are candidates for archival
- Skills with consistently low impact (invoked but never changing translation output) are flagged
- Duplicate or overlapping skills are identified for consolidation
- Pruning is always a recommendation -- human approval is required before archival

#### 2. Collision Detection

When multiple skills could apply to the same translation unit, collisions can occur. Vaswani:

- Analyzes the last 100 TUs for cases where 3+ skills were simultaneously active
- Identifies skill pairs that frequently conflict (produce contradictory guidance)
- Recommends priority ordering or scope narrowing for conflicting skills
- Resolution protocol: **specificity > version > human** (most specific skill wins; if tied, newest version wins; if still tied, escalate to human)

#### 3. Token Budget Audit

The pipeline operates within token budget constraints (API cost management). Vaswani:

- Calculates average tokens per TU across all pipeline stages
- Identifies stages that consume disproportionate tokens
- Compares actual spend against the configured hourly/daily budget
- Recommends model routing adjustments (e.g., shift more TUs to FlashX if budget is tight)
- Projects budget consumption for the coming week based on current trends

#### 4. Identity Drift Detection

While Koehn checks SOUL.md file hashes, Vaswani performs behavioral identity drift detection:

- Analyzes agent output patterns over time for style changes
- Compares current agent behavior against the behavioral profile defined in SOUL.md
- Checks for "personality bleed" where one agent starts mimicking another's style
- Uses embedding similarity between recent outputs and the agent's SOUL.md description

#### 5. A/B Analysis

When A/B tests are running (comparing model variants), Vaswani:

- Computes statistical significance of quality differences
- Calculates cost-per-quality-point for each variant
- Recommends promotion or retirement of model variants
- Ensures A/B test sample sizes are sufficient before drawing conclusions (minimum 50 TUs per variant)

### Output

```yaml
audit:
  type: weekly_optimization
  timestamp: "2026-05-29T04:00:00Z"
  checks:
    skill_pruning:
      status: pass
      candidates_for_archival: ["register-detection-v1"]
      recommendation: "Archive after human review"
    collision_detection:
      status: warn
      collision_pairs:
        - ["glossary-enforcement", "tone-preservation"]
      frequency: 12
      recommendation: "Add priority rule: glossary-enforcement > tone-preservation"
    token_budget:
      status: pass
      avg_tokens_per_tu: 2340
      daily_spend_pct: 67
      projection: "On track for 78% weekly budget utilization"
    identity_drift:
      status: pass
      drift_scores:
        translator: 0.02
        wittgenstein: 0.04
        quine: 0.01
        frege: 0.03
    ab_analysis:
      status: pass
      active_tests: 1
      details: "Flash vs FlashX: FlashX +3.2% quality, +8% cost. N=87, p=0.03"
      recommendation: "Promote FlashX for domain:legal"
```

---

## Audit Results: Pass / Warn / Block

Every audit check produces one of three statuses:

### Pass

The check completed successfully with no issues. No action required. The pipeline continues normally.

### Warn

A potential issue was detected but it is not severe enough to halt the pipeline. Warnings:

- Generate a Kanban card in the `review` column
- Are logged to `logs/audits/` with full details
- Accumulate -- 3+ active warnings from the same scientist trigger an automatic escalation to human review
- Are visible in the monitoring dashboard

### Block

A critical issue was detected that requires immediate attention. Blocks:

- **Pause the dispatcher** -- no new TUs are processed until the block is resolved
- Generate a `CRITICAL` Kanban card assigned to the relevant agent owner
- Send a notification (configured per deployment: Slack, email, or webhook)
- Require human intervention to clear (run `make audit-clear BLOCK_ID=xxx` after resolution)

Block-worthy conditions include:
- SOUL.md hash mismatch (identity corruption)
- Memory store corruption (unparseable glossary or corpus)
- Significant identity drift (drift score > 0.15)
- Token budget exceeded (>100% of daily budget)
- 2+ consecutive TUs blocked by the same skill collision

---

## Feedback Loop

Scientist findings feed back into the pipeline through several mechanisms:

### Kanban Integration

- Audit results create cards in dedicated Kanban columns: `audit-pass`, `audit-warn`, `audit-block`
- Warning cards include a recommended action and the responsible profile
- Block cards include a remediation procedure

### Skill Adjustment

- Koehn regression findings can trigger skill parameter updates
- Vaswani pruning recommendations, once approved, move skills to `archived` status
- Cho stale pattern findings inform which skills need refreshing

### Model Routing

- Vaswani's A/B analysis results feed into the `ab-model-routing` skill's configuration
- Token budget findings may adjust the Flash/FlashX routing ratio

### SOUL Remediation

- If SOUL.md corruption is detected, the pipeline triggers an automatic rollback:
  1. `git checkout HEAD~1 -- profiles/{agent}/SOUL.md`
  2. Re-verify hash
  3. Reinstall profile: `make profile-install AGENT={agent}`
  4. Resume pipeline

---

## Cron Job Configuration

Scientist audits are configured in the project's crontab or CI/CD scheduler:

```cron
# Cho: Memory & coherence audit - Sunday 02:00 UTC
0 2 * * 0  cd /path/to/interpretation-ai-cell && make audit-cho >> logs/audits/cho-$(date +\%Y\%m\%d).log 2>&1

# Vaswani: Optimization audit - Sunday 04:00 UTC (after Cho)
0 4 * * 0  cd /path/to/interpretation-ai-cell && make audit-vaswani >> logs/audits/vaswani-$(date +\%Y\%m\%d).log 2>&1

# Koehn: Per-merge audit (triggered by git hook, not cron)
# See .git/hooks/post-merge for the trigger script
```

### Make Targets

```bash
# Run individual scientist audits
make audit-koehn TU_ID=TU-2026-05-29-0042   # Run Koehn on a specific TU
make audit-cho                                 # Run Cho's full weekly audit
make audit-vaswani                             # Run Vaswani's full weekly audit

# Run all scientists (respects ordering: Cho → Vaswani)
make audit-all

# Clear a block after remediation
make audit-clear BLOCK_ID=BLK-20260529-001

# View audit history
make audit-log                                 # Last 20 audit results
make audit-log SCIENTIST=koehn LIMIT=50        # Filtered view
```

### Git Hook (Koehn)

The post-merge hook for Koehn is installed during bootstrap:

```bash
#!/bin/bash
# .git/hooks/post-merge
# Trigger Koehn audit on merged TUs

MERGED_TUS=$(git diff --name-only HEAD~1 HEAD -- corpus/ | grep '\.yml$')

for tu_file in $MERGED_TUS; do
  tu_id=$(basename "$tu_file" .yml)
  make audit-koehn TU_ID="$tu_id" &
done

wait
```

---

## Monitoring Audit Health

Key metrics to watch:

| Metric | Healthy Range | Alert Threshold |
|--------|--------------|-----------------|
| Koehn pass rate | > 90% | < 80% over 50 TUs |
| Cho weekly status | pass | Any block |
| Vaswani weekly status | pass or warn | Any block |
| Active warnings | 0-5 | > 10 |
| Active blocks | 0 | > 0 |
| Time to clear block | < 4 hours | > 24 hours |
| Drift score (any agent) | < 0.05 | > 0.10 |

Audit logs are stored in `logs/audits/` and retained for 90 days. Older logs are compressed and moved to `logs/audits/archive/`.
