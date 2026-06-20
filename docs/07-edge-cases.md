# Edge Cases and Safety Guardrails

This document covers the failure modes, safety mechanisms, and guardrails built into the Interpretation AI Cell pipeline. Every system that runs autonomously needs clear boundaries and recovery procedures. This page documents what can go wrong and how the system handles it.

---

## Infinite Loop Prevention

The multi-agent review pipeline (Translator -> Wittgenstein -> Quine -> Frege) could theoretically loop indefinitely if agents keep requesting revisions from each other.

### Max Rounds

Each TU has a configurable maximum number of review rounds:

```yaml
# shared/config.yml
pipeline:
  max_rounds: 5          # Maximum review cycles per TU
  warn_at_round: 3       # Log a warning when this round is reached
```

If a TU reaches `max_rounds` without consensus, it is:
1. Marked as `needs-human-review` on the Kanban board
2. The best available translation (highest confidence from any round) is preserved
3. A detailed log of all rounds and agent feedback is attached to the TU

### Wall-Clock Timeout

Independent of round count, each TU has a wall-clock timeout:

```yaml
pipeline:
  tu_timeout_seconds: 300   # 5 minutes per TU
```

If a TU exceeds this timeout, processing is halted and the TU is escalated. This protects against edge cases where a single round takes unexpectedly long (e.g., due to API latency or context window saturation).

### Escalation Ladder

When a TU cannot be resolved automatically, it follows an escalation ladder:

1. **Round 3 warning**: Logged, agents are instructed to converge
2. **Round 5 / timeout**: TU moves to `needs-human-review`
3. **3+ TUs stuck in same session**: Dispatcher pauses and alerts human operator
4. **5+ TUs stuck in 24 hours**: Pipeline enters degraded mode (see Context Window Saturation)

---

## Skill Collision

Skill collisions occur when two or more skills produce contradictory guidance for the same TU. For example, `glossary-enforcement` might require "Datenschutz" while `tone-preservation` suggests "Privatsphare" for a warmer tone.

### Detection

Vaswani's `collision-detection` audit (weekly) identifies collision patterns retrospectively. During runtime, the dispatcher detects immediate collisions when:

- Two skills attempt to modify the same token/phrase in the translation
- Two skills produce contradictory metadata flags (e.g., one says "formal," another says "informal")

### Resolution Protocol

Collisions are resolved using a strict priority chain:

**Specificity > Version > Human**

1. **Specificity**: The more specific skill wins. A skill scoped to `domain: ["legal"]` takes precedence over one scoped to `domain: ["*"]` when processing a legal TU.

2. **Version**: If specificity is equal, the newer version wins. A skill at `version: 3` takes precedence over `version: 2`.

3. **Human**: If both specificity and version are equal, the collision is logged and the TU is flagged for human review. The dispatcher uses the higher-priority skill's output as the default but marks it as provisional.

### Permanent Resolution

Vaswani may recommend adding an explicit priority rule to resolve recurring collisions:

```yaml
# shared/collision-rules.yml
rules:
  - skills: ["glossary-enforcement", "tone-preservation"]
    winner: glossary-enforcement
    rationale: "Glossary terms are contractual obligations"
```

---

## Context Window Saturation

The pipeline operates within the context window limits of the underlying models (Claude Opus 4, Claude Sonnet 4). When accumulated context (system prompt + skills + TU history + reflections) approaches the model's limit, the system enters progressive degradation.

### Stage 1: Trim Reflections (75% capacity)

- Agent reflection history is truncated to the most recent 5 entries
- Older reflections are summarized into a single paragraph
- No impact on translation quality expected

### Stage 2: Compress Skills (85% capacity)

- Low-priority skills (priority < 60) are temporarily unloaded
- Remaining skills have their instruction text compressed (removing examples, keeping rules)
- Minor quality impact possible; logged for Koehn review

### Stage 3: Reduce Context (92% capacity)

- TU history is limited to the current TU only (no sibling context)
- Glossary is filtered to only domain-relevant entries
- A/B test metadata is stripped
- Moderate quality impact; all TUs processed in this stage are flagged for review

