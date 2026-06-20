---
name: context-optimization
description: Optimize context window usage and token economy across all agents
trigger: weekly scheduled audit (Sunday 04:00 UTC)
---

# Context Optimization

Vaswani monitors how each agent uses its context window and ensures the translation pipeline operates within sustainable token budgets.

## Token Usage Analysis

For each agent, measure:

| Metric | Source | Unit |
|---|---|---|
| **Prompt tokens** | Input to the agent per translation | tokens |
| **Completion tokens** | Agent output per translation | tokens |
| **Context fill ratio** | (system prompt + memory + skills + input) / max context | percentage |
| **Memory retrieval tokens** | Tokens spent on MEMORY.md retrieval per call | tokens |
| **Skill injection tokens** | Tokens spent on SKILL.md content injected per call | tokens |

Track these as trailing-50 averages and week-over-week trends.

## Waste Identification

Flag the following as token waste:

1. **Redundant memory retrieval.** The same memory entry retrieved in >80% of calls without contributing to the verdict (never cited in feedback).
2. **Unused skill sections.** Skill sections that are injected but never referenced in agent output.
3. **Verbose feedback.** Agent responses that exceed 2x the median length for the same verdict type.
4. **Duplicate context.** Information present in both MEMORY.md retrieval and SKILL.md injection.

## Budget Recommendations

Based on usage patterns, recommend per-agent token budgets:

- **Baseline:** median usage over trailing 100 translations + 20% headroom.
- **Cap:** 2x baseline. If an agent consistently hits cap, investigate root cause.
- **Rebalancing:** if one agent is under budget by >30%, consider redistributing to agents near their cap.

## Progressive Degradation Protocol

When an agent's context approaches **80% of its budget**, apply degradation steps in order:

| Step | Threshold | Action |
|---|---|---|
| 1 | 80% | Drop `approved_spans` from memory retrieval (keep only rejections and learned patterns) |
| 2 | 85% | Compress feedback history: keep only the last 3 feedback entries instead of 10 |
| 3 | 90% | Reduce memory retrieval to top-5 most relevant entries (down from top-10) |
| 4 | 95% | Flag `limited_context` in the agent's state, alerting the orchestrator to reduce batch size |

Each degradation step must be logged with timestamp, agent, threshold crossed, and action taken.

## A/B Test Analysis

When sufficient data exists (100+ translations per cohort), compare Flash vs FlashX performance:

1. **Quality metrics:** approval rate, error distribution, consensus rounds.
2. **Efficiency metrics:** tokens per translation, latency, cost.
3. **Compute quality-adjusted cost:** `cost_per_approved_translation = total_cost / approved_count`.
4. **Statistical significance:** require p < 0.05 (two-proportion z-test for approval rate, Welch's t-test for continuous metrics).
5. **Recommendation:** if FlashX is quality-equivalent but cheaper, recommend migration. If Flash is higher quality, quantify the quality premium per 1000 translations.

## Output

Produce `context-optimization-report.md` with:
- Per-agent token usage table (trailing-50 averages)
- Waste flags with estimated token savings
- Budget recommendations
- Active degradation steps (if any)
- A/B test results (if sufficient data)

## Identity Drift Check

As part of each weekly audit, verify SOUL.md integrity:
1. Read `shared/drift_baseline.json` for stored SHA-256 hashes
2. Compute current SHA-256 of each `profiles/<agent>/SOUL.md`
3. Compare. Any mismatch = CRITICAL alert in the output JSON
4. If `shared/drift_baseline.json` does not exist, create it from current SOUL.md files (bootstrap mode)
