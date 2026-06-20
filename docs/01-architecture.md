# 01 - System Architecture

## Hermes Primitives Mapping

The Interpretation AI Cell maps its domain concepts directly onto Hermes Agent primitives:

| Our Concept | Hermes Primitive | Description |
|---|---|---|
| Agent identity | **Profile** | Each of the 7 agents is a Hermes profile with its own directory, config, and state. |
| Agent personality | **SOUL.md** | The philosophical anchor and behavioral contract for each agent. Injected into every prompt. |
| Learned procedures | **Skills** (`skills/*/SKILL.md`) | Versioned, trigger-based procedures. Each skill has YAML frontmatter (name, description, trigger) and markdown body. |
| Accumulated experience | **Memory** (`MEMORY.md` + `state.db`) | Episodic and semantic memory. `MEMORY.md` is human-readable; `state.db` is SQLite for fast retrieval. |
| Task orchestration | **Kanban** | Built-in task board with columns, assignment, dependencies, and dispatcher. |
| Quality gate | **Consensus Engine** | Multi-agent voting with configurable quorum, weights, and tie-breaking. |
| Task routing | **Dispatcher** | Hermes gateway process that polls the Kanban board and assigns tasks to idle agents. |
| Scheduled jobs | **Cron** (`cron/*.yml`) | Profile-level cron definitions that trigger skills on schedule or on git events. |
| Configuration | **config.yaml** | Per-profile configuration: model, provider, Kanban settings, auxiliary models. |

---

## Profile Registry

All 7 profiles, their layer assignments, model configurations, and dispatch cadence:

| Profile | Layer | Model | Provider | Dispatch Interval | Tier |
|---|---|---|---|---|---|
| `translator` | Core | `claude-opus-4-20250514` (A/B with `claude-sonnet-4-20250514`) | anthropic | 5s | Opus |
| `wittgenstein` | Philosopher | `claude-sonnet-4-20250514` | anthropic | 3s | Sonnet |
| `quine` | Philosopher | `claude-sonnet-4-20250514` | anthropic | 3s | Sonnet |
| `frege` | Philosopher | `claude-sonnet-4-20250514` | anthropic | 3s | Sonnet |
| `koehn` | Scientist | `claude-sonnet-4-20250514` | anthropic | 30s | Sonnet |
| `cho` | Scientist | `claude-sonnet-4-20250514` | anthropic | 30s | Sonnet |
| `vaswani` | Scientist | `claude-sonnet-4-20250514` | anthropic | 30s | Sonnet |

**Dispatch interval** is how frequently the Hermes gateway checks the Kanban board for tasks assignable to each profile. Philosophers poll aggressively (3s) because they are in the hot path. Scientists poll lazily (30s) because they handle async audits.

---

## Directory Structure

