# 03 - Kanban Workflow

The Interpretation AI Cell uses Hermes Agent's built-in Kanban system to orchestrate all work -- from source document ingestion through translation, philosopher review, and scientist audit. This page documents the complete task lifecycle.

---

## Task States

Every task on the Kanban board moves through a defined set of columns:

```
todo --> ready --> in_progress --> review --> done
                                    |
                                    v
                                 blocked
```

| State | Description | Who moves tasks here |
|---|---|---|
| `todo` | Newly created tasks. May have unresolved dependencies. | Humans (manual submission) or Translator (task decomposition) |
| `ready` | All dependencies satisfied. Eligible for dispatcher pickup. | Kanban engine (automatic when `parents` are all `done`) |
| `in_progress` | An agent has claimed the task and is actively working. | Hermes dispatcher (automatic on pickup) |
| `review` | Work is complete but awaiting evaluation (philosopher consensus). | Agent (automatic on completion of translation) |
| `done` | Task is finished. Translation approved and committed. | Consensus engine (automatic on 2-of-3 approval) or human |
| `blocked` | Task cannot proceed. Escalated for human intervention. | Consensus engine (after max rounds exhausted) or safety rules |
| `automated` | Tasks created by cron jobs (scientist audits). | Cron scheduler (automatic) |

### State Transition Rules

- `todo` -> `ready`: automatic when all entries in `parents[]` have reached `done`.
- `ready` -> `in_progress`: automatic when the dispatcher assigns the task to an agent.
- `in_progress` -> `review`: automatic when the agent produces output. For translations, this triggers the philosopher consensus protocol.
- `review` -> `done`: automatic when the consensus engine returns `approve`.
- `review` -> `in_progress`: automatic when the consensus engine returns `revise` (revision loop, up to `max_rounds`).
- `review` -> `blocked`: automatic when `max_rounds` is exhausted or when a safety rule triggers (e.g., 2 consecutive blocks).
- `blocked` -> `todo`: manual. A human reviews the blocked task, provides guidance or a manual translation, and resubmits.

---

## Task Decomposition Graph

A source document goes through several levels of decomposition before individual translation units reach the pipeline. Here is the complete graph:

```
Level 0: Document Ingestion
+------------------------------------------+
|  Human submits source document to        |
|  Kanban board as a single task           |
|  Type: document                          |
|  Assignee: translator                    |
|  Column: todo                            |
+------------------+-----------------------+
                   |
                   v
Level 1: Segmentation (Translator's segmentation skill)
+------------------------------------------+
|  Translator segments document into TUs   |
|  Each TU becomes a child task            |
|  Parent: document task                   |
+------------------+-----------------------+
                   |
     +-------------+-------------+--- ... ---+
     |             |             |            |
     v             v             v            v
Level 2: Translation Tasks (one per TU)
+----------+  +----------+  +----------+  +----------+
| TU-001   |  | TU-002   |  | TU-003   |  | TU-N     |
| Type:    |  | Type:    |  | Type:    |  | Type:    |
| translate|  | translate|  | translate|  | translate|
| Assignee:|  | Assignee:|  | Assignee:|  | Assignee:|
| translator| | translator| | translator| | translator|
+----+-----+  +----+-----+  +----+-----+  +----+-----+
     |              |              |              |
     v              v              v              v
Level 3: Review Tasks (one per TU, created after translation)
+----------+  +----------+  +----------+  +----------+
| Review   |  | Review   |  | Review   |  | Review   |
| TU-001   |  | TU-002   |  | TU-003   |  | TU-N     |
| Type:    |  | Type:    |  | Type:    |  | Type:    |
| review   |  | review   |  | review   |  | review   |
| Assignee:|  | Assignee:|  | Assignee:|  | Assignee:|
| wittgen- |  | wittgen- |  | wittgen- |  | wittgen- |
| stein,   |  | stein,   |  | stein,   |  | stein,   |
| quine,   |  | quine,   |  | quine,   |  | quine,   |
| frege    |  | frege    |  | frege    |  | frege    |
| parents: |  | parents: |  | parents: |  | parents: |
| [TU-001] |  | [TU-002] |  | [TU-003] |  | [TU-N]  |
+----+-----+  +----+-----+  +----+-----+  +----+-----+
     |              |              |              |
     +------+-------+------+------+-------+------+
            |              |              |
            v              v              v
Level 4: Audit Tasks (batch-level, created after merge)
+----------------+  +------------------+  +-------------------+
| Koehn          |  | Cho              |  | Vaswani           |
| post-merge     |  | weekly-memory    |  | weekly-           |
| audit          |  | audit            |  | optimization      |
| Type: audit    |  | Type: audit      |  | Type: audit       |
| Trigger:       |  | Trigger:         |  | Trigger:          |
| post-merge     |  | cron 03:00 Sun   |  | cron 04:00 Sun    |
| parents:       |  |                  |  | (after Cho)       |
| [all reviews]  |  |                  |  |                   |
+----------------+  +------------------+  +-------------------+
```

