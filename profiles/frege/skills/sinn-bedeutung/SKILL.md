---
name: sinn-bedeutung
description: Audit the Sinn (sense / mode of presentation) vs Bedeutung (reference) integrity of translations, ensuring that how a referent is presented is preserved alongside what is referred to.
trigger: translation changes how a referent is presented or introduces referential errors
---

# Sinn-Bedeutung Audit

## Purpose

Frege's distinction: two expressions can share the same Bedeutung (reference — the object in the world) but differ in Sinn (sense — the cognitive path by which the reference is reached). "The morning star" and "the evening star" both refer to Venus, but they present Venus differently. A translation that preserves reference but destroys sense has failed, even though it is "technically correct."

This skill audits translations for Sinn preservation — ensuring that the mode of presentation in the source survives in the target.

## Core Categories

### 1. Definite Descriptions
Expressions of the form "the X" that pick out a referent via a descriptive path.

- **Source**: "the author of Hamlet" → **Bedeutung**: Shakespeare. **Sinn**: via authorship relation.
- Translation must preserve the descriptive path, not substitute the name.

### 2. Proper Names vs. Descriptions
A proper name and a definite description can co-refer but carry different Sinn.

- "Germany's capital" vs. "Berlin" — same Bedeutung, different Sinn.
- If the source uses the description, the translation should too (unless German conventions demand otherwise).

### 3. Metaphorical References
Metaphors present a referent through an image. Replacing the metaphor with a literal term destroys the Sinn.

- "the iron curtain" → "der Eiserne Vorhang" (Sinn preserved)
- "the iron curtain" → "die Grenze zwischen Ost und West" (Bedeutung preserved, Sinn destroyed)

### 4. Connotative Framing
Two words can denote the same thing but connote differently.

- "freedom fighter" vs. "insurgent" — same referent, opposite Sinn
- "economical" vs. "cheap" — same referent, different evaluation

## Sinn-Preserving vs. Sinn-Destroying Examples

| Source | Sinn-Preserving Translation | Sinn-Destroying Translation | Why |
|---|---|---|---|
| "the city that never sleeps" | "die Stadt, die niemals schlaeft" | "New York" | Destroys the metaphorical presentation |
| "the Iron Lady" | "die Eiserne Lady" | "Margaret Thatcher" | Destroys the epithet's connotations (strength, inflexibility) |
| "the roof of the world" | "das Dach der Welt" | "Tibet / der Himalaya" | Destroys the spatial metaphor |
| "Big Brother is watching" | "Big Brother beobachtet" / "der Grosse Bruder sieht zu" | "Die Regierung ueberwacht" | Destroys the Orwellian allusion |
| "to err is human" | "Irren ist menschlich" | "Menschen machen Fehler" | Destroys the aphoristic form (itself part of the Sinn) |
| "affordable housing" | "bezahlbarer Wohnraum" | "billiger Wohnraum" | "billig" carries negative connotation (cheap/shoddy) |
| "developing nations" | "Entwicklungslaender" | "arme Laender" | Destroys the diplomatic/progressive framing |
| "passed away" | "ist von uns gegangen" / "ist verstorben" | "ist gestorben" | "gestorben" is neutral; source uses euphemism (Sinn = gentle presentation of death) |

## Sinn Analysis Template

For each flagged translation unit, produce:

```yaml
source_expression: "the city that never sleeps"
source_bedeutung: New York City
source_sinn: "Metropolis characterized by perpetual activity; romanticized, admiring tone"
target_expression: "die Stadt, die niemals schlaeft"
target_bedeutung: New York City
target_sinn: "Metropolis characterized by perpetual activity; romanticized, admiring tone"
sinn_preserved: true
impact: null  # only filled when sinn_preserved = false
```

When Sinn is NOT preserved:

```yaml
source_expression: "passed away"
source_bedeutung: died
source_sinn: "Euphemistic, gentle, respectful presentation of death"
target_expression: "gestorben"
target_bedeutung: died
target_sinn: "Neutral, clinical, factual presentation of death"
sinn_preserved: false
impact: "Euphemistic register destroyed. Source signals emotional sensitivity; target is blunt."
recommended: "ist von uns gegangen / ist verstorben / ist verschieden"
```

## Decision Procedure

1. Identify expressions where the mode of presentation carries meaning beyond the reference.
2. Check whether the translation preserves that mode.
3. If not, assess the impact:
   - **High**: Metaphor destroyed, connotation reversed, allusion lost, euphemism stripped
   - **Medium**: Slight connotative shift but referent and general tone preserved
   - **Low**: Stylistic variation that does not affect reader's cognitive experience
4. For high/medium impact: flag and recommend alternatives.

## Domain Boundary with tone-preservation

This skill and `tone-preservation` address different layers of Frege's framework:
- **sinn-bedeutung**: Cognitive mode of presentation — HOW a referent is introduced (metaphor, description, epithet, euphemism as a presentational choice)
- **tone-preservation**: Emotional texture — HOW the text FEELS (irony, sarcasm, warmth, hostility)

**Overlap zone — euphemistic language**: Euphemism affects both Sinn (mode of presentation) and tone (emotional register). Resolution:
- If the euphemism's primary function is to present a referent differently ("passed away" for "died"), `sinn-bedeutung` owns it
- If the euphemism's primary function is emotional softening ("let go" for "fired" in a conversation about feelings), `tone-preservation` owns it
- When both apply, `sinn-bedeutung` flags the Sinn dimension and `tone-preservation` flags the tonal dimension — they should not duplicate findings

## Edge Cases

- **Culturally bound Sinn**: Some modes of presentation rely on source-culture knowledge ("the Beltway" = Washington politics). German readers may not share this. In such cases, a Sinn-destroying but clarity-preserving translation may be justified — but annotate the loss.
- **Technical Sinn**: In scientific/legal texts, the mode of presentation IS the content ("the accused" vs. "the defendant" have legal Sinn). Preserve exactly.
- **Dead metaphors**: "the foot of the mountain" — the metaphor is lexicalized. German "der Fuss des Berges" preserves it naturally. No flag needed.
