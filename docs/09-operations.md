# Operations Guide

This document covers the day-to-day operation of the Interpretation AI Cell pipeline: bootstrapping, running translations, monitoring, troubleshooting, and maintenance.

---

## Bootstrap

### Prerequisites

- macOS or Linux
- Python 3.10+
- Git with git-crypt (optional, for sensitive corpus)
- An Anthropic API key
- Make (GNU Make)

### Initial Setup

```bash
# 1. Clone the repository
git clone <repo-url> interpretation-ai-cell
cd interpretation-ai-cell

# 2. Run bootstrap (installs dependencies, creates directories, installs profiles)
make bootstrap
```

`make bootstrap` performs the following steps:

1. Creates a Python virtual environment in `.venv/`
2. Installs Python dependencies from `requirements.txt`
3. Creates the directory structure:
   ```
   profiles/          # Agent SOUL.md files and skills
   shared/            # Glossary, config, collision rules
   corpus/            # Translation memory
   logs/              # Runtime and audit logs
     audits/
     skills/
     pipeline/
   ```
4. Installs all agent profiles (copies SOUL.md and skills into the Hermes runtime)
5. Generates initial SOUL.md hashes in `shared/soul-hashes.yml`
6. Validates the glossary
7. Prints a status summary

### Setting API Keys

API keys are stored in environment variables, never in config files:

```bash
# Add to your shell profile (~/.zshrc or ~/.bashrc)
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

Verify API connectivity:

```bash
make api-check
```

This sends a minimal test request to each configured model and reports status.

### Profile Installation

Profiles are installed during bootstrap, but can be reinstalled individually:

```bash
# Reinstall a specific profile
make profile-install AGENT=translator
make profile-install AGENT=wittgenstein
make profile-install AGENT=frege

# Reinstall all profiles
make profiles-install-all

# Verify profile installation
make profile-verify
```

---

## Starting the Pipeline

### Gateway Start

The gateway is the entry point for translation requests:

```bash
# Start the gateway (foreground)
make gateway-start

# Start the gateway (background, with PID file)
make gateway-start-bg

# Check gateway status
make gateway-status

# Stop the gateway
make gateway-stop
```

The gateway listens for translation submissions and feeds them into the dispatcher.

### Submitting Translation Tasks

#### Via CLI

```bash
# Translate a single file
make translate FILE=input/document.txt

# Translate with domain tag
make translate FILE=input/contract.txt DOMAIN=legal

# Translate with sensitivity flag
make translate FILE=input/patient-report.txt DOMAIN=medical SENSITIVITY=restricted

# Translate a directory of files
make translate-batch DIR=input/batch-2026-05-29/

# Translate inline text
make translate-text TEXT="The data protection officer must approve all changes."
```

#### Via File Drop

Place files in the `input/` directory. The gateway watches this directory and automatically submits new files:

```bash
cp my-document.txt input/
# The gateway picks it up within 5 seconds
```

#### Via API (if configured)

```bash
curl -X POST http://localhost:8080/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The quarterly report shows significant growth.",
    "domain": "business",
    "sensitivity": "internal"
  }'
```

### Pipeline Flow

Once submitted, a translation task flows through:

1. **Segmentation** (Translator): Source text is split into TUs
2. **Translation** (Translator): Each TU is translated EN->DE
3. **Pragmatic review** (Wittgenstein): Context, idioms, register checked
4. **Ambiguity review** (Quine): Ambiguity scored, indeterminacy flagged
5. **Semantic review** (Frege): Sinn/Bedeutung, tone, formality verified
6. **Merge**: Approved TUs are merged to corpus
7. **Audit** (Koehn): Post-merge quality check

---

## Monitoring

### Log Locations

| Log | Path | Contents |
|-----|------|----------|
| Pipeline | `logs/pipeline/` | Per-TU processing logs |
| Audits | `logs/audits/` | Scientist audit results |
| Skills | `logs/skills/` | Skill invocation and override logs |
| Gateway | `logs/gateway.log` | HTTP requests, submissions |
| Dispatcher | `logs/dispatcher.log` | TU routing, queue status |
| API | `logs/api.log` | Anthropic API calls, latency, errors |

### Key Metrics to Watch

| Metric | Where to Find | Healthy Range |
|--------|--------------|---------------|
| TUs processed/hour | `logs/dispatcher.log` | 20-100 (depends on complexity) |
| Average TU latency | `logs/pipeline/` | < 30 seconds |
| Glossary override rate | `logs/skills/` | < 15% |
| API error rate | `logs/api.log` | < 1% |
| Token budget utilization | `logs/dispatcher.log` | < 80% |
| Active warnings | Kanban `audit-warn` column | < 5 |
| Active blocks | Kanban `audit-block` column | 0 |
| Context window usage | `logs/pipeline/` | < 75% average |

### Quick Status Check

```bash
# Overall pipeline status
make status

