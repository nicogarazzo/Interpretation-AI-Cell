---
name: regression-detection
description: Detect quality regression in translation outputs by tracking key metrics over time
trigger: when new metrics are available after a translation batch
---

# Regression Detection

Koehn monitors translation quality across batches and raises alerts when metrics degrade beyond acceptable thresholds.

## Tracked Metrics

| Metric | Source | Window |
|---|---|---|
| **Approval rate** | Consensus verdicts (approved / total) | Trailing 50 translations |
| **Error category distribution** | Tagged error types from philosopher feedback | Trailing 50 translations |
| **Consensus round count** | Number of rounds before verdict per translation | Trailing 50 translations |
| **Per-philosopher agreement rate** | How often each philosopher agrees with the final verdict | Trailing 50 translations |

## Regression Thresholds

A regression is flagged when any of the following conditions are met:

1. **Approval rate drop > 10%.** If the trailing-50 approval rate falls more than 10 percentage points below the previous trailing-50 window (e.g., 88% to 77%).
2. **New error category appearing.** An error category that was absent in the previous 100 translations appears in the current batch. This may indicate a new failure mode introduced by a skill or memory change.
3. **Consensus rounds increasing > 20%.** The mean number of consensus rounds in the current trailing-50 exceeds the previous trailing-50 by more than 20%. This suggests growing disagreement among philosophers.
4. **Per-philosopher agreement collapse.** Any single philosopher's agreement rate with the final verdict drops below 60%, indicating potential misalignment with the group.

## Correlation Analysis

When a regression is detected:

1. **Identify the time range** of the regression (first batch where metric crossed threshold).
2. **Run `git log --since` and `git blame`** on all SKILL.md files modified within that time range.
3. **Cross-reference** the changed skills with the error categories that increased.
4. **Produce a correlation hypothesis:** e.g., "Approval rate dropped 12% after Wittgenstein's register-check skill was updated to be stricter on 2026-05-25."

## Severity Levels

| Severity | Condition | Action |
|---|---|---|
| `INFO` | Metric moved but stayed within threshold | Log only |
| `WARNING` | One threshold breached | Log + add to next audit report |
| `CRITICAL` | Two or more thresholds breached simultaneously | Log + flag for immediate human review + pause auto-merge |

## Output

Append a regression entry to `regression-log.md` with: timestamp, metric snapshots (before/after), severity, correlated skill changes (if any), and recommended action.
