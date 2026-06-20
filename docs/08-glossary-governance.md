# Glossary Governance

The glossary is the single source of truth for terminology in the Interpretation AI Cell pipeline. It ensures that key terms are translated consistently across all translation units, all agents, and all time. This document covers the glossary's structure, governance workflow, seed content, and scaling plan.

---

## The Canonical Glossary

The canonical glossary lives at `shared/glossary.yml`. Every agent reads from this file; no agent writes to it directly. Changes go through the governance workflow described below.

### File Structure

```yaml
# shared/glossary.yml
version: 12
last_updated: 2026-05-29
updated_by: frege

entries:
  - source: "data protection"
    target: "Datenschutz"
    domain: legal
    notes: "Use in all regulatory and compliance contexts"
    approved_by: frege
    approved_date: 2026-05-15
    review_required: false

  - source: "machine learning"
    target: "maschinelles Lernen"
    domain: technology
    notes: "Never abbreviate to 'ML' in German output"
    approved_by: frege
    approved_date: 2026-05-15
    review_required: false

  - source: "informed consent"
    target: "informierte Einwilligung"
    domain: medical
    notes: "Legal/medical term - human review required for context"
    approved_by: frege
    approved_date: 2026-05-20
    review_required: true
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `source` | Yes | English source term or phrase (case-insensitive matching) |
| `target` | Yes | Approved German translation |
| `domain` | Yes | Domain tag: `technology`, `legal`, `business`, `medical`, `general` |
| `notes` | No | Usage notes, context guidance, or exceptions |
| `approved_by` | Yes | Must be `frege` or `human` |
| `approved_date` | Yes | ISO 8601 date of approval |
| `review_required` | No | If `true`, Translator flags uses for human review even after glossary match |
| `deprecated` | No | If `true`, entry is retained for history but not enforced |
| `replaces` | No | Source term of the entry this one supersedes |
| `conflict_resolution` | No | Rationale for choosing this term over alternatives |

---

## Seed Glossary

The pipeline ships with a seed glossary of approximately 50 terms covering the most common translation needs across five domains. This provides a working baseline from day one.

### Technology (~12 terms)

| Source | Target | Notes |
|--------|--------|-------|
| machine learning | maschinelles Lernen | Never abbreviate |
| artificial intelligence | kunstliche Intelligenz | KI is acceptable as abbreviation |
| cloud computing | Cloud Computing | Borrowed term, no translation |
| data center | Rechenzentrum | |
| open source | Open Source | Borrowed, capitalize both words |
| API | API | Acronym, no translation |
| software | Software | Borrowed |
| hardware | Hardware | Borrowed |
| database | Datenbank | |
| user interface | Benutzeroberflache | UI acceptable in technical docs |
| deployment | Bereitstellung | In DevOps context |
| repository | Repository | Borrowed in tech context |

### Legal (~10 terms)

| Source | Target | Notes |
|--------|--------|-------|
| data protection | Datenschutz | Regulatory contexts |
| privacy policy | Datenschutzerklarung | |
| terms of service | Nutzungsbedingungen | |
| liability | Haftung | |
| compliance | Compliance | Borrowed in business; "Einhaltung" in formal legal |
| intellectual property | geistiges Eigentum | |
| non-disclosure agreement | Geheimhaltungsvereinbarung | NDA acceptable in informal |
| jurisdiction | Gerichtsbarkeit | |
| binding | verbindlich | Adjective form |
| indemnification | Freistellung | Legal term of art |

### Business (~10 terms)

| Source | Target | Notes |
|--------|--------|-------|
| stakeholder | Stakeholder | Borrowed; "Interessengruppe" in formal |
| revenue | Umsatz | |
| quarterly report | Quartalsbericht | |
| market share | Marktanteil | |
| supply chain | Lieferkette | |
| key performance indicator | Leistungskennzahl | KPI acceptable |
| return on investment | Kapitalrendite | ROI acceptable |
| scalability | Skalierbarkeit | |
| benchmark | Benchmark | Borrowed |
| workflow | Arbeitsablauf | "Workflow" acceptable in tech contexts |

### Medical (~10 terms)

| Source | Target | Notes |
|--------|--------|-------|
| informed consent | informierte Einwilligung | Always human-review |
| clinical trial | klinische Studie | |
| adverse event | unerwinschtes Ereignis | |
| dosage | Dosierung | |
| diagnosis | Diagnose | |
| patient record | Patientenakte | |
| contraindication | Kontraindikation | |
| prognosis | Prognose | |
| pathology | Pathologie | |
| therapeutic | therapeutisch | |

### General (~8 terms)

| Source | Target | Notes |
|--------|--------|-------|
| however | jedoch / allerdings | Context-dependent |
| therefore | daher / deshalb | Context-dependent |
| approximately | etwa / ungefahr | |
| significant | erheblich / bedeutend | Not "signifikant" unless statistical |
| implement | umsetzen | Not "implementieren" in non-tech |
| regarding | bezuglich / hinsichtlich | |
| in addition | daruber hinaus / zudem | |
| ensure | sicherstellen / gewahrleisten | "Gewahrleisten" for guarantees |

---

## False Friends

False friends (falsche Freunde) are English-German word pairs that look similar but have different meanings. These are among the most common translation errors and receive special handling.

The glossary includes a dedicated false friends section that the `glossary-enforcement` skill checks with high priority:

| English | Incorrect German | Correct German | Note |
|---------|-----------------|----------------|------|
| eventually | ~~eventuell~~ | schliesslich / letztendlich | "eventuell" means "possibly" |
| actual | ~~aktuell~~ | tatsachlich / eigentlich | "aktuell" means "current" |
| become | ~~bekommen~~ | werden | "bekommen" means "to receive" |
| gift | ~~Gift~~ | Geschenk | "Gift" means "poison" |
| brave | ~~brav~~ | mutig / tapfer | "brav" means "well-behaved" |
| chef | ~~Chef~~ | Kuchenchef / Koch | "Chef" means "boss" |
| fabric | ~~Fabrik~~ | Stoff / Gewebe | "Fabrik" means "factory" |
| sensible | ~~sensibel~~ | vernunftig / sinnvoll | "sensibel" means "sensitive" |
| sympathetic | ~~sympathisch~~ | mitfuhlend / verstandnisvoll | "sympathisch" means "likeable" |
| consequent | ~~konsequent~~ | daraus folgend | "konsequent" means "consistent" |
| map | ~~Mappe~~ | Karte / Landkarte | "Mappe" means "folder/binder" |
| novel | ~~Novelle~~ | Roman | "Novelle" is a specific literary form |
| ordinary | ~~ordinar~~ | gewohnlich / normal | "ordinar" means "vulgar" |
| prospect | ~~Prospekt~~ | Aussicht / Perspektive | "Prospekt" means "brochure" |
| undertaker | ~~Unternehmer~~ | Bestattungsunternehmer | "Unternehmer" means "entrepreneur" |

False friend entries are stored in the glossary with a special flag:

```yaml
  - source: "eventually"
    target: "schliesslich"
    domain: general
    false_friend: true
    false_friend_trap: "eventuell"
    notes: "eventuell = possibly/perhaps, NOT eventually"
    approved_by: frege
    approved_date: 2026-05-15
