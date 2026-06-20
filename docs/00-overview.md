# 00 - Project Overview

## Vision

The Interpretation AI Cell is a self-improving English-to-German translation engine where **agent intelligence is version-controlled**. Every agent in the pipeline has a defined identity, learned skills, and accumulated memory -- all stored as plain files in Git. When an agent learns something new (a better way to handle German compound nouns, a pattern for detecting false friends), that knowledge is committed alongside the translation output it produced. The result is a translation system whose quality trajectory is fully auditable, reproducible, and reversible.

The long-term goal is not a single perfect translator, but a *cell* of specialized agents that collectively exceed what any single model could achieve alone -- and that get measurably better with every batch of translations they process.

---

## Philosophy: SOUL, Skills, Memory

Every agent in the cell is built on three pillars borrowed from the Hermes Agent framework:

| Pillar | File | What It Captures |
|---|---|---|
| **SOUL** | `SOUL.md` | The agent's identity -- who it is, what it values, how it thinks. This is the constitution that never changes accidentally. |
| **Skills** | `skills/*/SKILL.md` | Procedures the agent has learned. Each skill has a trigger condition, a defined behavior, and versioned content. Skills are added, updated, archived, or pruned over time. |
| **Memory** | `MEMORY.md` + `state.db` | Experience the agent has accumulated from past translations. Patterns it noticed, mistakes it learned from, preferences it calibrated. Memory grows organically and is periodically audited for staleness and coherence. |

The key insight is that these three layers map directly to how human translators develop:

- **SOUL** = professional identity and values ("I am a German-language specialist who prioritizes natural fluency over literal accuracy")
- **Skills** = techniques learned through training ("When encountering English idioms, find the German functional equivalent rather than translating literally")
- **Memory** = experience from past work ("The last time I saw 'break the ice' in a business context, the client preferred 'das Eis brechen' over a more creative localization")

Because all three layers live in Git, the entire cognitive state of every agent is versioned. You can diff an agent's intelligence between any two points in time, roll back a bad skill update, or trace exactly why a particular translation was produced.

---

## Two-Layer Architecture

The pipeline is organized into two layers that operate at different speeds and serve different purposes:

### Layer 1: Philosophers (Hot Path -- Quality Gate)

Three philosopher agents form a **consensus panel** that reviews every translation in real time before it is committed. They are named after philosophers of language whose ideas directly inform their evaluation criteria:

- **Wittgenstein** -- evaluates pragmatic equivalence and idiomatic naturalness
- **Quine** -- detects ambiguity problems (inadvertent disambiguation, spurious ambiguity)
- **Frege** -- calibrates sense/reference preservation and tone/register accuracy

A translation must receive **2-of-3 weighted approval** from the philosopher panel to pass. If it fails, feedback is routed back to the Translator for revision, up to 3 rounds. This is the quality gate -- nothing reaches the corpus without philosophical consensus.

### Layer 2: Scientists (Async -- Audit & Optimization)

Three scientist agents run **asynchronously** after translations are committed. They are named after researchers in machine translation and deep learning:

- **Koehn** -- audits git diffs for skill regression and translation drift
- **Cho** -- verifies memory state integrity and cross-agent coherence
- **Vaswani** -- optimizes token budgets, prunes dead skills, detects identity drift

Scientists do not block the translation pipeline. They operate on a slower cadence (post-merge for Koehn, weekly cron for Cho and Vaswani) and produce audit reports that inform human operators and guide the cell's evolution.

### Why Two Layers?

| Concern | Philosophers (Hot) | Scientists (Async) |
|---|---|---|
| **Latency** | Must respond in <30 seconds per agent | Can take minutes |
| **Scope** | Single translation unit | Batch-level and cross-agent patterns |
| **Action** | Approve/revise/block a translation | Report findings, recommend changes |
| **Model** | Claude Sonnet 4 (fast, cost-efficient) | Claude Sonnet 4 (same model, async cadence) |
| **Frequency** | Every translation | Post-merge or weekly |

---

## Why Hermes Agent

[Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research) provides the runtime framework. It was chosen because its primitives map directly to the cell's needs:

- **Profiles** -- each of the 7 agents is a Hermes profile with its own config, SOUL, skills, and memory. Profiles are isolated but can communicate through Kanban.
- **Kanban** -- the built-in Kanban system orchestrates task flow. Translation tasks move through columns (`todo` -> `ready` -> `in_progress` -> `review` -> `done`), and agents claim tasks based on their profile type.
- **SOUL.md** -- Hermes natively supports identity files that are injected into every agent prompt. This is the foundation of the cell's philosophical consistency.
- **Skills** -- Hermes skills have frontmatter metadata (name, trigger conditions), versioned content, and can be dynamically loaded or archived.
- **Consensus Engine** -- Hermes supports multi-agent voting with configurable quorum, weights, and tie-breaking strategies. The philosopher panel uses this directly.
- **Profile Distributions** -- profiles can be packaged and installed from directories, making the cell portable and reproducible via `make bootstrap`.

---

## Why Anthropic (Claude)

