# Retrospective — "How it's advertised", round two: one instruction block, one clear control, and a warning that stops crying wolf

**Date:** 2026-09-10 · **Commit:** `f36047e3` · **Worktree:** `.worktrees/apply-copy-v3`,
branch `feat/apply-copy-v3` · **No migration.** api + web.

Deployed and verified: both Cloud Builds SUCCESS on `f36047e` (api `b6ec0458`, web `4122413a`,
**waited on by build ID**); serving `halatuju-api-01018-65q` / `halatuju-web-00872-x76` (read from
`status.latestReadyRevisionName`); site 200; no api ERROR logs since. The served admin bundle was
read back in both directions — five strings present, five gone. RESULT: PASS.

Gates: pytest **6150** · jest **1988** · tsc **24** (TD-221 baseline) · lint **0** · i18n
**4974 × 3** · `next build` exit 0 · `makemigrations --check` clean. Two bite-checks, both bit.

---

## What prompted it

The owner opened the tab a few hours after round one deployed and reported five things, in their
words:

1. Place all instruction on top, not on every translation page — and fold four named sentences in.
2. "Clear all wording" need not appear on every page; once, at the top of the English page, because
   it clears all pages.
3. "Draft from English" ⇒ "Translate from English".
4. The platform's standard wording is mentioned but not shown. Show it.
5. Make the language more formal, clear but concise.

Four of the five are presentation. The fifth — showing the default — is the one that changes what
an administrator can actually decide, and it is why the tab is now usable without a second screen.

## The bug nobody reported

Reading their own screenshot to check the copy turned up a red ethnicity warning sitting over a
Tamil bullet that said, in substance, *willing to be contacted*. The warning claimed the criterion
selected on **religion**.

The mechanism: `sensitive_terms` matched its word list as bare substrings, and the Tamil word for
consent — சம்மதம் — ends with the Tamil word for religion, மதம். The same class of fault was live
in English the whole time (`race` inside `brace`), and had simply never appeared in the fixtures
anybody happened to write.

**`(?<!\w)` does not fix it**, which was the first thing tried and the thing worth writing down.
The character preceding the match in சம்மதம் is the pulli, U+0BCD — a combining mark, Unicode
category Mn, which Python does **not** count as `\w`. So the lookbehind passes and the false
positive stands. The Tamil block has to be named: `(?<![\w஀-௿])`.

Two consequences followed and are recorded as decisions:

- **The trade was chosen deliberately.** The word-start rule silently drops inflected Tamil forms
  (மதத்தின் no longer matches, because the term carries its own pulli). That is a real loss of
  recall and it is the right side to be wrong on for an **advisory that never refuses** — a reader
  who has learned to dismiss the banner ignores it on the day it is correct.
- **A word matching two terms is reported once.** After the boundary fix, "Indian" matched both
  `indian` and `india`; two findings over one word reads as two problems.

## What shipped, and why each piece is the shape it is

**Every standing instruction sits at the top, once.** Four sentences had accreted next to the
things they governed: one under the tab strip, one on every language tab, one under the criteria,
one beside the button. A reader met the same guidance three times and read it none.

The trap in obeying "move it all to the top" is that a **moved sentence and a dropped sentence look
identical in a diff**. The accuracy caution — terms easier than your Rules attract applications
that are declined automatically — could have vanished with the tidy-up and nothing would have
failed. Each retired key was checked into the new block by name, and an **absence guard** now fails
if any of them reappears. The failure mode is not the sentence being missing; it is the sentence
coming back somewhere else.

**"Saved." stayed in the save bar.** It answers an action rather than standing over the form, and
the owner's list is about standing guidance.

**Clear all wording appears once, on the English tab.** It clears every language. Offering it from
a Malay tab invites a reader to destroy work they cannot see — the same argument round one used to
put a confirm dialog on it, applied one layer out.

**"Translate from English".** The owner's word, reversing the previous day's deliberate choice of
"Draft". The expectation the old word carried moved rather than being dropped: the standing
instructions now say the button produces a machine translation to be read and corrected before
saving, and a test holds that sentence in all three languages. My own test asserting the control
says "draft, never translate" failed, which is exactly what it was for; it was updated with the
reversal written into it.

**The standard wording is shown, not merely named** — a collapsible panel that reads the message
files **by tab locale**, so an administrator working on the Malay tab sees what a Malay applicant
would read. `platformApplyCard(locale)` in `applyCopy.ts` is the one reader; it walks
`criteria1..n` until a key is missing rather than hard-coding four.

**Formal register throughout.**

## What went well

- The absence guard was written before the retirements, not after, so the consolidation could not
  quietly lose a sentence.
- The Tamil bug was found by reading the owner's screenshot as a Tamil reader rather than as a
  copy reviewer. It was not in scope and would not have surfaced from the ticket.
- The word-boundary fix is one mechanism for three languages and fixed an English case nobody had
  reported.

## What to watch

- **ms and ta are first drafts** for the round-two strings, `hintExact` and `hintTranslate`
  especially. The Tamil for the accuracy caution is the one to read first — it is the sentence the
  guard now protects.
- The instruction block is four sentences. The decision records that past four it needs structure
  rather than relocation.
- The narrowed detector's recall loss is written at the code and in `decisions.md`. If a real
  ethnicity-scoped criterion is ever observed passing unflagged, the fix is inflected stems in
  `SENSITIVE_TERMS` — no change to the matching rule.
