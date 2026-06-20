---
name: idiom-localization
description: Detect English idioms and map them to pragmatically equivalent German idioms, avoiding literal translations that destroy idiomatic meaning.
trigger: idiomatic expression detected in source OR literal translation would lose pragmatic meaning
---

# Idiom Localization

## Purpose

English idioms rarely survive literal translation into German. This skill identifies idiomatic expressions in the source text and retrieves pragmatically equivalent German idioms, preserving communicative intent rather than surface form.

## Decision Procedure

1. **Identify**: Scan the source text for fixed or semi-fixed multi-word expressions whose meaning is non-compositional.
2. **Assess Intent**: Determine the pragmatic function of the idiom (emphasis, understatement, humor, warning, encouragement, etc.).
3. **Retrieve Equivalents**: Rank candidate German idioms by:
   - **Pragmatic equivalence** (same communicative effect) — highest priority
   - **Register match** (formal/informal alignment with source)
   - **Regional appropriateness** (Hochdeutsch is default; mark Austrian/Swiss variants)
4. **Select**: Choose the highest-ranked candidate. If no German idiom achieves pragmatic equivalence, use a non-idiomatic paraphrase and flag the loss.

## Common EN→DE Idiom Mappings

| English Idiom | BAD (Literal) | GOOD (Localized) | Notes |
|---|---|---|---|
| break the ice | das Eis brechen | das Eis brechen | Rare direct match |
| hit the nail on the head | den Nagel auf den Kopf treffen | den Nagel auf den Kopf treffen | Direct equivalent exists |
| it's raining cats and dogs | es regnet Katzen und Hunde | es regnet in Stroemen / es giesst wie aus Eimern | Literal is nonsensical |
| bite the bullet | die Kugel beissen | in den sauren Apfel beissen | Different image, same pragmatics |
| spill the beans | die Bohnen verschuetten | die Katze aus dem Sack lassen | Different image, same function |
| the ball is in your court | der Ball ist in deinem Feld | jetzt bist du am Zug | Sports → chess metaphor shift |
| piece of cake | ein Stueck Kuchen | ein Kinderspiel / ein Klacks | Food → child's play |
| break a leg | brich dir ein Bein | Hals- und Beinbruch! / toi, toi, toi! | Theater tradition preserved |
| burn the midnight oil | das Mitternachtsoel verbrennen | die Nacht zum Tag machen | Oil lamp → day/night inversion |
| let the cat out of the bag | die Katze aus der Tasche lassen | die Katze aus dem Sack lassen | Bag→Sack, close but not identical |
| cost an arm and a leg | einen Arm und ein Bein kosten | ein Vermoegen kosten / eine Stange Geld kosten | Body parts → fortune |
| once in a blue moon | einmal bei blauem Mond | alle Jubeljahre (einmal) | Astronomical → temporal |
| beat around the bush | um den Busch herumschlagen | um den heissen Brei herumreden | Bush → hot porridge |
| under the weather | unter dem Wetter | nicht auf der Hoehe / angeschlagen | Weather metaphor doesn't transfer |
| call it a day | nenn es einen Tag | Feierabend machen / Schluss machen | German has a dedicated concept |
| on the same page | auf der gleichen Seite | auf dem gleichen Stand sein | Page → status |
| the last straw | der letzte Strohhalm | der Tropfen, der das Fass zum Ueberlaufen bringt | Straw → drop that overflows the barrel |
| pull someone's leg | jemandes Bein ziehen | jemanden auf den Arm nehmen | Leg → arm |
| when pigs fly | wenn Schweine fliegen | wenn Schweine fliegen / am Sankt-Nimmerleins-Tag | Pigs fly works; saint's day variant exists |
| add fuel to the fire | Oel ins Feuer giessen | Oel ins Feuer giessen | Direct match |

## Failure Modes

- **Over-application**: Treating literal uses of idiomatic words as idioms (e.g., "he broke the ice on the pond" is literal, not idiomatic).
- **Register mismatch**: Substituting a colloquial German idiom for a formal English one or vice versa.
- **False friends**: German idioms that look similar but carry different connotations.
- **Regional bias**: Using Austrian or Swiss idioms when Hochdeutsch is expected.

## Output Format

```yaml
idiom_detected: "bite the bullet"
source_intent: acceptance of a difficult situation
literal_translation: "die Kugel beissen"
literal_viable: false
recommended: "in den sauren Apfel beissen"
register: informal
confidence: 0.92
alternatives:
  - "die bittere Pille schlucken" # slightly more formal
```

## Learned Refinements

<!-- This section is reserved for Hermes reflection. The agent will append learned patterns, edge cases, and corrections discovered during translation runs. Do not manually edit. -->