### Stage 4: Emergency Mode (97% capacity)

- Only the Translator agent processes the TU (no review pipeline)
- Only `glossary-enforcement` and `segmentation` skills remain active
- Translation is marked as `emergency-mode` and requires human review
- An alert is sent to the operator

### Recovery

When context usage drops below 70% (e.g., after processing a batch of short TUs), the system automatically restores to Stage 1 / normal operation. Recovery is gradual -- skills are reloaded in priority order.

---

## Identity Drift Detection

Identity drift occurs when an agent's behavior gradually diverges from its SOUL.md specification. This can happen due to model updates, accumulated context effects, or subtle prompt injection through source text.

### SOUL.md Hash Verification

Every audit cycle, Koehn computes SHA-256 hashes of all SOUL.md files:

```bash
sha256sum profiles/*/SOUL.md > /tmp/current-hashes.txt
diff shared/soul-hashes.yml /tmp/current-hashes.txt
```

A hash mismatch triggers an immediate `CRITICAL` alert and pipeline pause.

### Behavioral Drift Detection

Vaswani performs behavioral drift analysis weekly:

- Computes embedding similarity between agent outputs and SOUL.md descriptions
- Tracks style metrics (sentence length distribution, vocabulary diversity, formality markers)
- Compares current metrics against a 30-day baseline
- Drift score: 0.0 (identical to baseline) to 1.0 (completely divergent)

| Drift Score | Severity | Action |
|-------------|----------|--------|
| 0.00 - 0.05 | Normal | No action |
| 0.05 - 0.10 | Minor | Logged, monitored |
| 0.10 - 0.15 | Moderate | Warning, human review scheduled |
| 0.15+ | Critical | Pipeline paused, SOUL rollback initiated |

---

## SOUL Rollback

When identity drift or corruption is detected, a SOUL rollback restores the agent to its last known-good state.

### Procedure

```bash
# 1. Identify the last known-good commit for the affected profile
git log --oneline profiles/{agent}/SOUL.md

# 2. Restore SOUL.md from that commit
git checkout {commit_hash} -- profiles/{agent}/SOUL.md

# 3. Verify the restored hash
sha256sum profiles/{agent}/SOUL.md
# Compare against shared/soul-hashes.yml

# 4. Reinstall the profile
make profile-install AGENT={agent}

# 5. Update the hash registry
make soul-hash-update

# 6. Resume pipeline
make pipeline-resume
```

### Automated Rollback

If Koehn detects a SOUL.md hash mismatch, the system can perform an automated rollback:

1. Checks out the previous version from git
2. Verifies the restored hash matches the registry
3. Reinstalls the profile
4. Resumes the pipeline
5. Creates a Kanban card documenting the incident

Automated rollback only goes back one commit. If the previous commit is also corrupted, the pipeline stays paused and requires human intervention.

---

## API Resilience

The pipeline depends on Anthropic API calls. Network issues, rate limits, and service outages must be handled gracefully.

### Circuit Breaker Pattern

The API client implements a circuit breaker:

```
CLOSED (normal) → OPEN (after 3 consecutive failures) → HALF-OPEN (after 30s cooldown)
```

- **Closed**: API calls proceed normally. Failures are counted.
- **Open**: All API calls are immediately rejected (fail fast). TUs are queued. After a 30-second cooldown, the circuit transitions to half-open.
- **Half-open**: A single test call is made. If it succeeds, the circuit closes. If it fails, the circuit opens again with a longer cooldown (exponential backoff, max 5 minutes).

### Fallback Chain

When the primary model is unavailable, the system falls through a model chain:

```
Claude Opus 4 (primary, highest quality)
    ↓ failure
Claude Sonnet 4 (fallback, fast and cost-efficient)
    ↓ failure
Queue (TU is queued for retry when service recovers)
```

Each fallback is logged. If translations are completed on a fallback model, they are tagged with the model used so Koehn can assess quality differences.

### Rate Limiting

The dispatcher enforces rate limits to stay within API quotas:

