# Retrospective — a safer clear, and a draft from English (2026-09-10)

Plan: `docs/plans/2026-09-10-apply-copy-clear-and-draft.md`. Worktree `.worktrees/apply-copy-v2`,
branch `feat/apply-copy-v2`, base `origin/main` at `4c6c15e2`. **No migration.** api + web.

Gates: pytest **6144** · jest **1971** · tsc **24** (TD-221 baseline) · lint **0 Errors** ·
i18n **4972 × 3** · `next build` exit 0 · `makemigrations --check` clean. **Three bite-checks, all
bit**, each injection verified as landed before the run and each restored by writing the original
bytes back.

---

## The finding that shaped the sprint

**The owner's report was right and their reasoning was inverted, and both halves matter.**

They said the clear button "is misplaced… only appropriate when all the textboxes are empty".
Reading the code, its timing is already the opposite of that: it appears only when English is
SAVED, and hides on a gift that has written nothing — so on a truly empty gift it is not there at
all, which is what their very first screenshot showed.

But the instinct was pointing at a real defect that better phrasing would have missed. The button:

- deletes **every language**;
- appears based on **English**, on whichever language tab you are standing on;
- asked **nothing** before doing it.

So the dangerous case is not the empty gift. It is the reader on an **empty Malay tab**, looking at
a form with nothing in it, pressing a button that reads like a formatting preference, and losing
the English they wrote yesterday. **A control's blast radius has to be legible from where it is
pressed** — and this one's was legible only from a tab it wasn't on.

The general lesson: when somebody reports that a control feels wrong, the report's *conclusion* may
be wrong while the *discomfort* is data. Read the code for what the control actually does before
either agreeing or correcting; here, correcting the timing claim without looking would have closed
a live footgun as "working as designed".

## The second half: what a machine may and may not do to public copy

The owner asked for a translate button. What shipped is a **Draft from English** button, and the
difference is the whole design:

- It **fills the boxes and saves nothing**. The wording reaches a public page only through the
  existing PATCH, pressed by a person. That is `decisions.md` 2026-05-31 — *the model extracts, the
  deterministic layer decides* — applied to copy rather than to documents.
- It is **labelled "Draft"**, because the word is what sets the reader's expectation that they must
  read it. "Translate" implies a finished thing.
- It drafts from **this gift's own English**, never the platform default. Drafting from the
  platform would translate ANOTHER gift's criteria into this gift's Malay — a right-language
  falsehood, which is the precise failure `applyCopy.ts` was written to prevent one sprint ago.

### The bullet count is a correctness rule, not tidiness

Each bullet is one condition an applicant is judged against. A translation that folds two into one
is a **lower advertised bar in one language only** — and `apply_copy.normalise` would store it
without complaint, because all-or-nothing is per LANGUAGE, not per bullet. So the count is asserted
against the English and a mismatch is refused.

This is the shape worth carrying: when a machine rewrites a structured thing, ask which of its
STRUCTURAL properties the downstream validator does not check, and check those yourself.

### Refusing a too-long draft rather than offering it

A drafted line over the stored cap would fill a box the Save then refuses, leaving the reader to
guess which box is at fault. Better to refuse with a code that says so. Malay and Tamil run longer
than English, so this is a real case rather than a theoretical one.

## What was found on the way in

**Merge-conflict markers had been committed into `docs/lessons.md`** — by my own merge the previous
evening. Both sides' content was present; only the `<<<<<<<` / `=======` / `>>>>>>>` lines were
left. Nothing failed: markdown does not parse, no test reads that file, and `git status` was clean
because the markers were *in the commit*.

The merge that produced them resolved three JSON message files with a script that parsed them
properly, and resolved the markdown by eye. **The file resolved by eye is the one that broke**, and
it is the file read at the start of every sprint. The fix is one line in the merge checklist: after
resolving any merge, grep the whole tree for conflict markers before committing. Fixed and pushed
separately (`0835b6b9`) before this sprint began.

## Bite-checks

| Injection | Expected | Result |
| --- | --- | --- |
| `if len(bullets) != expected` → `if False` | the merged-bullet + extra-bullet tests fail | 2 failed ✔ |
| the draft endpoint writes `apply_copy` and saves | `test_a_draft_NEVER_writes_to_the_gift` fails | 1 failed ✔ |
| `englishUnsaved` compares the WHOLE payload | "not blocked by a Malay edit" fails | 1 failed ✔ |

Each injection was grepped for before the run — a fault that never landed produces a green suite
and a false sense of coverage.

## Honest gaps

- **ms and ta are my first drafts** for the 23 new admin strings, the Tamil especially. The owner
  is the Tamil authority and has not read them.
- **The prompt's Tamil rules are a deliberate subset** of the project's 320-line style guide — the
  joining and sandhi rules a machine gets wrong on administrative prose. Whether that subset is the
  right one is an empirical question nobody can answer until real drafts are read.
- **Not click-tested in a browser.** TD-182 still breaks admin Google sign-in on localhost. The
  owner's post-check is the first real press of either button.
- **No live model call has been made.** Every test mocks `_gemini_generate`, deliberately — but that
  means the prompt has never met the model. The first real press is also the first evidence that
  the reply parses.
