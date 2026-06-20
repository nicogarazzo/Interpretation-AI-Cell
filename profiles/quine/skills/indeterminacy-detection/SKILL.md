---
name: indeterminacy-detection
description: Detect cases where German grammar forces disambiguation that English intentionally or accidentally leaves open, following Quine's thesis of indeterminacy of translation.
trigger: translation unit contains gender-neutral pronouns, quantifier scope ambiguity, or PP-attachment ambiguity that German grammar will force-resolve
---

# Indeterminacy Detection

## Purpose

Quine's indeterminacy thesis holds that there is no fact of the matter about which translation is "correct" when the source underdetermines meaning. English tolerates certain ambiguities that German grammar cannot preserve — grammatical gender, case marking, and compound noun structure all force choices the source never made. This skill detects these forced-disambiguation points and distinguishes between meaning-affecting and purely grammatical resolutions.

## Core Principle

**Flag if the forced choice affects meaning. Accept if it is purely grammatical.**

## Domain Boundary with ambiguity-scoring

This skill detects where German GRAMMAR forces a choice the source left open. `ambiguity-scoring` classifies and scores the ambiguity itself. When both skills apply to the same span:
- `ambiguity-scoring` owns the classification (type) and impact score
- This skill owns the analysis of HOW German resolves it and whether the resolution is defensible
- Do not duplicate the ambiguity classification — reference `ambiguity-scoring`'s output instead

## Forced-Disambiguation Categories

### 1. Gender-Neutral Pronouns → Grammatical Gender

English "they" (singular), "it" (for animals/babies), and role nouns ("the doctor", "the teacher") leave gender unspecified. German forces a choice.

| English | Problem | German Options | Recommendation |
|---|---|---|---|
| "The doctor said they would..." | Singular they → er/sie | "Der Arzt sagte, er wuerde..." / "Die Aerztin sagte, sie wuerde..." | If gender unknown: restructure to avoid pronoun ("Die aerztliche Empfehlung lautet...") |
| "The user enters their password" | Generic their | "Der Benutzer gibt sein Passwort ein" / "Die Benutzerin gibt ihr..." | Tech context: use gender-neutral forms or Gendern (Benutzer:innen) per style guide |
| "Someone left their bag" | Indefinite + their | "Jemand hat seine/ihre Tasche..." | Default: "seine" (traditional) or "die eigene Tasche" (neutral restructure) |
| "The cat... it" | Animal → grammatical gender | "die Katze... sie" (feminine by grammar) | Follow German grammatical gender of the noun |

### 2. Compound Noun Disambiguation

English noun stacks are structurally ambiguous. German compound nouns force a specific hierarchical reading.

| English | Readings | German Forces |
|---|---|---|
| "child language acquisition" | [child language] acquisition vs. child [language acquisition] | Kinderspracherwerbung vs. Kinderspracherwerb — different compounds encode different readings |
| "small business owner" | [small business] owner vs. small [business owner] | Kleinunternehmer (small-business owner) vs. kleiner Geschaeftsinhaber (small business-owner) |
| "French history teacher" | Teacher of French history vs. French teacher of history | Franzoesischgeschichtslehrer vs. franzoesischer Geschichtslehrer |

### 3. Case System Resolution

German's four-case system (Nominativ, Akkusativ, Dativ, Genitiv) disambiguates grammatical relations that English word order leaves flexible.

| English | Ambiguity | German Resolution |
|---|---|---|
| "The mother loves the daughter" | No ambiguity (SVO fixed) | "Die Mutter liebt die Tochter" — but flexible word order possible: "Die Tochter liebt die Mutter" means the same if cases are clear; with other nouns, case marking resolves |
| "John gave the man the book" | Double object — which is indirect? | Dative marks the recipient: "...gab dem Mann das Buch" |

### 4. Quantifier Scope

English quantifier scope is often ambiguous between surface and inverse scope. German word order and intonation partially fix scope.

| English | Readings | German |
|---|---|---|
| "Every student read a book" | One book for all vs. each read a different book | "Jeder Student hat ein Buch gelesen" — still ambiguous but default is distributive in German |
| "A guard is standing in front of every building" | One guard vs. one per building | Word order and article choice force a reading |

### 5. PP-Attachment

| English | Attachment Options | German |
|---|---|---|
| "She discussed the problem with the manager" | Discussed-with-manager vs. problem-with-manager | German case/preposition may disambiguate, or may need restructuring |
| "He ate the pizza on the table" | Ate-on-table vs. pizza-on-table | "Er ass die Pizza auf dem Tisch" — still ambiguous; "die Pizza, die auf dem Tisch lag" for clarity |

## Decision Protocol

```
1. DETECT: Identify forced-disambiguation points in the translation.
2. CLASSIFY: Categorize the type (gender, compound, case, quantifier, PP).
3. ASSESS: Does the forced choice change the possible meanings?
   - YES → FLAG as meaning-affecting indeterminacy
   - NO  → ACCEPT as purely grammatical resolution
4. For flagged items:
   a. List the readings the source permits.
   b. List the reading the German translation selects.
   c. Assess whether context resolves the indeterminacy.
   d. If not: recommend restructuring to preserve openness, or annotate the choice made.
```

## Output Format

```yaml
indeterminacies:
  - source_span: "The researcher presented their findings"
    type: gender_neutral_pronoun
    source_permits: [male, female, non-binary, unspecified]
    german_forces: "specific grammatical gender via article + pronoun"
    meaning_affected: true
    context_resolves: false
    recommendation: "Restructure: 'Die Forschungsergebnisse wurden vorgestellt' (passive avoids pronoun)"
    alternative: "Die forschende Person stellte ihre Ergebnisse vor"
```
