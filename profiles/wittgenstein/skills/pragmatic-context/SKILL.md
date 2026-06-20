---
name: pragmatic-context
description: Evaluate whether translation preserves the speech act (request, command, suggestion, apology, etc.) and adjust German output to maintain pragmatic force.
trigger: source contains indirect speech acts, hedging, politeness markers, or modal constructions
---

# Pragmatic Context Preservation

## Purpose

English and German encode politeness, indirectness, and speech acts differently. A grammatically correct translation can still fail pragmatically if it converts a polite request into a blunt command, or strips hedging that signals tentativeness. This skill ensures the illocutionary force of the source survives translation.

## Speech Act Pattern Mapping

| English Pattern | Speech Act | German Equivalent | Notes |
|---|---|---|---|
| Could you please...? | Polite request | Koennten Sie bitte...? | Konjunktiv II required |
| Would you mind...? | Very polite request | Wuerden Sie es stoeren, wenn...? / Wuerde es Ihnen etwas ausmachen...? | High formality |
| You should... | Advice/suggestion | Sie sollten... | Konjunktiv II softens |
| You must... | Obligation | Sie muessen... | Direct; no softening needed |
| I was wondering if... | Tentative inquiry | Ich habe mich gefragt, ob... / Ich wollte fragen, ob... | Preterite adds distance |
| I'm afraid that... | Apologetic framing | Ich befuerchte, dass... / Leider... | Leider is more natural in many contexts |
| Let's... | Inclusive suggestion | Lass uns... / Lassen Sie uns... | Sie/du split |
| Why don't we...? | Soft suggestion | Wie waere es, wenn wir...? | Konjunktiv II |
| If you could just... | Minimizing request | Wenn Sie vielleicht... koennten | Stack: Konjunktiv II + vielleicht |
| I'd appreciate it if... | Formal request | Ich wuerde es begruessen, wenn... | Konjunktiv II |
| Sorry, but... | Hedged disagreement | Entschuldigung, aber... / Verzeihen Sie, aber... | Register-dependent |
| To be honest... | Candor marker | Ehrlich gesagt... / Um ehrlich zu sein... | Direct equivalent |
| It might be worth... | Tentative suggestion | Es koennte sich lohnen... / Vielleicht waere es sinnvoll... | Konjunktiv II + hedging |
| Feel free to... | Permission/invitation | Sie koennen gerne... / Fuehlen Sie sich frei... (avoid) | "Fuehlen Sie sich frei" is a calque; avoid |

## Modal Verb Mapping

| English Modal | Function | German Equivalent | Pragmatic Notes |
|---|---|---|---|
| can | ability/permission | koennen (Indikativ) | Neutral |
| could | polite possibility | koennte (Konjunktiv II) | Adds politeness layer |
| would | conditional/polite | wuerde (Konjunktiv II) | Essential for polite requests |
| should | advice | sollte (Konjunktiv II) | Softer than "soll" |
| shall | formal obligation | soll (Indikativ) | Legal/formal contexts |
| might | tentative possibility | koennte / duerfte | duerfte = more tentative |
| must | strong obligation | muss | No softening |
| ought to | moral obligation | sollte | Same as should in most contexts |

## Hedging Devices

| English Hedge | German Equivalent | Function |
|---|---|---|
| kind of / sort of | irgendwie / gewissermassen | Vagueness |
| a bit / a little | ein bisschen / etwas | Minimizer |
| perhaps / maybe | vielleicht / eventuell | Epistemic uncertainty |
| I think | ich denke / ich glaube / meiner Meinung nach | Epistemic distancing |
| basically | im Grunde / im Wesentlichen | Simplification marker |
| actually | eigentlich / tatsaechlich | Counter-expectation (eigentlich) vs. confirmation (tatsaechlich) |
| just | nur / einfach / mal | Minimizer; "mal" is critical in German requests |

## Bitte Positioning in German

The position of "bitte" changes the pragmatic force:

- **Koennten Sie bitte die Tuer schliessen?** — Standard polite request
- **Bitte schliessen Sie die Tuer.** — Firm but polite instruction
- **Schliessen Sie bitte die Tuer.** — Neutral request
- **Schliessen Sie die Tuer, bitte.** — Afterthought; can sound impatient

## Konjunktiv II for Politeness

German uses Konjunktiv II (subjunctive mood) as a primary politeness mechanism. English uses modal stacking. The mapping is not 1:1:

- English stacks modals: "Would you possibly be able to..." (3 layers)
- German uses Konjunktiv II + particles: "Koennten Sie vielleicht..." (2 layers achieve the same effect)
- Over-translating English modal stacks into German produces unnatural verbosity.

## Domain Boundary

This skill handles speech acts, hedging, and politeness markers. It does NOT handle:
- **Idioms**: Even when an idiom functions as an indirect speech act (e.g., "break a leg" as encouragement), defer to `idiom-localization` for the idiomatic mapping. Only assess whether the CHOSEN idiom preserves the speech act force.
- **Register/formality classification**: That is `register-detection`'s job (pre-translation) and Frege's `formality-calibration` (post-translation).

If an expression is both idiomatic AND a speech act, `idiom-localization` owns the localization, and this skill validates that the localized result preserves pragmatic force.

## Decision Procedure

1. Identify the speech act type in the source.
2. Assess the politeness level (direct → indirect scale, 1-5).
3. Map to the German construction that achieves the same politeness level.
4. Verify that the Konjunktiv II / particle combination is natural, not a calque.
5. Check bitte positioning if present.

## Output Format

```yaml
speech_act: polite_request
source_indirectness: 4  # 1=direct, 5=very indirect
source_pattern: "Would you mind checking...?"
target: "Wuerden Sie es stoeren, nachzusehen...?"
target_indirectness: 4
pragmatic_match: true
konjunktiv_ii_used: true
bitte_position: null  # not applicable here
```