```

When `glossary-enforcement` detects a false friend trap in the translation output, it applies an automatic correction and adds a high-priority flag to the TU metadata.

---

## Governance Protocol

### Who Can Propose Terms

Any agent or human can propose a new glossary entry. Proposals are submitted as Kanban cards:

- **Translator**: Proposes terms when it encounters a recurring translation choice
- **Wittgenstein**: Proposes terms when idiom localization reveals a consistent pattern
- **Frege**: Proposes terms proactively based on domain analysis
- **Human operator**: Proposes terms based on client feedback or domain expertise
- **Cho**: Flags inconsistent terminology during audits (implicit proposal)

### Approval Workflow

```
Proposal → Kanban: glossary-proposed → Frege Review → Approved / Rejected
```

1. **Proposal**: A new term is proposed via a Kanban card in the `glossary-proposed` column. The card includes:
   - Source term
   - Proposed target term
   - Domain
   - Justification (why this term, why not alternatives)
   - Example usage (at least one source sentence)

2. **Frege Review**: Frege evaluates the proposal against:
   - Semantic accuracy (Sinn/Bedeutung alignment)
   - Consistency with existing glossary entries
   - Domain appropriateness
   - No conflicts with existing entries

3. **Decision**: Frege moves the card to `glossary-approved` or `glossary-rejected` with a rationale.

4. **Human Review Gate**: For `domain: legal` or `domain: medical`, Frege's approval is necessary but not sufficient. A human domain expert must also sign off. The card moves to `glossary-human-review` before final approval.

5. **Commit**: Approved terms are added to `shared/glossary.yml`, the version number is incremented, and the change is committed to git with a descriptive message.

### Rejection

Rejected proposals are documented with Frege's rationale. The card moves to `glossary-rejected` and remains there for 30 days for reference, then is archived.

---

## Glossary Enforcement in Translation

The `glossary-enforcement` skill (owned by Translator, priority 100) is the runtime mechanism that applies the glossary:

### Matching Rules

1. **Exact phrase match**: The source term must appear as a complete phrase in the source TU. Substring matches within compound words are flagged but not auto-replaced.
2. **Case-insensitive**: "Data Protection" matches "data protection."
3. **Boundary-aware**: Matches respect word boundaries. "data" does not match "database."
4. **Multi-word**: Phrases are matched as units. "terms of service" is a single glossary entry, not three separate words.

### Enforcement Behavior

1. Scan source TU for glossary matches
2. Check if the Translator's output uses the approved target term
3. If yes: no action, log match as confirmed
4. If no: replace with glossary term, log the override
5. If `review_required: true`: flag for human review regardless of match

### Override Logging

Every glossary override is logged in the TU metadata:

```yaml
glossary_overrides:
  - source_term: "data protection"
    model_output: "Schutz der Daten"
    glossary_target: "Datenschutz"
    action: replaced
    timestamp: "2026-05-29T14:32:00Z"