The runtime uses [Anthropic](https://anthropic.com) as the LLM provider:

| Consideration | Decision |
|---|---|
| **Translation Quality** | Claude Opus 4 (`claude-opus-4-20250514`) is the highest-quality model available. For client-facing German translations without native speaker review, quality is non-negotiable. |
| **Cost Tiering** | Opus 4 ($15/$75 per 1M input/output tokens) is used only for the Translator. All other agents use Sonnet 4 ($3/$15 per 1M), keeping review and audit costs ~5x lower. |
| **A/B Testing** | The ab-model-routing skill supports optional A/B comparison between Opus 4 (primary) and Sonnet 4 (lightweight) for internal/test runs, enabling data-driven cost optimization. |
| **Reasoning** | Claude Sonnet 4 provides excellent reasoning for the philosopher and scientist layers -- review, audit, and optimization tasks. |

---

## The 7 Agents

| # | Profile | Layer | Model | One-Line Description |
|---|---|---|---|---|
| 1 | **translator** | Core | Claude Opus 4 (primary) / Sonnet 4 (A/B test) | Produces publication-quality EN-to-DE translations with glossary enforcement and structured JSON output. |
| 2 | **wittgenstein** | Philosopher | Claude Sonnet 4 | Evaluates pragmatic equivalence, idiomatic naturalness, and contextual appropriateness -- "meaning is use." |
| 3 | **quine** | Philosopher | Claude Sonnet 4 | Detects ambiguity problems: inadvertent disambiguation, spurious ambiguity, referential opacity shifts. |
| 4 | **frege** | Philosopher | Claude Sonnet 4 | Calibrates Sinn/Bedeutung preservation and tone/register accuracy -- also serves as glossary governance authority. |
| 5 | **koehn** | Scientist | Claude Sonnet 4 | Audits git diffs post-merge for skill regression, translation drift, and SOUL state inconsistencies. |
| 6 | **cho** | Scientist | Claude Sonnet 4 | Verifies memory integrity across all agents: orphaned entries, stale patterns, cross-agent contradictions. |
| 7 | **vaswani** | Scientist | Claude Sonnet 4 | Optimizes token economy, prunes dead skills, detects identity drift, and analyzes A/B model performance. |

---

## How Translation Flows Through the Pipeline

```
                                    +-----------+
                                    |  Source    |
                                    |  Document  |
                                    +-----+-----+
                                          |
                                          v
                                  +-------+--------+
                                  |  Segmentation  |
                                  |  (Translator   |
                                  |   skill)       |
                                  +-------+--------+
                                          |
                                    TU-001, TU-002, ...
                                          |
                                          v
                              +-----------+-----------+
                              |    Translator Agent   |
                              |  (Claude Opus 4 or    |
                              |   FlashX via A/B)     |
                              +-----------+-----------+
                                          |
                                   Draft translation
                                          |
                                          v
                    +---------------------+---------------------+
                    |                     |                     |
               +----+----+         +-----+-----+         +----+----+
               |Wittgen- |         |   Quine   |         |  Frege  |
               |stein    |         |           |         |         |
               +----+----+         +-----+-----+         +----+----+
                    |                     |                     |
                    +---------------------+---------------------+
                                          |
                                   2-of-3 vote?
                                    /         \
                                  YES          NO
                                  /             \
                                 v               v
                          +------+------+   +----+----+
                          | Git Commit  |   | Revision|
                          | to corpus/  |   | Loop    |
                          +------+------+   | (max 3) |
                                 |          +----+----+
                                 |               |
                                 |          Back to Translator
                                 v
                    +------------+------------+
                    |     Scientist Audit     |
                    |  (async, post-merge     |
                    |   or weekly cron)       |
                    +------------+------------+
                                 |
                          +------+------+------+
                          |      |      |      |
                       Koehn   Cho  Vaswani
                          |      |      |
                          v      v      v
                      Audit reports / optimization actions
                                 |
                                 v
                          Tagged Release
```

1. **Segmentation**: The Translator's segmentation skill breaks a source document into Translation Units (TUs) -- paragraphs, headings, list items, tables, code blocks.
2. **Translation**: Each TU is translated by the Translator agent, routed to either Claude Opus 4 (primary) or Sonnet 4 (lightweight, test only) via deterministic A/B hashing. The glossary-enforcement skill ensures terminological consistency.
3. **Philosopher Consensus**: All three philosophers evaluate the draft in parallel. Each produces a verdict (`approve`, `revise`, or `block`) with structured critiques. A 2-of-3 weighted vote determines the outcome.
4. **Revision Loop**: If the translation fails consensus, philosopher feedback is sent back to the Translator. Up to 3 revision rounds are allowed before escalation to a human reviewer.
5. **Git Commit**: Approved translations are committed to the `corpus/translations/` directory along with evaluation metadata in `corpus/evaluations/`.
6. **Scientist Audit**: After merges, Koehn audits the diff. Weekly, Cho checks memory integrity and Vaswani optimizes the token economy and skill health.
7. **Tagged Release**: When a full document completes the pipeline with all audits passing, it is tagged as a release.