### Task Types

| Type | Created By | Claimed By | Description |
|---|---|---|---|
| `document` | Human | Translator | A full source document for translation |
| `translate` | Translator (segmentation) | Translator | A single Translation Unit to translate |
| `review` | Translator (after producing draft) | All 3 philosophers | Philosopher consensus review of a draft translation |
| `audit` | Cron scheduler | Koehn, Cho, or Vaswani | Asynchronous quality/integrity audit |
| `glossary-proposal` | Any agent | Frege | Proposal to add a term to the canonical glossary |
| `human-review` | Consensus engine (escalation) | Human | Blocked translation requiring human intervention |

---

## Kanban Dispatcher Configuration

The Hermes gateway acts as the central dispatcher. Its behavior is configured per-profile in `config.yaml`:

```yaml
kanban:
  dispatch_in_gateway: true
  dispatch_interval_seconds: 5   # How often to poll for new tasks
```

### Dispatcher Loop

For each registered profile, the gateway repeats this cycle:

1. **Poll**: Query the Kanban board for tasks in `ready` column that match the profile's type.
2. **Claim**: Move the highest-priority matching task to `in_progress` and set the profile as assignee.
3. **Invoke**: Start the agent with the task payload (source text, context, metadata).
4. **Complete**: When the agent returns output, move the task to the appropriate next column.
5. **Wait**: Sleep for `dispatch_interval_seconds` before polling again.

### Polling Intervals by Layer

| Layer | Interval | Rationale |
|---|---|---|
| Translator | 5 seconds | Must pick up TUs promptly but not hammer the board |
| Philosophers | 3 seconds | Hot path -- faster polling reduces consensus latency |
| Scientists | 30 seconds | Async work -- no urgency, reduce unnecessary API calls |

---

## Task Assignment

Tasks are assigned to profiles based on **labels** that the Kanban engine matches against profile capabilities:

| Task Label | Claimed By | Notes |
|---|---|---|
| `translation` | `translator` | One translator processes one TU at a time |
| `philosophy-review` | `wittgenstein`, `quine`, `frege` | All three claim the same task and work in parallel |
| `koehn-audit` | `koehn` | Post-merge diff audit |
| `cho-audit` | `cho` | Weekly memory integrity check |
| `vaswani-optimization` | `vaswani` | Weekly token/skill optimization |
| `human-review-required` | (none -- awaits human) | Escalated tasks that no agent claims |
| `glossary-proposals` | `frege` | Glossary additions requiring Frege's approval |

### Multi-Agent Assignment (Philosophers)

When a `philosophy-review` task enters `ready`, all three philosopher profiles claim it simultaneously. The consensus engine collects their verdicts and applies the voting rules (see [04 - Consensus Protocol](04-consensus-protocol.md)). The task does not move to `done` until the consensus engine has a result.

---

## Dependency Management