```
Interpretation AI Cell/
|
+-- profiles/
|   |
|   +-- translator/
|   |   +-- SOUL.md                          # Agent identity: core directives, output format, constraints
|   |   +-- config.yaml                      # Model: claude-opus-4-20250514, provider: anthropic, kanban settings
|   |   +-- skills/
|   |   |   +-- glossary-enforcement/
|   |   |   |   +-- SKILL.md                 # Canonical EN-DE glossary, enforcement rules, update protocol
|   |   |   +-- ab-model-routing/
|   |   |   |   +-- SKILL.md                 # Deterministic hash routing to Flash vs FlashX
|   |   |   +-- segmentation/
|   |   |       +-- SKILL.md                 # Document -> Translation Unit splitting rules
|   |   +-- memories/                        # [gitignored] Per-machine episodic memory
|   |   +-- sessions/                        # [gitignored] Per-machine session state
|   |   +-- state.db                         # [gitignored] SQLite memory store
|   |   +-- .env                             # [gitignored] ANTHROPIC_API_KEY
|   |
|   +-- wittgenstein/
|   |   +-- SOUL.md                          # Philosophical anchor: meaning is use
|   |   +-- config.yaml
|   |   +-- skills/
|   |   |   +-- idiom-localization/SKILL.md
|   |   |   +-- pragmatic-context/SKILL.md
|   |   |   +-- register-detection/SKILL.md
|   |
|   +-- quine/
|   |   +-- SOUL.md                          # Philosophical anchor: indeterminacy of translation
|   |   +-- config.yaml
|   |   +-- skills/
|   |       +-- ambiguity-scoring/SKILL.md
|   |
|   +-- frege/
|   |   +-- SOUL.md                          # Philosophical anchor: Sinn und Bedeutung
|   |   +-- config.yaml
|   |
|   +-- koehn/
|   |   +-- SOUL.md                          # Git drift auditor
|   |   +-- config.yaml
|   |   +-- skills/
|   |   |   +-- diff-audit/SKILL.md
|   |   |   +-- regression-detection/SKILL.md
|   |   +-- cron/
|   |       +-- post-merge-audit.yml         # Triggers on every merge to main
|   |
|   +-- cho/
|   |   +-- SOUL.md                          # Memory state analyst
|   |   +-- config.yaml
|   |   +-- skills/
|   |   |   +-- memory-integrity/SKILL.md
|   |   |   +-- cross-agent-coherence/SKILL.md
|   |   +-- cron/
|   |       +-- weekly-memory-audit.yml      # Sundays at 03:00 UTC
|   |
|   +-- vaswani/
|       +-- SOUL.md                          # Attention & skill optimizer
|       +-- config.yaml
|       +-- skills/
|       |   +-- context-optimization/SKILL.md
|       |   +-- skill-pruning/SKILL.md
|       +-- cron/
|           +-- weekly-optimization.yml      # Sundays at 04:00 UTC (after Cho)
|
+-- shared/
|   +-- glossary.yml                         # Canonical EN-DE glossary (version-controlled)
|   +-- consensus-config.yml                 # Philosopher voting rules, weights, escalation
|   +-- token-budget.yml                     # Per-agent token budgets, cost tracking, adjustment rules
|
+-- corpus/
|   +-- source/                              # English source documents
|   +-- translations/                        # Approved German translations
|   +-- evaluations/                         # Philosopher evaluation metadata
|
+-- docs/                                    # This wiki
|
+-- Makefile                                 # bootstrap, install-profiles, test-profiles, clean
+-- README.md
+-- .gitignore
+-- .gitattributes
```

---

## What Goes in Git vs. What Stays Per-Machine

The `.gitignore` draws a clear boundary between version-controlled intelligence and per-machine runtime state:

| In Git (version-controlled) | Per-machine (gitignored) |
|---|---|
| `SOUL.md` -- agent identity | `memories/` -- episodic memory store |
| `skills/*/SKILL.md` -- learned procedures | `sessions/` -- active session state |
| `config.yaml` -- agent configuration | `state.db` -- SQLite memory database |
| `shared/*.yml` -- glossary, consensus config, token budgets | `.env` -- API keys |
| `corpus/` -- source texts, translations, evaluations | `logs/` -- runtime logs |
| `cron/*.yml` -- scheduled job definitions | |
| `Makefile`, `README.md`, docs | |

### Rationale

- **SOUL, skills, and config** define *what* an agent is. They are the agent's source code and must be tracked.
- **Memory and state** are *runtime artifacts*. They accumulate on the machine where the agent runs. If you need to move an agent to a new machine, you export its memory; you don't commit it to the shared repo.
- **Corpus** is the translation output -- the product of the pipeline. It is version-controlled because translations are the deliverable.
- **API keys** are secrets and must never be committed.

### Git LFS for state.db

The `.gitattributes` file configures Git LFS for `*.db` files:

```
*.db filter=lfs diff=lfs merge=lfs -text
```

This is a safety net: if a `state.db` file is ever accidentally committed (overriding `.gitignore`), it will be stored via LFS rather than bloating the repository. SQLite databases are binary files and compress poorly with standard git.

Additionally, `.gitattributes` enforces consistent line endings (`eol=lf`) for all text-based configuration files (`.md`, `.yml`, `.yaml`, `.json`).

---

## config.yaml Structure

Each profile has a `config.yaml` that configures its model, provider, and Kanban behavior. The structure varies slightly between agent types.

### Translator config.yaml

```yaml
model:
  default: claude-opus-4-20250514   # Highest quality for client deliverables
  provider: anthropic

auxiliary:
  kanban_decomposer: claude-sonnet-4-20250514  # Sonnet for task decomposition (cost-efficient)

kanban:
  dispatch_in_gateway: true       # Let the Hermes gateway dispatch tasks
  dispatch_interval_seconds: 5    # Poll every 5 seconds

agent:
  personalities: {}               # No sub-personalities for translator
```