```

This data feeds into Koehn's regression detection -- a rising override rate may indicate model quality issues.

---

## Scaling Plan: YAML to SQLite

The YAML glossary works well for small to medium term bases. As the glossary grows, a migration to SQLite is planned.

### Migration Trigger

When the glossary exceeds approximately 2,000 entries, the following issues become noticeable:

- YAML parse time exceeds 500ms
- Full glossary injection into context windows consumes significant tokens
- Merge conflicts in `glossary.yml` become frequent with multiple contributors

### Migration Path

```
Phase 1: YAML (current, <500 entries)
Phase 2: YAML with domain sharding (<2000 entries)
Phase 3: SQLite with YAML export (<10000 entries)
Phase 4: SQLite with API layer (10000+ entries)
```

#### Phase 2: Domain Sharding

Before migrating to SQLite, the YAML glossary can be split by domain:

```
shared/
  glossary/
    technology.yml
    legal.yml
    business.yml
    medical.yml
    general.yml
    false-friends.yml
    index.yml          # Metadata and cross-references
```

This reduces merge conflicts and allows domain-specific loading (only inject relevant domain entries into context).

#### Phase 3: SQLite

```sql
CREATE TABLE glossary (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    domain TEXT NOT NULL,
    notes TEXT,
    approved_by TEXT NOT NULL,
    approved_date TEXT NOT NULL,
    review_required BOOLEAN DEFAULT FALSE,
    deprecated BOOLEAN DEFAULT FALSE,
    replaces TEXT,
    false_friend BOOLEAN DEFAULT FALSE,
    false_friend_trap TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX idx_source ON glossary(source);
CREATE INDEX idx_domain ON glossary(domain);
CREATE INDEX idx_false_friend ON glossary(false_friend);
```

A YAML export is generated on every change for backward compatibility and git tracking:

```bash
make glossary-export   # SQLite → YAML dump for git commit
```

#### Phase 4: API Layer

For very large glossaries, an HTTP API layer allows:
- Fuzzy matching and search
- Batch lookups
- Usage analytics
- Multi-user concurrent editing

This phase is far-future and only relevant if the system scales to enterprise-level terminology management.

---

## Versioning

Every change to the glossary is tracked in git:

### Commit Convention

```
glossary: add "Datenschutz" (legal domain)
glossary: update "compliance" target for formal legal context
glossary: deprecate "Privatsphare" in favor of "Datenschutz"
glossary: add false friend "eventually/eventuell"
```

### Version Number

The `version` field in `glossary.yml` is incremented with every change:

- Adding an entry: version +1
- Modifying an entry: version +1
- Deprecating an entry: version +1
- No change for reformatting or comment-only edits

### Diffing

To see what changed between glossary versions:

```bash
# Show glossary changes in the last 5 commits
git log -5 --oneline -- shared/glossary.yml

# Show detailed diff for a specific change
git diff HEAD~1 -- shared/glossary.yml

# Show all entries added since a specific date
git log --after="2026-05-01" --oneline -- shared/glossary.yml
```

### Cho's Integrity Check

Cho's weekly audit verifies glossary integrity:

- All entries have required fields
- No duplicate source terms within the same domain
- Version number matches the actual number of historical changes
- All `approved_by` values are valid (either `frege` or `human`)
- No `deprecated: true` entries are still being enforced by `glossary-enforcement`
