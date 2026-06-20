---
name: formality-calibration
description: Validate and calibrate the formality level of German output against the source text. Owns the final Sie/du decision, Konjunktiv II usage, vocabulary register, and grammatical correctness of formality markers (articles, gender, case).
trigger: always (formality calibration is required for every translation unit)
---

# Formality Calibration

## Purpose

German has a richer formality apparatus than English — the Sie/du distinction, Konjunktiv II as a politeness mechanism, compound noun density, and vocabulary stratification between Germanic and Latinate/Greek layers. This skill calibrates the German output so that a native reader perceives the same formality level as an English reader perceives in the source.

## Formality Signals in German

### 1. Sie/du (Address Pronoun)
The single highest-impact formality marker in German. Misusing it is immediately noticeable.

| Formality Level | Pronoun | Possessive | Verb Conjugation |
|---|---|---|---|
| Formal | Sie | Ihr/Ihre | 3rd person plural |
| Informal | du | dein/deine | 2nd person singular |
| Informal plural | ihr | euer/eure | 2nd person plural |

### 2. Konjunktiv II (Subjunctive II)
Functions as a politeness gradient, not just a grammatical mood.

| Directness | Construction | Example |
|---|---|---|
| Direct (informal) | Indicative imperative | "Gib mir das Buch." |
| Neutral | Indicative + bitte | "Geben Sie mir bitte das Buch." |
| Polite | Konjunktiv II | "Koennten Sie mir das Buch geben?" |
| Very polite | Konjunktiv II + particle | "Wuerden Sie mir vielleicht das Buch geben?" |
| Maximally polite | Konjunktiv II + subjunctive frame | "Duerfte ich Sie bitten, mir das Buch zu geben?" |

### 3. Compound Nouns
Higher compound density correlates with higher formality / technicality.

| Informal | Formal |
|---|---|
| Weg zur Arbeit | Arbeitsweg |
| wie man es macht | Vorgehensweise |
| Vertrag fuer die Arbeit | Arbeitsvertrag |

### 4. Latinate/Greek vs. Germanic Vocabulary
Like English, German has a register split between its native Germanic layer and borrowed Latinate/Greek vocabulary.

| Informal (Germanic) | Formal (Latinate/Greek) |
|---|---|
| anfangen | initiieren |
| Grund | Motivation / Ursache |
| zeigen | demonstrieren |
| helfen | assistieren |
| benutzen | utilisieren / verwenden |
| Teil | Komponente |
| kaufen | erwerben / akquirieren |

### 5. Sentence Length and Complexity
| Formality | Sentence Pattern |
|---|---|
| Informal | Short. Simple. Fragments okay. |
| Business-casual | Medium length. One subordinate clause typical. |
| Formal | Longer sentences. Multiple subordinate clauses. Nominalization. |
| Academic/Legal | Very long. Deeply nested subordination. Heavy nominalization. Passive voice. |

## Decision Matrix

| Source Formality | Sie/du | Konjunktiv II | Vocabulary Layer | Compound Density | Sentence Length |
|---|---|---|---|---|---|
| **Slang/Colloquial** | du | None | Germanic, colloquial | Low | Short, fragments |
| **Informal** | du | Rare | Germanic | Low-medium | Short-medium |
| **Business-casual** | Sie (default) | Occasional | Mixed | Medium | Medium |
| **Business-formal** | Sie | Frequent | Mixed, leaning Latinate | Medium-high | Medium-long |
| **Academic** | Sie | Standard | Latinate/Greek heavy | High | Long, complex |
| **Legal** | Sie | Where required | Legal terminology | Very high | Very long |
| **Medical** | Sie | Moderate | Latin terms + German explanations | High | Varies by audience |

## Special Cases

### Academic Writing
- Passive voice dominant ("es wird argumentiert, dass...")
- Konjunktiv I for indirect speech ("Der Autor behaupte, dass...")
- Hedging: "scheint", "duerfte", "laesst sich vermuten"
- Nominalization: prefer "die Untersuchung" over "untersuchen"
- Impersonal constructions: "man" or passive over "ich"

### Legal Texts
- Archaic formulations preserved: "hiermit", "gemaess", "vorbehaltlich", "unbeschadet"
- Genitive chains: "die Bestimmungen des Absatzes 3 des Paragraphen 12"
- Defined terms capitalized and used consistently
- "soll" (should, weak obligation) vs. "muss" (must, strong obligation) vs. "kann" (may, permission) are legally distinct
- No contractions, no colloquialisms, no particles

### Marketing Copy
- Often deliberately breaks formality rules for effect
- May mix Sie and informal tone ("Sie werden begeistert sein!" — formal address, enthusiastic tone)
- Sentence fragments and exclamations acceptable
- Neologisms and English loanwords common in German marketing
- Adjust to target demographic: young = du + English sprinkled; corporate = Sie + polished

### Casual Emails
- du unless organizational culture dictates Sie
- Particles: mal, halt, eben, ja frequently used
- Greetings: "Hi [Name]", "Hallo [Name]", "Hey"
- Closings: "VG" (Viele Gruesse), "LG" (Liebe Gruesse), "Cheers" (increasingly used in German)
- Contractions: "gibt's", "geht's", "hab ich"

## Grammatical Correctness as Formality Prerequisite

Before assessing formality calibration, verify that basic grammatical markers are correct. These are formality-relevant because a wrong article or gender error in a formal text is a critical register violation:

- **Article correctness**: der/die/das must match the noun's grammatical gender (e.g., "das Eis" NOT "die Eis")
- **Case agreement**: adjective endings must agree with case and gender
- **Pronoun consistency**: Sie/du must be consistent throughout the translation unit
- **Verb conjugation**: must match the chosen address form (Sie → 3rd person plural, du → 2nd person singular)

Flag grammatical errors that affect formality perception as `formality_error` with severity `major`.

## Formality Mismatch Detection

Flag when the German output deviates from the source formality by more than one level:

```yaml
source_formality: informal (level 2/6)
target_formality: business-formal (level 4/6)
mismatch: 2 levels  # exceeds threshold
markers_causing_mismatch:
  - Sie used where du is appropriate
  - Konjunktiv II in casual context
  - "erwerben" instead of "kaufen"
recommendation: "Reduce formality: switch to du, drop Konjunktiv II, use Germanic vocabulary"
```

## Output Format

```yaml
source_formality: business-casual
source_signals:
  - contractions present (it's, we're)
  - first-name address
  - one subordinate clause per sentence avg
  - professional vocabulary, no jargon
target_calibration:
  sie_du: Sie
  konjunktiv_ii: occasional
  vocabulary_layer: mixed
  compound_density: medium
  sentence_length: medium
  particles: moderate (mal, vielleicht)
formality_match: true
```
