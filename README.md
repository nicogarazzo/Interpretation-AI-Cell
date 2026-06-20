# Interpretation AI Cell

Multi-agent English-to-German translation pipeline built on [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research).

## Architecture

7 Hermes Agent profiles orchestrated via Kanban:

| Profile | Layer | Role | Model |
|---|---|---|---|
| `translator` | Core | EN→DE translation | Claude Opus 4 (primary) / Sonnet 4 (A/B test) |
| `wittgenstein` | Philosopher | Pragmatics & idiom localization | Claude Sonnet 4 |
| `quine` | Philosopher | Ambiguity detection | Claude Sonnet 4 |
| `frege` | Philosopher | Sinn/Bedeutung & tone | Claude Sonnet 4 |
| `koehn` | Scientist | Git diff & skill regression audit | Claude Sonnet 4 |
| `cho` | Scientist | Memory state integrity | Claude Sonnet 4 |
| `vaswani` | Scientist | Context optimization & pruning | Claude Sonnet 4 |

## Pipeline Flow

```
Source Text → Translator → Philosopher Consensus (2-of-3) → Git Commit → Scientist Audit → Tagged Release
```

## Isolation

This project uses a **project-local `HERMES_HOME`** (`.hermes/` inside this repo) so it is completely isolated from your personal `~/.hermes`. The translation agents cannot see or affect your personal Hermes setup.

## Quick Start

```bash
# 1. Bootstrap: creates isolated .hermes/ and installs all profiles
make bootstrap

# 2. Set your API keys
echo "ANTHROPIC_API_KEY=sk-ant-..." > .hermes/.env
echo "GLM_API_KEY=your-z-ai-key" >> .hermes/.env

# 3. Choose environment
make env-prod   # Anthropic (client deliverables)
make env-test   # z.ai (free, iteration)

# 4. Start the Kanban gateway (isolated)
make start

# 4. Submit a translation task
HERMES_HOME=.hermes hermes kanban add --assignee translator --title "Translate: Hello world"
```

## Documentation

See [docs/](docs/) for the full wiki:

- [00 - Project Overview](docs/00-overview.md)
- [01 - System Architecture](docs/01-architecture.md)
- [02 - Agent Profiles](docs/02-agent-profiles.md)
- [03 - Kanban Workflow](docs/03-kanban-workflow.md)
- [04 - Consensus Protocol](docs/04-consensus-protocol.md)
- [05 - Scientist Audits](docs/05-scientist-audits.md)
- [06 - Skills Reference](docs/06-skills-reference.md)
- [07 - Edge Cases & Safety](docs/07-edge-cases.md)
- [08 - Glossary Governance](docs/08-glossary-governance.md)
- [09 - Operations](docs/09-operations.md)

## Runtime

- **Production:** [Anthropic](https://anthropic.com) — Opus 4 (translation) + Sonnet 4 (review/audit)
- **Test:** [z.ai](https://z.ai) (Zhipu AI) — GLM-4.7-Flash/FlashX (free) + GLM-5.1 (scientists)
- **Switch:** `make env-prod` / `make env-test`
- **Framework:** Hermes Agent v0.15+