The Translator is the only profile using Opus 4 -- it produces client-facing translations where quality is non-negotiable. The `auxiliary` section uses Sonnet 4 for Kanban task decomposition (breaking documents into TU tasks). The A/B routing to Sonnet 4 for test runs is handled by the `ab-model-routing` skill, not by config.

### Philosopher config.yaml (Wittgenstein, Quine, Frege)

```yaml
model:
  default: claude-sonnet-4-20250514
  provider: anthropic

kanban:
  dispatch_in_gateway: true
  dispatch_interval_seconds: 3    # Faster polling -- hot path
```

Philosophers use Sonnet 4 for fast, cost-efficient review. They poll aggressively (3s) because they are in the hot path.

### Scientist config.yaml (Koehn, Cho, Vaswani)

```yaml
model:
  default: claude-sonnet-4-20250514
  provider: anthropic

kanban:
  dispatch_in_gateway: true
  dispatch_interval_seconds: 30   # Lazy polling -- async work
```

Scientists also use Sonnet 4 but poll lazily (30s). Their async nature means sub-second responsiveness is unnecessary.

---

## How Anthropic Is Configured as Provider

Anthropic provides the Claude model family via its API. In Hermes Agent, this is configured via the `provider: anthropic` field in each profile's `config.yaml`. The API key is stored in a per-machine `.env` file:

```bash
# .hermes/.env
ANTHROPIC_API_KEY=your-anthropic-api-key-here
```

All profiles share the same API key. The `.env` file is gitignored.

### Model pricing (as of 2026-05-30)

| Model | Input | Output | Use Case |
|---|---|---|---|
| `claude-opus-4-20250514` | $15/1M tokens | $75/1M tokens | Translator (primary) |
| `claude-sonnet-4-20250514` | $3/1M tokens | $15/1M tokens | Philosophers, scientists, A/B lightweight |

The cost tiering is deliberate: Opus 4 is reserved for the Translator (client-facing output where quality is critical), while all review and audit agents use the more cost-efficient Sonnet 4. See `shared/token-budget.yml` for detailed per-agent budgets and cost estimates.

---

## Dispatcher Configuration and Kanban Settings

The Hermes gateway process acts as the central dispatcher. It is started with:

```bash
hermes gateway start
```

The gateway performs the following loop for each registered profile:

1. Poll the Kanban board at the profile's `dispatch_interval_seconds`.
2. Find tasks in the `todo` column that are assignable to the profile (based on task labels and profile type).
3. Move matched tasks to `in_progress` and invoke the profile's agent.
4. When the agent completes, move the task to `review` or `done` depending on the workflow.

### Kanban board structure

The Kanban board for the cell is named `interpretation-cell` and has the following columns:

| Column | Purpose |
|---|---|
| `todo` | New tasks waiting to be claimed |
| `ready` | Tasks with all dependencies satisfied, eligible for dispatch |
| `in_progress` | Tasks currently being processed by an agent |
| `review` | Tasks awaiting philosopher consensus or human review |
| `done` | Completed tasks |
| `blocked` | Tasks that cannot proceed (e.g., max revision rounds exceeded) |
| `automated` | Tasks created by cron jobs (scientist audits) |

### Task routing rules

Tasks are routed to profiles based on labels:

- Tasks labeled `translation` are claimed by the `translator` profile.
- Tasks labeled `philosophy-review` are claimed by all three philosopher profiles in parallel.
- Tasks labeled `koehn-audit` are claimed by the `koehn` profile.
- Tasks labeled `cho-audit` are claimed by the `cho` profile.
- Tasks labeled `vaswani-optimization` are claimed by the `vaswani` profile.

### Rate limiting

Global rate limits are defined in `shared/token-budget.yml`:

```yaml
global:
  max_tokens_per_hour: 500000
  max_requests_per_minute: 30
  max_concurrent_requests: 5
```

These limits apply across all agents combined and serve as a safety buffer against runaway loops or API abuse. Individual per-agent budgets are also defined in the same file (see the token budget section for details).