# Output example:
# Gateway:     RUNNING (PID 12345)
# Dispatcher:  RUNNING
# Queue:       3 TUs pending
# Budget:      67% daily utilization
# Warnings:    2 active
# Blocks:      0
# Last audit:  2026-05-28T02:00Z (Cho: pass)
```

### Dashboard

If a monitoring dashboard is configured (optional):

```bash
make dashboard
# Opens http://localhost:3000 with real-time metrics
```

The dashboard shows:
- TU throughput over time
- Model routing distribution (Opus 4 vs Sonnet 4)
- Quality metrics trends
- Token budget burn-down
- Active alerts

---

## Troubleshooting

### Common Issues

#### "API connection refused"

```
Symptom: Translations fail with connection errors
Cause:   Anthropic API unreachable or API key invalid
Fix:
  1. make api-check                    # Verify connectivity
  2. echo $ANTHROPIC_API_KEY          # Verify key is set
  3. Check https://status.anthropic.com # Check service status
  4. Review logs/api.log              # Check for rate limiting
```

#### "TU stuck in processing"

```
Symptom: A TU has been in "processing" state for > 5 minutes
Cause:   Infinite loop between agents, or API timeout
Fix:
  1. make tu-status TU_ID=TU-xxx     # Check TU state
  2. make tu-cancel TU_ID=TU-xxx     # Cancel and requeue
  3. Check logs/pipeline/ for the TU  # Identify which agent is stuck
```

#### "Glossary parse error"

```
Symptom: Pipeline fails to start with YAML parse error
Cause:   Malformed glossary.yml (usually bad indentation)
Fix:
  1. python -c "import yaml; yaml.safe_load(open('shared/glossary.yml'))"
  2. Fix the YAML syntax error
  3. make glossary-validate            # Verify fix
  4. make pipeline-resume
