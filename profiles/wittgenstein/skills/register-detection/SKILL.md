---
name: register-detection
description: Classify the register and formality level of the source text. Outputs a register label and Sie/du recommendation for downstream skills. Does NOT produce or modify translations.
trigger: source text received for classification (pre-translation analysis only)
---

# Register Detection

## Purpose

Register misalignment is one of the most common translation failures. A legal brief translated into conversational German, or a casual email rendered in Kanzleideutsch, destroys the communicative intent even when every word is technically correct. This skill runs on every translation unit to establish the register baseline that other skills depend on.

## Register Taxonomy

| Register | Description | English Signals | German Equivalent | Sie/du |
|---|---|---|---|---|
| **academic** | Scholarly, peer-addressed | Passive voice, hedging, citation markers, Latinate vocabulary, complex subordination | Wissenschaftssprache: nominalization, Passiv, Konjunktiv I for indirect speech | Sie |
| **legal** | Statutory, contractual | Shall/hereby/whereas, defined terms, long sentences, archaic forms | Rechtssprache: hiermit, gemaess, unbeschadet, complex Genitive chains | Sie |
| **medical** | Clinical, patient-facing varies | Greek/Latin terminology, abbreviations, passive constructions | Medizinische Fachsprache: Latin terms retained or Germanized depending on audience | Sie |
| **business-formal** | Corporate, external | Full sentences, no contractions, titles used, measured tone | Geschaeftssprache: Konjunktiv II, formal salutations (Sehr geehrte/r) | Sie |
| **business-casual** | Workplace, internal | Some contractions, first names, direct tone, light humor | Halbformell: polite but relaxed, first names acceptable | Sie (default) or du (if company culture known) |
| **informal** | Friends, peers | Contractions, slang lite, incomplete sentences, emoji in text | Umgangssprache: particles (halt, eben, mal), contractions (gibt's) | du |
| **colloquial** | Very casual, spoken | Heavy contractions, filler words, dialect markers | Alltagssprache: regional coloring acceptable, particles heavy | du |
| **slang** | Youth/subculture | Neologisms, code-switching, non-standard grammar | Jugendsprache / Szenesprache: English loanwords, verlan-style play | du |

## Detection Signals

### Vocabulary Complexity
- **High**: Latinate/Greek roots, domain jargon, nominalization → academic/legal/medical
- **Medium**: Standard professional vocabulary, no jargon → business-formal/casual
- **Low**: Common words, slang, colloquialisms → informal/colloquial/slang

### Sentence Structure
- **Complex subordination** (3+ clauses): academic, legal
- **Moderate subordination** (1-2 dependent clauses): business-formal
- **Simple/compound sentences**: business-casual, informal
- **Fragments, run-ons**: colloquial, slang

### Contractions
- **None**: formal registers (academic, legal, business-formal)
- **Standard** (don't, it's, we're): informal, business-casual
- **Heavy** (gonna, wanna, y'all): colloquial, slang

### Pragmatic Markers
- "Dear Sir/Madam" → business-formal / legal
- "Hi [Name]" → business-casual
- "Hey" / "Yo" → informal / colloquial
- Hedging density → academic
- Imperative frequency → instructional or informal

### Domain Jargon
- Legal terms (hereinafter, indemnify) → legal
- Medical terms (contraindicated, prognosis) → medical
- Technical terms → assess sub-domain

## Sie/du Decision Matrix

| Factor | Sie | du |
|---|---|---|
| Unknown audience | X | |
| External business communication | X | |
| Legal/official documents | X | |
| Academic publications | X | |
| Internal team communication (traditional company) | X | |
| Internal team communication (startup/tech) | | X |
| Marketing to young demographic | | X |
| Children's content | | X |
| Social media (brand voice casual) | | X |
| User manuals (traditional) | X | |
| User manuals (tech/app) | | X |
| Customer support (default) | X | |

When the source text does not provide enough signal, default to **Sie**. It is easier to correct an overly formal translation than to recover from inappropriate informality.

## Domain Boundary

This skill ONLY classifies register. It does NOT:
- Produce Sie/du corrections on translations (that is Frege's `formality-calibration` skill)
- Judge whether a translation's formality level is correct (that is Frege's domain)
- Recommend vocabulary changes based on register (that is Frege's `tone-preservation` skill)

Output from this skill feeds INTO the translation process as pre-analysis. Frege's `formality-calibration` skill validates the result AFTER translation.

## Output Format

```yaml
register: business-formal
confidence: 0.87
signals:
  vocabulary_complexity: medium-high
  sentence_structure: moderate_subordination
  contractions: none
  pragmatic_markers: ["Dear Mr.", "formal closing"]
  domain_jargon: ["quarterly results", "fiscal year"]
german_register: Geschaeftssprache
sie_du: Sie
notes: "Source uses American business English conventions. German output should use Sehr geehrte/r salutation and Konjunktiv II for requests."
```

## Edge Cases

- **Mixed register**: Some texts shift register (e.g., a business email that starts formal and ends casual). Flag the shift and recommend consistent German register unless the shift is intentional.
- **Transcribed speech**: Spoken language transcribed formally. Detect oral markers (fillers, repetition) even in "clean" text.
- **Marketing copy**: Often mixes registers deliberately. Preserve the tonal shifts.
- **Localized English**: British vs. American English may signal different formality defaults (British English often reads as slightly more formal).
