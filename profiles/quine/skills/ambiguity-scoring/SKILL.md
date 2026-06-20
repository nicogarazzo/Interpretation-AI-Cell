---
name: ambiguity-scoring
description: Score and classify ambiguities in source and target texts, flagging cases where translation introduces or fails to resolve meaning-critical ambiguity.
trigger: translation contains polysemous words, scope ambiguities, or referential opacity
---

# Ambiguity Scoring

## Purpose

Ambiguity is not inherently a flaw — natural language is pervasively ambiguous, and much of it is harmless. This skill distinguishes between ambiguities that affect translation fidelity (impact >= 3) and those that are benign. It classifies ambiguity by type and scores its potential impact on meaning.

## Ambiguity Taxonomy

### 1. Lexical Polysemy
A single word carries multiple distinct meanings. Translation must select the correct sense.

**Detection**: Word has multiple dictionary entries with divergent translations.

### 2. Scope Ambiguity
Quantifiers, negation, or modifiers can attach to different constituents, yielding different truth conditions.

**Detection**: Sentences with multiple quantifiers, negation + quantifier, or adverbial modifiers with unclear attachment.

### 3. Referential Opacity
Substitution of co-referential terms changes truth value in intensional contexts (belief, knowledge, desire).

**Detection**: Propositional attitude verbs (believe, know, want, think) + definite descriptions or proper names.

### 4. Structural Ambiguity
The syntactic parse of a sentence admits multiple bracketings.

**Detection**: PP-attachment ambiguity, relative clause attachment, coordination scope.

## Impact Scoring

| Score | Label | Action |
|---|---|---|
| 1 | Negligible | No action. Ambiguity is resolved by context or is benign. |
| 2 | Minor | Log but do not flag. Translation can safely pick the dominant reading. |
| 3 | Moderate | **Flag.** Translation should note the ambiguity. Dominant reading may not be obvious. |
| 4 | Significant | **Flag + annotate.** Two or more readings are plausible. Translator must choose and justify. |
| 5 | Critical | **Flag + escalate.** Ambiguity affects legal, medical, or safety-critical meaning. Requires human review. |

**Rule: Only flag ambiguities scoring >= 3.**

## Common EN→DE Ambiguity Traps

| # | English Source | Ambiguity Type | Why It's a Trap | German Resolution |
|---|---|---|---|---|
| 1 | "bank" | Lexical polysemy | Financial institution vs. river bank | Bank (finance) vs. Ufer (river) — German disambiguates |
| 2 | "Everyone didn't pass" | Scope | "Not everyone passed" vs. "No one passed" | "Nicht alle haben bestanden" vs. "Niemand hat bestanden" — German forces a choice |
| 3 | "Flying planes can be dangerous" | Structural | The act of flying vs. planes that are flying | "Flugzeuge zu fliegen..." vs. "Fliegende Flugzeuge..." — German disambiguates via construction |
| 4 | "I saw the man with the telescope" | Structural (PP-attachment) | I used the telescope vs. the man had the telescope | "Ich sah den Mann mit dem Fernrohr" remains ambiguous; rewrite needed for clarity |
| 5 | "They" (singular) | Referential | Gender-neutral singular vs. plural | German forces er/sie/es or must restructure (see indeterminacy-detection) |
| 6 | "light" | Lexical polysemy | Not heavy vs. illumination vs. pale | leicht / Licht / hell — German splits into three words |
| 7 | "The chicken is ready to eat" | Structural | Chicken will eat vs. chicken is cooked | "Das Haehnchen ist bereit zu essen" vs. "Das Haehnchen ist fertig zum Essen" — subtle but German can clarify |
| 8 | "No head injury is too trivial to ignore" | Scope (negation) | Intended: treat all injuries. Literal: ignore all injuries. | German must restructure entirely to preserve intended meaning |
| 9 | "John told Bill that he should leave" | Referential | "he" = John or Bill? | German "er" is equally ambiguous; may need to repeat the name |
| 10 | "visiting relatives can be boring" | Structural | The act of visiting vs. relatives who visit | "Verwandte zu besuchen..." vs. "Besuchende Verwandte..." — German disambiguates |

## Domain Boundary with indeterminacy-detection

This skill and `indeterminacy-detection` have complementary scopes:
- **ambiguity-scoring**: Scores and classifies ambiguities that EXIST in the source text and evaluates how translation handles them. Focus: what ambiguities are present?
- **indeterminacy-detection**: Detects points where German GRAMMAR forces disambiguation that English left open. Focus: what choices does German force?

When quantifier scope is both an existing ambiguity AND a forced-disambiguation point, `ambiguity-scoring` flags the ambiguity and scores it; `indeterminacy-detection` assesses whether the German resolution is defensible. They should not duplicate findings — if both fire on the same span, `ambiguity-scoring` provides the classification and score, `indeterminacy-detection` provides the resolution analysis.

## Decision Procedure

1. Parse the translation unit for ambiguity markers (polysemous words, quantifiers, PP-attachment sites, intensional verbs).
2. Classify each detected ambiguity by type.
3. Score impact (1-5) based on:
   - Number of plausible readings
   - Divergence between readings (semantic distance)
   - Domain criticality (legal/medical = higher base score)
   - Whether German resolves or preserves the ambiguity
4. For scores >= 3: generate a structured flag.

## Output Format

```yaml
ambiguities:
  - source_span: "Everyone didn't pass the test"
    type: scope
    readings:
      - "Not everyone passed" (partial negation)
      - "No one passed" (total negation)
    impact: 4
    german_resolution: "German requires explicit choice: 'Nicht alle' vs. 'Niemand'"
    recommended: "Nicht alle haben den Test bestanden"
    justification: "Context suggests partial negation (preceding sentence discusses varying scores)"
```
