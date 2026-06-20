# 10 — Translation Run Logging & Traceability

## Overview

Every translation job processed through the Kanban pipeline produces a complete audit trail in `corpus/runs/`. Each run captures the input, every agent's output, the consensus verdict, and the final approved translation — providing full traceability from source to approved output.

## Run Directory Structure

```
corpus/runs/
├── .template/                      # Template for new runs (do not modify directly)
└── 2026-05-30_001/                 # Run ID: date + sequence number
    ├── manifest.yml                # Run metadata, status, agent activity log
    ├── source/
    │   └── segments.json           # Source text split into translation units
    ├── agents/
    │   ├── translator/
    │   │   └── output.json         # Translation output per segment
    │   ├── wittgenstein/
    │   │   └── review.json         # Pragmatic/idiom review
    │   ├── quine/
    │   │   └── review.json         # Ambiguity audit
    │   ├── frege/
    │   │   └── review.json         # Sinn/Bedeutung + tone review
    │   ├── koehn/
    │   │   └── audit.json          # Git diff / regression audit (async)
    │   ├── cho/
    │   │   └── audit.json          # Memory integrity audit (async)
    │   └── vaswani/
    │       └── audit.json          # Optimization audit (async)
    ├── consensus/
    │   └── verdict.json            # Merged philosopher verdicts + weighted scores
    └── final/
        └── approved.json           # Final approved translations
```

## Creating a New Run

```bash
make new-run
```

This copies `.template/` to a new timestamped directory, auto-fills the `run_id` and `created_at` fields in `manifest.yml`.

Output:
```
Created run: 2026-05-30_001
  Directory: /path/to/corpus/runs/2026-05-30_001
  Next: edit manifest.yml and source/segments.json
```

## Run Lifecycle

```
1. CREATE          make new-run
2. POPULATE        Edit source/segments.json with EN source text
3. TRANSLATE       Translator agent processes segments → agents/translator/output.json
4. REVIEW          3 philosophers review in parallel → agents/{w,q,f}/review.json
5. CONSENSUS       Voting engine merges verdicts → consensus/verdict.json
6. REVISION        If revise: translator re-translates, loop to step 4 (max 3 rounds)
7. APPROVE         Consensus passes → final/approved.json
8. AUDIT           Scientists run async post-merge → agents/{k,c,v}/audit.json
9. ARCHIVE         manifest.yml status → "approved" or "failed"
```

## manifest.yml — Run Metadata

The manifest tracks the entire run state in one file:

- **Run identity**: `run_id`, `created_at`, `status`
- **Source metadata**: client, campaign, content type, funnel stage
- **Segment counts**: total, translated, approved, blocked
- **Agent activity**: timestamps, models used, verdicts, token counts per agent
- **Audit results**: scientist findings summary
- **Human review**: escalation tracking if consensus fails

Status values: `pending` → `in_progress` → `review` → `approved` | `failed`

## Segment Format

Each segment in `source/segments.json` represents one translation unit:

```json
{
  "id": "seg_001",
  "type": "post_copy",
  "text": "Discover how leading manufacturers are adopting more modern, wipe-based solutions...",
  "context": {
    "asset_name": "Awareness Ad 1 - Rags vs Wipes",
    "funnel_stage": "awareness",
    "content_type": "linkedin_ad",
    "character_limit": 300,
    "notes": "LinkedIn post body text"
  }
}
```

Segment types: `post_copy`, `headline`, `image_copy`, `cta`, `body_text`, `bullet_list`, `table_cell`

## Agent Output Files

### Translator (output.json)

Each translation includes:
- Source and target text
- Confidence score
- Flags (ambiguities, decisions made)
- Glossary terms applied
- Client patterns matched (from client skill)
- Token usage

### Philosophers (review.json)

Same structure for all three, per their SOUL.md output format:
- Verdict: approve | revise | block
- Issues with severity, category, spans, suggestions
- Skills invoked
- Approved spans (what's good)

### Consensus (verdict.json)

Merged from all three philosopher reviews:
- Weighted votes per segment
- Dominant issue category (determines which philosopher's weight applies)
- Merged issue list (deduplicated across agents)
- Revision instructions (if revise/block)
- Escalation flag

### Final (approved.json)

The pipeline's deliverable:
- Final approved text per segment
- Revision history (if multiple rounds)
- Quality signals from all three philosophers
- Glossary and client pattern compliance

## Querying Runs

Find all runs for a specific client:
```bash
grep -rl "client: <client-id>" corpus/runs/*/manifest.yml
```

Find failed runs:
```bash
grep -rl "status: \"failed\"" corpus/runs/*/manifest.yml
```

Find runs that were escalated to human:
```bash
grep -rl "escalated_to_human: true" corpus/runs/*/manifest.yml
```

## Retention

- **Approved runs**: Keep indefinitely (training data for the pipeline)
- **Failed runs**: Keep for 90 days (debugging), then archive
- **Scientist audits**: Aggregated weekly by Vaswani's optimization skill

## Git Tracking

Translation runs ARE tracked in git (unlike agent runtime state):
- `corpus/runs/` is in the repo
- Each approved translation is a commit-worthy event
- Scientists (Koehn) audit the git diff of new translations