```

#### "SOUL hash mismatch"

```
Symptom: Pipeline paused with CRITICAL alert
Cause:   A SOUL.md file was modified outside the governance process
Fix:
  1. make soul-verify                  # Identify which profile(s)
  2. git diff profiles/*/SOUL.md       # Review changes
  3. If accidental: make soul-rollback AGENT=xxx
  4. If intentional: make soul-hash-update
  5. make pipeline-resume
```

#### "Token budget exhausted"

```
Symptom: New TUs are queued, not processed
Cause:   Hourly or daily token budget reached 100%
Fix:
  1. make budget-status                # Check current utilization
  2. Wait for next budget period (top of hour or midnight UTC)
  3. Or: make budget-override          # Temporarily increase budget (requires confirmation)
```

#### "Context window saturation"

```
Symptom: Translation quality drops, emergency mode warnings in logs
Cause:   Accumulated context exceeds model limits
Fix:
  1. Check logs/pipeline/ for "stage" markers (Stage 1-4)
  2. If Stage 3+: reduce batch size, process shorter documents
  3. make reflections-prune            # Archive old reflections
  4. make context-reset                # Reset context accumulation
```

---

## Rollback Procedures

### Translation Rollback

Revert a specific translation to a previous version:

```bash
# View translation history for a TU
make tu-history TU_ID=TU-2026-05-29-0042

# Rollback to a specific version
make tu-rollback TU_ID=TU-2026-05-29-0042 VERSION=2

# Rollback all TUs from a batch
make batch-rollback BATCH_ID=BATCH-20260529
```

### SOUL Rollback

Restore an agent's SOUL.md to a previous version:

```bash
# Rollback a specific agent
make soul-rollback AGENT=translator

# Rollback with a specific commit
make soul-rollback AGENT=translator COMMIT=abc123

# Verify and resume
make soul-verify
make pipeline-resume
```

### Full Rollback

In case of systemic failure, roll back the entire system:

```bash
# WARNING: This resets all profiles, glossary, and config to a previous state
make full-rollback COMMIT=abc123

# This performs:
# 1. git checkout {commit} -- profiles/ shared/
# 2. make profiles-install-all
# 3. make soul-hash-update
# 4. make glossary-validate
# 5. make pipeline-resume
```

Full rollback does NOT touch the corpus (translated TUs). Corpus rollback is a separate, manual operation.

---

## A/B Testing

### How A/B Tests Work

The `ab-model-routing` skill assigns TUs to model variants based on the configuration in `shared/ab-config.yml`:

```yaml
# shared/ab-config.yml
active_test:
  name: "opus-vs-sonnet-legal"
  started: 2026-05-20
  variants:
    - name: "primary"
      model: "claude-opus-4-20250514"
      weight: 50
    - name: "lightweight"
      model: "claude-sonnet-4-20250514"
      weight: 50
  domain_filter: "legal"          # Only apply to legal domain TUs
  min_sample_size: 50             # Minimum TUs per variant before analysis
  auto_promote: false             # Require human approval to promote
```

### Interpreting Results

Vaswani's weekly audit includes A/B analysis. Key metrics:

- **Quality score**: Average quality rating across all TUs per variant
- **Cost per TU**: Average token cost per variant
- **Override rate**: How often the glossary had to override the model's output
- **Statistical significance**: p-value for quality difference (need p < 0.05)
- **Sample size**: Must meet minimum before drawing conclusions

### Promoting a Model

When results are conclusive:

```bash
# View current A/B results
make ab-results

# Promote a variant (updates default model routing)
make ab-promote VARIANT=flashx

# End the test without promoting
make ab-end
```

---

## Profile Updates

### Editing SOUL.md

When an agent's core identity or behavior needs to change:

1. Edit `profiles/{agent}/SOUL.md`
2. Commit with a descriptive message: `git commit -m "soul: update translator emphasis on formal register"`
3. Reinstall the profile: `make profile-install AGENT=translator`
4. Update SOUL hashes: `make soul-hash-update`
5. Monitor the next 20+ TUs for behavioral changes

### Editing Skills

1. Edit the skill file: `profiles/{agent}/skills/{skill-name}.skill.md`
2. Increment the `version` field in the YAML frontmatter
3. Commit: `git commit -m "skill: update glossary-enforcement v3 - add compound word handling"`
4. Reinstall: `make profile-install AGENT=translator`
5. No hash update needed (SOUL hashes only cover SOUL.md, not skills)

### Archiving a Skill

1. Change `status: active` to `status: archived` in the skill's frontmatter
2. Commit and reinstall
3. The skill remains in the repository but is not loaded by Hermes

---

## Adding New Agents

To add a new agent profile to the pipeline:

### 1. Create the Profile Directory

```bash
mkdir -p profiles/new-agent/skills
```

### 2. Write the SOUL.md

Create `profiles/new-agent/SOUL.md` following the established pattern:

```markdown
---
name: new-agent
role: [description of the agent's role]
model: claude-sonnet-4-20250514   # or claude-opus-4-20250514
---

# New Agent

## Identity
[Who this agent is and what it does]

## Responsibilities
[Specific duties in the pipeline]

## Constraints
[What this agent must NOT do]

## Interaction Protocol
[How this agent communicates with others via Kanban]
```

### 3. Create Initial Skills

Write skill files in `profiles/new-agent/skills/`.

### 4. Register the Agent

Add the agent to the pipeline configuration:

```yaml
# shared/config.yml
agents:
  - name: new-agent
    position: after-frege      # Where in the pipeline this agent sits
    model: claude-sonnet-4-20250514
    skills_dir: profiles/new-agent/skills/
```

### 5. Install and Verify

```bash
make profile-install AGENT=new-agent
make soul-hash-update
make profile-verify
```

---

## Backup and Recovery

### What to Back Up

| Path | Priority | Frequency | Method |
|------|----------|-----------|--------|
| `profiles/` | Critical | Every change (git) | Git commit |
| `shared/` | Critical | Every change (git) | Git commit |
| `corpus/` | High | Daily | Git commit + offsite |
| `logs/` | Medium | Weekly | Archive to cold storage |
| `.env` / API keys | Critical | On change | Secure vault |

### Git as Primary Backup

The repository itself is the primary backup mechanism:

```bash
# Verify git status
git status

# Push to remote (assuming remote is configured)
git push origin main
```

### Offsite Backup

For additional protection, especially for the corpus:

```bash
# Manual backup
make backup
# Creates a timestamped archive: backups/interpretation-ai-cell-20260529.tar.gz

# Automated daily backup (add to crontab)
0 3 * * * cd /path/to/interpretation-ai-cell && make backup >> logs/backup.log 2>&1
```

### Recovery

```bash
# Restore from backup
make restore BACKUP=backups/interpretation-ai-cell-20260529.tar.gz

# This performs:
# 1. Extracts backup to a temporary directory
# 2. Validates integrity (checksums)
# 3. Restores profiles/, shared/, corpus/
# 4. Reinstalls all profiles
# 5. Validates glossary and SOUL hashes
```

---

## Scaling

### Dispatcher Settings

The dispatcher controls how many TUs are processed simultaneously:

```yaml
# shared/config.yml
dispatcher:
  concurrent_workers: 3          # Number of TUs processed in parallel
  queue_max_size: 100            # Maximum queued TUs
  batch_size: 10                 # TUs per batch submission
  poll_interval_seconds: 5       # How often to check for new input
```

### Adjusting Concurrent Workers

- **1 worker**: Safest, sequential processing. Use for debugging.
- **3 workers** (default): Good balance of throughput and resource usage.
- **5-10 workers**: Higher throughput, requires higher API rate limits.
- **10+ workers**: May hit API rate limits; requires `burst_allowance` adjustment.

```bash
# Change workers without restart
make dispatcher-set WORKERS=5

# Or edit shared/config.yml and restart
make gateway-restart
```

### Rate Limit Adjustments

When scaling up workers, also adjust rate limits:

```yaml
api:
  requests_per_minute: 120       # Increase for more workers
  tokens_per_minute: 200000      # Increase budget accordingly
  burst_allowance: 20
```

### Performance Tips

1. **Batch similar documents**: Grouping documents by domain allows more efficient glossary loading (only relevant domain entries are injected).
2. **Pre-segment long documents**: Very long documents can be pre-segmented before submission to avoid timeout issues.
3. **Schedule heavy batches off-peak**: Run large batch jobs during low-usage hours to avoid budget conflicts with interactive translations.
4. **Monitor context window usage**: If context saturation events are frequent, consider reducing `concurrent_workers` or pruning old reflections.
5. **Archive completed corpus entries**: Move old corpus entries to `corpus/archive/` to keep the active corpus lean.

### Makefile Quick Reference

```bash
make bootstrap              # Initial setup
make gateway-start          # Start the pipeline
make gateway-stop           # Stop the pipeline
make gateway-restart        # Restart
make status                 # Overall status
make translate FILE=x       # Translate a file
make translate-batch DIR=x  # Translate a directory
make audit-all              # Run all scientist audits
make audit-cho              # Run Cho audit
make audit-vaswani          # Run Vaswani audit
make audit-koehn TU_ID=x    # Run Koehn on a TU
make glossary-validate      # Validate glossary
make profile-verify         # Verify all profiles
make soul-verify            # Check SOUL.md hashes
make soul-rollback AGENT=x  # Rollback a SOUL.md
make backup                 # Create backup
make ab-results             # View A/B test results
make budget-status          # Check token budget
make api-check              # Verify API connectivity
```