Tasks can declare dependencies on other tasks via the `parents` field:

```yaml
task:
  id: review-tu-001
  type: review
  parents:
    - translate-tu-001     # This task cannot start until translate-tu-001 is done
```

### Dependency Rules

1. A task with `parents` starts in `todo` and automatically moves to `ready` when all parents reach `done`.
2. If a parent moves to `blocked`, the child remains in `todo` indefinitely until the parent is resolved.
3. Circular dependencies are rejected at task creation time.
4. A document-level completion task can depend on all its TU review tasks, enabling a "gate" that only opens when the entire document passes consensus.

### Common Dependency Chains

```
translate-tu-001  -->  review-tu-001
translate-tu-002  -->  review-tu-002
translate-tu-003  -->  review-tu-003
                            |
                            v
                   [all reviews done]
                            |
                            v
                     merge-to-main
                            |
                            v
                   koehn-post-merge-audit
```

---

## Parallel Execution

Translation Units within a batch run in **parallel**. The dispatcher treats each TU as an independent task:

```
Document: "Privacy Policy v2.0"
  |
  +-- TU-001 (heading)     --> Translator --> Philosophers  --> done
  +-- TU-002 (paragraph)   --> Translator --> Philosophers  --> done    (parallel)
  +-- TU-003 (list item)   --> Translator --> Philosophers  --> done    (parallel)
  +-- TU-004 (list item)   --> Translator --> Philosophers  --> done    (parallel)
  +-- TU-005 (table)       --> Translator --> Philosophers  --> done    (parallel)
  +-- TU-006 (code block)  --> [pass-through, no translation needed]
```

### Parallelism Constraints

| Constraint | Source | Value |
|---|---|---|
| Max concurrent API requests | `shared/token-budget.yml` | 5 |
| Max requests per minute | `shared/token-budget.yml` | 30 |
| Max tokens per hour (all agents) | `shared/token-budget.yml` | 500,000 |

With 5 concurrent requests, up to 5 TUs can be in the translation or review stage simultaneously. The dispatcher automatically throttles when limits are approached.

### Philosopher Parallelism

Within a single review task, all three philosophers evaluate the draft **simultaneously**. They do not wait for each other. The consensus engine collects verdicts as they arrive and applies the voting rules once it has responses from all three (or after the per-agent timeout of 30 seconds).

---

## How the Kanban Board Visualizes Pipeline Progress

A snapshot of the board during active translation of a 6-TU document might look like:

```
| todo         | ready        | in_progress    | review         | done           | blocked      |
|--------------|--------------|----------------|----------------|----------------|--------------|
|              |              |                |                | TU-001 (done)  |              |
|              |              | TU-004         | TU-002         | TU-003 (done)  |              |
|              |              | (translating)  | (3 philosophers|                |              |
|              |              |                |  evaluating)   |                |              |
|              | TU-005       |                |                |                |              |
|              | (ready,      |                |                |                |              |
|              |  waiting for |                |                |                |              |
|              |  dispatcher) |                |                |                |              |
| TU-006       |              |                |                |                |              |
| (waiting on  |              |                |                |                |              |
|  TU-005 dep) |              |                |                |                |              |
```

### Board Labels

Tasks carry labels that provide at-a-glance status:

| Label | Meaning |
|---|---|
| `round-1`, `round-2`, `round-3` | Which consensus revision round the task is on |
| `human-review-required` | Escalated -- needs human attention |
| `koehn-audit` / `cho-audit` / `vaswani-optimization` | Scientist audit tasks |
| `model:flash` / `model:flashx` | Which A/B cohort the translation belongs to |
| `glossary-proposals` | Pending glossary addition |

### Task Priority

Within a column, tasks are ordered by:

1. **Blocked dependencies**: tasks that other tasks are waiting on get priority.
2. **Revision round**: tasks on round 2 or 3 get priority over round 1 (finish what you started).
3. **Creation time**: FIFO within the same priority tier.
