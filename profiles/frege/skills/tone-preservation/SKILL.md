---
name: tone-preservation
description: Preserve the emotional tone and connotative meaning of the source text, including irony, sarcasm, euphemism, and emotional register.
trigger: source contains emotionally charged language, irony, sarcasm, euphemism, or marked tonal shifts
---

# Tone Preservation

## Purpose

Tone is the emotional texture of a text — the difference between "We need to talk" (ominous) and "Let's catch up" (warm). A translation can be semantically accurate and tonally wrong. This skill ensures that the emotional and connotative layer of the source survives into German, using the full range of German tonal resources: modal particles, diminutives, word choice, and sentence rhythm.

## Tone Spectrum

### Positive Axis
```
neutral → warm → enthusiastic → passionate
```

### Negative Axis
```
neutral → cool → distant → hostile
```

### Specialized Tones
- **Ironic**: Surface meaning contradicts intended meaning
- **Sarcastic**: Irony with contempt
- **Euphemistic**: Softened presentation of harsh reality
- **Understated**: Deliberately muted emotional expression (British English specialty)
- **Hyperbolic**: Deliberately amplified emotional expression
- **Melancholic**: Quiet sadness, nostalgia
- **Authoritative**: Confidence without aggression

## German Tone Markers

### Modal Particles

German modal particles are the primary mechanism for encoding tone. They have no direct English equivalents and are often the key to natural-sounding German.

| Particle | Tone Effect | Example |
|---|---|---|
| **ja** | Shared knowledge, mild emphasis | "Das ist ja bekannt" (as we all know) |
| **doch** | Contradiction, insistence, reassurance | "Komm doch mal vorbei" (do come by — encouraging) |
| **mal** | Casualness, softening | "Schau mal" (just look — casual) |
| **schon** | Concession, reassurance | "Das wird schon" (it'll be fine — reassuring) |
| **halt** | Resignation, acceptance | "So ist es halt" (that's just how it is) |
| **eben** | Finality, inevitability | "Das ist eben so" (that's just the way it is — more definitive than halt) |
| **wohl** | Probability, hedging | "Er hat wohl vergessen" (he probably forgot — uncertain) |
| **eigentlich** | Actually, counter-expectation | "Eigentlich wollte ich..." (actually, I wanted to...) |
| **ruhig** | Permission, encouragement | "Du kannst ruhig fragen" (feel free to ask) |
| **bloss/nur** | Warning, urgency | "Mach das bloss nicht!" (don't you dare!) |

### Diminutives (-chen, -lein)

| Usage | Tone Effect | Example |
|---|---|---|
| Affection | Warmth, tenderness | "Schaetzchen" (little treasure) |
| Condescension | Belittling | "Na, mein Freundchen" (well, my little friend — threatening) |
| Trivialization | Dismissive | "ein Problemchen" (a tiny problem — dismissive) |
| Irony | Sarcastic understatement | "ein Suemmchen" (a tidy little sum — for a large amount) |

### Formal vs. Informal Vocabulary

| Neutral | Formal (cool/distant) | Informal (warm/close) |
|---|---|---|
| bekommen | erhalten | kriegen |
| anfangen | beginnen / ansetzen | loslegen |
| Geld | Mittel / finanzielle Ressourcen | Kohle / Knete |
| sterben | versterben / verscheiden | abkratzen / den Loeffel abgeben |
| essen | speisen / zu sich nehmen | futtern / mampfen |
| reden | erlaeutern / ausfuehren | quatschen / labern |

## Tone-Preserving vs. Tone-Destroying Examples

| Source (EN) | Tone | Tone-Preserving (DE) | Tone-Destroying (DE) | Problem |
|---|---|---|---|---|
| "Oh, what a *lovely* surprise." (sarcastic) | Sarcastic | "Oh, was fuer eine *reizende* Ueberraschung." | "Oh, was fuer eine schoene Ueberraschung." | "schoen" reads as genuine; "reizend" preserves the acid |
| "We regret to inform you..." | Formal-distant | "Wir bedauern, Ihnen mitteilen zu muessen..." | "Leider muessen wir sagen..." | "sagen" is too casual for the register |
| "I'm so done with this." | Frustrated-informal | "Ich hab so die Schnauze voll." | "Ich bin damit fertig." | "fertig" is neutral; "Schnauze voll" captures frustration |
| "Not bad at all, actually." | Understated approval | "Gar nicht schlecht, eigentlich." | "Das ist gut." | Understatement destroyed; "eigentlich" preserves the hedging |
| "Rest in peace, old friend." | Melancholic-warm | "Ruhe in Frieden, alter Freund." | "Der Verstorbene moege in Frieden ruhen." | Warmth replaced by bureaucratic distance |
| "This is absolutely unacceptable!" | Hostile-authoritative | "Das ist absolut inakzeptabel!" | "Das geht nicht." | Intensity dramatically reduced |

## Detection Signals

### Irony/Sarcasm Indicators
- Italicized or quoted words ("*wonderful*", "so-called")
- Hyperbolic praise in negative context
- Contrast between literal meaning and situational expectation
- Exclamation marks in unexpected places

### Euphemism Indicators
- Indirect reference to taboo topics (death, firing, failure)
- Passive constructions hiding agency ("mistakes were made")
- Abstract nouns replacing concrete actions ("downsizing" = firing)

### Emotional Charge Indicators
- Exclamation marks, ellipses
- Intensifiers (absolutely, utterly, incredibly)
- Loaded vocabulary (freedom vs. anarchy, reform vs. upheaval)
- Sentence length variation (short punchy sentences = urgency/anger)

## Domain Boundary with sinn-bedeutung

This skill owns the EMOTIONAL texture of the text. `sinn-bedeutung` owns the COGNITIVE mode of presentation. See `sinn-bedeutung/SKILL.md` for the euphemism overlap resolution protocol. In short: if the primary function is emotional register → this skill; if it's referential presentation → `sinn-bedeutung`.

## Decision Procedure

1. Identify the dominant tone of the source passage.
2. Identify tonal markers (particles, word choice, punctuation, structure).
3. Map to German tonal resources:
   - Select appropriate modal particles
   - Choose vocabulary at the right connotative level
   - Adjust sentence rhythm to match emotional pacing
4. Verify the translation reads with the same emotional effect to a native German speaker.
5. Flag cases where German lacks a direct tonal equivalent and a compromise was made.

## Output Format

```yaml
source_tone: sarcastic
tone_markers:
  - italicized "lovely"
  - contrast with negative context
german_tone_strategy:
  particles: []
  vocabulary: "reizend (ironic register)"
  punctuation: preserved
tone_preserved: true
confidence: 0.88
```
