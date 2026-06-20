---
name: diff-audit
description: Audit git diffs of translation files and SOUL state changes after each merge
trigger: when a new translation batch is merged to the main branch
---

# Diff Audit

Koehn reviews every merge to the main branch, parsing the git diff to ensure no unintended changes slip through the translation pipeline.

## Protocol

1. **Retrieve the merge diff.** Run `git diff <merge-base>..HEAD` scoped to tracked paths.
2. **Parse diff hunks.** For each hunk extract:
   - File path (from the `diff --git a/... b/...` header)
   - Hunk range (from the `@@ -start,count +start,count @@` header)
   - Added lines (prefixed with `+`)
   - Removed lines (prefixed with `-`)
   - Context lines (no prefix)
3. **Categorize every changed file** into one of:
   | Category | Path pattern | Examples |
   |---|---|---|
   | Translation content | `translations/**`, `output/**` | New or revised EN-DE pairs |
   | Skill update | `profiles/*/skills/**/SKILL.md` | Modified trigger, protocol, or criteria |
   | Memory update | `profiles/*/MEMORY.md`, `state.db` | New entries, pruned entries |
   | Configuration | `cron/**`, `*.yml`, `config.*` | Schedule or pipeline config changes |
   | Unknown | anything else | Requires manual review |

4. **Summarize per category:** file count, total lines added, total lines removed.

## Red Flags

Flag the merge for human review if any of the following are detected:

- **Large deletions without explanation.** More than 50 lines removed from a single file with no corresponding commit message justification.
- **Skill downgrades.** A SKILL.md loses sections (e.g., a protocol step is deleted or a threshold is relaxed) without an accompanying rationale in the commit body.
- **Memory truncation.** MEMORY.md entries are removed or `state.db` rows are deleted outside of an explicit pruning operation triggered by a scientist skill.
- **Unauthorized profile edits.** A philosopher profile is modified by a commit not attributed to a scientist or the orchestrator.
- **Binary files.** Any binary file added or modified in the repository.

## Diff Reading Guide

| Symbol | Meaning |
|---|---|
| `+` line | Line was **added** in this change |
| `-` line | Line was **removed** in this change |
| ` ` line (space) | Unchanged **context** line surrounding the change |
| `@@ -L,N +L,N @@` | Hunk header: old file starts at line L (N lines), new file starts at line L (N lines) |
| `diff --git a/path b/path` | File header: identifies which file changed |
| `--- a/path` / `+++ b/path` | Old and new file paths (may differ on renames) |
| `\ No newline at end of file` | File does not end with a newline character |

## Output

Produce a structured audit report as a Markdown table appended to `audit-log.md` with columns: timestamp, merge SHA, category breakdown, red flags (if any), and verdict (`CLEAN` or `REVIEW_REQUIRED`).