```yaml
# shared/config.yml
api:
  requests_per_minute: 60
  tokens_per_minute: 100000
  burst_allowance: 10       # Extra requests allowed in short bursts
```

When rate limits are approached (>80% utilization), the dispatcher throttles by inserting delays between TU submissions.

---

## Data Privacy

### Sensitivity Flags

Source text can be tagged with sensitivity levels:

```yaml
# In TU metadata
sensitivity: public        # public | internal | confidential | restricted
```

- **public**: Normal processing, full logging
- **internal**: Normal processing, logs redacted after 30 days
- **confidential**: No A/B testing, no reflection logging, minimal metadata
- **restricted**: Ephemeral mode (see below), human review required

### Ephemeral Mode

For restricted content, ephemeral mode ensures no data persists:

- Translation is processed in memory only
- No TU is written to the corpus
- No agent reflections are recorded
- Logs contain only the TU ID and processing status (no content)
- The translation is delivered directly to the requester and then purged

### Git-Crypt for Sensitive Corpus

When the corpus contains sensitive material (e.g., client contracts, medical records), `git-crypt` is used:

```bash
# Initialize git-crypt (one-time setup)
git-crypt init

# Add sensitive paths to .gitattributes
echo "corpus/confidential/** filter=git-crypt diff=git-crypt" >> .gitattributes

# Add authorized keys
git-crypt add-gpg-user {GPG_KEY_ID}
```

Encrypted files are transparent to authorized users but appear as binary blobs to others.

---

## Consecutive Block Detection

If the pipeline produces 2 or more consecutive blocked TUs (i.e., TUs that receive a `block` status from any scientist or review agent), the dispatcher automatically pauses:

1. No new TUs are submitted for processing
2. A `CRITICAL` alert is generated
3. The blocked TUs are queued for human review
4. The dispatcher logs the block pattern for Vaswani's analysis

This prevents the system from wasting API tokens on a systemic issue (e.g., a corrupted glossary causing every TU to fail glossary enforcement).

### Resuming After Consecutive Blocks

```bash
# Review blocked TUs
make list-blocked

# After fixing the root cause, clear blocks and resume
make clear-blocks
make pipeline-resume
```

---

## Token Budget Exhaustion

The pipeline operates within hourly and daily token budgets to manage API costs.

```yaml
# shared/config.yml
budget:
  hourly_tokens: 500000
  daily_tokens: 10000000
  alert_at_pct: 80
  pause_at_pct: 100
```

### When Budget Is Exhausted

1. The dispatcher stops submitting new TUs
2. Currently-processing TUs are allowed to complete
3. New TUs are queued with a timestamp
4. When the next budget period begins (top of the hour or midnight UTC), queued TUs are processed in FIFO order
5. A notification is sent: "Token budget exhausted. {N} TUs queued for next period."

### Budget Monitoring

Vaswani's weekly audit includes token budget analysis:
- Average tokens per TU by pipeline stage
- Budget utilization trends
- Recommendations for model routing adjustments to reduce cost

---

## Glossary Conflicts

Glossary conflicts occur when:
- Two glossary entries could match the same source phrase
- A glossary entry conflicts with an agent's skill output
- A new glossary entry contradicts an existing one

### Frege as Governance Authority

Frege is the ultimate authority on glossary decisions:

- All glossary additions require Frege's approval (via Kanban workflow)
- When a conflict is detected, Frege is invoked to arbitrate
- Frege's decision is recorded in the glossary entry's metadata:

```yaml
# shared/glossary.yml entry
- source: "data protection"
  target: "Datenschutz"
  domain: legal
  approved_by: frege
  conflict_resolution: "Preferred over 'Schutz personenbezogener Daten' for brevity in non-regulatory contexts"
  approved_date: 2026-05-28
```

### Conflict Resolution Process

1. Conflict is detected (by Translator during processing or Cho during audit)
2. A Kanban card is created in the `glossary-review` column
3. Frege evaluates both options with context
4. Frege renders a decision with rationale
5. The glossary is updated, the losing entry is marked `deprecated`
6. Legal/medical domain conflicts always require human sign-off in addition to Frege's decision
