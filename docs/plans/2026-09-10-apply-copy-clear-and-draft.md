# A safer clear, and a draft from English — "How it's advertised", round two

**Owner-approved 2026-09-10.** Follow-up to the apply-copy sprint that shipped the day before.
Both halves were found by the owner using the live tab, not by a test.

---

## Why

### 1. The clear button was a live footgun

`admin.applyCopy.useDefault` — *"Use the standard wording"* — sat in the save bar beside Save. It:

- **deletes every language**, by sending `apply_copy: {}`;
- **appears whenever ENGLISH is saved** (`configured` reads `toPayload(saved).en`), regardless of
  which language tab the reader is on;
- **asked nothing** — one click, no confirmation, no undo.

So it stood live beside an **empty Malay form**, and pressing it there would take the English with
it. The owner's report was that the button "is misplaced… only appropriate when all the textboxes
are empty". Their instinct was right; the reasoning is sharper than the phrasing: the button's
timing is already the opposite of what they assumed (it hides on a truly empty gift), and the real
faults are that it is **named for its outcome rather than its action**, that it **reads as a peer
of Save**, and that its blast radius is **invisible from where it is pressed**.

### 2. Nobody can write Malay or Tamil from a blank box

The tab hands an organisation three language tabs and no help filling two of them. A gift that
writes English only is served its own English to Malay and Tamil readers (`for_wire`) — correct,
deliberate, and a downgrade from the platform default, which *is* translated. Sabah's copy will be
written by people who have English to hand and a deadline.

---

## What is being built

### Part 1 — the clear button says what it does, and asks

| Change | Why |
| --- | --- |
| Label → **"Clear all wording"** | Named for the ACTION. The old label describes the state afterwards, which is what made it read as an alternative way to submit. |
| A **confirm dialog** naming the languages | The blast radius is invisible from a Malay tab. `writtenLocales(saved)` lists what will be lost, by name. |
| The dialog uses the **critical** tone | It is a delete. The save bar's own house style stays untouched — the buttons stay on the right (owner ruling, 2026-09-07). |

**Not** made per-language. Dropping only Malay is already possible: empty the Malay boxes and
Save. Adding a second semantic would give one screen two ways to remove wording.

### Part 2 — "Draft from English"

A button on the Malay and Tamil tabs. It calls a new endpoint, fills the boxes, and **saves
nothing**.

- `POST admin/scholarship/programmes/<pk>/apply-copy/draft/ {locale}` → `{locale, block}`
- Model: **`gemini-2.5-flash`** (owner decision — a few hundred words a press, reviewed by a
  person before it can reach anybody).
- Reuses the `sponsor_terms._gemini_generate` shape exactly: one mockable seam, no downgrade
  fallback, metered through `usage_context`.

**Rules that must not be tidied:**

1. **It drafts; it never saves.** The wording only reaches a public page through the existing
   PATCH, pressed by a person. This is `decisions.md` 2026-05-31 (*the model extracts, the
   deterministic layer decides*) applied to copy.
2. **The source is the gift's own English**, never the platform default — drafting from the
   platform would translate ANOTHER gift's criteria into this gift's Malay, the exact
   right-language falsehood `applyCopy.ts` exists to prevent.
3. **The bullet count must survive.** Each bullet is one condition. A translation that merges two
   changes the advertised bar in one language only, and `normalise` would store it happily
   (all-or-nothing is per LANGUAGE, not per bullet).
4. **It reads the SAVED English**, so the button is asleep while English has unsaved edits —
   otherwise it would translate wording the reader can no longer see.
5. **Labelled "Draft", not "Translate."** The word carries the expectation the feature depends on.
6. Qualification names (SPM, STPM, PNGK, IPTA, B40, STR…) are kept verbatim in every language — a
   criterion the student cannot match against the certificate in their hand is worse than English.

---

## Lessons applied (from `docs/lessons.md`)

1. **Verify a rename by ABSENCE.** `useDefault` is RETIRED from all three message files, and the
   guard asks whether the old key is gone — not whether the new one is present.
2. **UI copy is a claim about the system.** The message files were grepped for anything still
   describing the old button.
3. **Gemini extracts, a human decides** (`decisions.md`, 2026-05-31) — the never-saves rule.
4. **Graceful when unconfigured** — a missing key is a readable refusal, not a 500.
5. **Restore a bite by writing the original bytes back**, with an anchor unique to the injection
   site. Never `git checkout --`.
6. **Scan for conflict markers before committing a merge** — the lesson written this morning,
   after the previous sprint's merge left them in `lessons.md`.

## Files

~18. **No migration.** Backend 5 (`apply_copy_draft.py`, `views_admin.py`, `urls.py`,
`settings/base.py`, `test_org_fence.py`) + 1 new test file; frontend 3 + 3 message files + 1 new
test file; docs.

## Execution

Single agent, in worktree `.worktrees/apply-copy-v2` on `feat/apply-copy-v2`. Both parts edit
`ApplyCopyTab.tsx`, so parallel agents would collide; another agent is pushing to `main`.
