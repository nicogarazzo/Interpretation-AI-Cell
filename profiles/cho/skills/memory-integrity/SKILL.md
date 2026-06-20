---
name: memory-integrity
description: Audit MEMORY.md and state.db integrity across all agent profiles
trigger: weekly scheduled audit (Sunday 03:00 UTC)
---

# Memory Integrity Audit

Cho verifies that every agent's persistent memory (MEMORY.md and state.db) remains structurally sound, internally consistent, and free of data rot.

## Scope

Scan all profiles under `profiles/*/`:
- `MEMORY.md` — human-readable memory log
- `state.db` — structured state database (SQLite or JSON)

## Integrity Checks

### 1. Orphaned Entries

An entry is orphaned when it references a translation ID that no longer exists in the output corpus.

- Query every `translation_id` referenced in MEMORY.md and state.db.
- Cross-reference against `translations/` directory and the translation index.
- Flag entries where the referenced translation has been deleted or moved.

### 2. Stale Patterns

A pattern is stale when it has not been reinforced or referenced in the last 200 translations.

- For each learned pattern in MEMORY.md (lines matching `## Pattern:` or `- learned:`), check the last reinforcement timestamp.
- If the pattern has not been accessed or updated in 200+ translations, mark as `STALE`.
- Stale patterns are candidates for archival, not automatic deletion.

### 3. Timestamp Consistency

- Within each agent's MEMORY.md, timestamps must be **monotonically increasing** (each entry's timestamp >= the previous entry's timestamp).
- Detect any out-of-order entries and flag with the specific line numbers.
- Check for timestamps in the future (beyond current UTC time).
- Verify timestamp format consistency (ISO 8601).

### 4. Entry Count Trends

- Track the total entry count per agent per week.
- Flag anomalies: sudden spikes (>50% increase in one week) or drops (any decrease without a corresponding pruning log entry).
- Maintain a trailing trend in `memory-audit-log.md`.

## Integrity Rules

| Rule | Condition | Severity |
|---|---|---|
| Every memory entry must reference an existing translation | `translation_id` resolves to a file in `translations/` | ERROR |
| No duplicate entries | Same `translation_id` + `agent` + `observation` combo must be unique | WARNING |
| Timestamps must be monotonically increasing per agent | `entry[n].timestamp <= entry[n+1].timestamp` | ERROR |
| No future timestamps | `entry.timestamp <= now()` | ERROR |
| Entry count must not decrease without pruning log | `count(week N) < count(week N-1)` without `pruning-log` entry | WARNING |

## Output

Produce `memory-audit-report.md` with:
- Per-agent summary table (entry count, orphaned count, stale count, timestamp errors)
- Detailed findings per agent (specific entries and line numbers)
- Overall verdict: `HEALTHY`, `DEGRADED`, or `CORRUPT`
