---
name: unslop
description: "Use for /unslop: rewrite prose that reads machine-written (AI vocabulary, filler, hedging). Skip code, comments, quoted text, and product copy."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Unslop

Scan the text for the patterns below, then rewrite them. Preserve the meaning and the intended tone. Fix the sentence, not only the word: a replaced buzzword in the same empty sentence is still empty.

## Content and language

- **Superficial -ing phrases** ("highlighting", "ensuring", "showcasing"): delete, or give the real source.
- **Vague attributions** ("experts believe", "reports suggest"): name the source or delete.
- **AI vocabulary:** additionally, crucial, delve, enhance, foster, garner, interplay, intricate, landscape, pivotal, showcase, tapestry, testament, underscore, vibrant. Use the plain word.
- **Fancy "is":** "serves as", "stands as", "boasts", "features". Say "is" or "has".
- **"Not just X, but Y."** State the point.
- **Forced triples, synonym cycling, false ranges** ("from X to Y" with no scale). Use the natural number, pick one term and repeat it, and list topics directly.
- **Abstract metaphor nouns:** substrate, wedge, vector, locus, nexus, bedrock, scaffolding, paradigm, flywheel, north star, endgame, ratchet, "evacuate" for moving code. Use the concrete word.

## Style and filler

- **No em dashes.** Use a period or a comma. Avoid colons as mid-sentence connectors (a bold lead-in's colon is fine).
- **Bold, headings, emoji.** Bold only a lead-in that names an item and is followed by new detail; never "**Performance:** Performance improved". Sentence-case headings, no decorative emoji, straight quotes.
- **Chatbot and sycophantic phrases** ("I hope this helps", "Great question"): remove.
- **Filler:** "in order to" is "to", "due to the fact that" is "because", "it is important to note that" is nothing.
- **Hedging:** "could potentially be argued" is "may", or a plain claim.
- **Generic conclusions** ("the future looks bright"): state a fact or cut.

## Plain speech

- **Say what it does, not how it feels.** "SQL you can read" becomes "`.toSQL()` returns the exact string sent to the database". A sentence that fits any project's docs says nothing about this one, so cut it.
- **One idea per sentence.** Split a sentence the reader has to re-read.
- **Active voice.** Name the actor: "the loader parses the file".
- **Plain words, no adverbs.** "Use", not "utilize". "Significantly faster" becomes the measured delta.
- **No mannered prose.** Aphorisms, personified code ("the plan holds it"), figurative verbs, and rhetorical fragments become a literal statement.
- **Do not over-compress.** Keep articles and verbs and spell out arrows and abbreviations. "Parser rejects bad date → exit 2" becomes "The parser rejects a bad date, exits with code 2, and writes nothing."

**The test:** every sentence states a fact, an instruction, or a number the reader can use, and a sentence from it would be wrong or meaningless in another project's docs.

**Report:** what you rewrote and the patterns that recurred, and anything you left because cutting it would change the meaning.
