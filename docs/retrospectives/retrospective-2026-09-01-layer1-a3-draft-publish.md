# Retrospective — Layer 1 A3: draft, publish, revert

**Date:** 2026-09-01
**Branch:** `feat/layer1-a3-draft-publish`
**Roadmap:** `docs/plans/2026-07-29-layer1-themes-roadmap.md`, arc A sprint 3 — **arc A is complete**
**Migration:** `courses/0072` — additive **plus one deliberate DROP** and a data step. Migrate-first.

---

## What was built

Before this, saving a colour changed it for every applicant **instantly**, and there was no undo —
the previous hex was simply gone.

| state | meaning |
|---|---|
| `draft` | being worked on. **Never served.** One per organisation. |
| `active` | what visitors see. One per organisation. |
| `archived` | what they used to see. **Kept** — that history *is* the undo. |

Four verbs on the screen: save a draft, discard it, publish it, revert.

---

## The one thing that must not go wrong

**A draft must never reach a visitor.**

There is exactly one filter — `OrganisationTheme.active_for` — and the serve path
(`scholarship.branding.Branding.theme`) calls it and nothing else. Widening it to "the
organisation's theme" would serve an unpublished experiment the moment somebody started typing.

Breaking that filter fails **13 tests**. It is the sprint's whole risk, held at one line.

---

## Design decisions worth keeping

**The shape is `SponsorTermsVersion`'s, on purpose.** That state machine has been in production for
a month: draft immutability, a publish that archives the previous active row inside one
transaction, `allowed=False` by default so a shell caller fails closed. Copying it beat inventing a
second one. What was dropped: the lawyer attestation, the .docx import, the quiz.

**The transitions live in `theme_versions.py`, not on the model.** A publish is two writes that must
happen together. Split across callers it is one deploy away from an organisation with two live
themes or none — and the bite-check proved it, because removing the archiving step tripped the
database's own partial unique index as well as four tests.

**Uniqueness is PARTIAL, per state.** One draft and one active per organisation; as many archived as
they like. A blanket "one row per organisation" would have left Revert with nothing to go back to.

**Reverting the FIRST colour lands on the platform stylesheet, and that is a real outcome.** It is
genuinely what they had before, and it is how a tenant gets all the way back to the default — so
there is no separate "reset" concept to keep in step with revert.

**Publish is asleep while there are unsaved edits.** Publishing ships the SAVED draft, so offering
it mid-edit would publish something other than the colour on screen. The tooltip says to save first.

---

## What went wrong

**1. A test named for a visitor was asking what an administrator sees.**

*Symptom.* `test_a_draft_never_reaches_a_visitor` failed with `KeyError: 'theme'`.

*Root cause.* It called the public branding endpoint using `self.client` — which was carrying the
org_admin's token. The NRIC gate refused the request, so the body was an error rather than a
payload. The test could not have answered its own question.

*Why it matters more than the fix.* This is the most important test in the sprint. Had the response
happened to be a valid payload, it would have passed while measuring the wrong thing entirely.

*Fix.* A fresh, anonymous client, with a comment saying why. The request now looks like a student's
browser, which is what the claim is about.

**2. Changing what a default MEANS re-pointed three tests that never changed.**

Three `test_branding_endpoint` tests construct `OrganisationTheme` rows directly and assert they are
served. After A3 a row with no status is a **draft**, so all three correctly stopped being served —
they failed, loudly, and were right to. They now say `status=STATUS_ACTIVE` with a note explaining
that a bare row is a draft.

*The general shape:* when a new field's default changes what an existing row MEANS, every direct
constructor in the suite is in the blast radius, whether or not it was edited.

**3. Backticks in a heredoc, twice more.**

Two `bash` heredocs died on backticks inside prose I was writing about code. It is already a lesson
in this repo and in the workspace CLAUDE.md, and I hit it anyway. The fix each time was to write the
file with the editor instead of the shell. Recorded again only because the recurrence is the point:
the pull is that the content is *about* code, so it is full of backticks.

**4. An invalid Python method name, with spaces and a comma in it.**

Caught on the next run, cost a minute, and is only worth noting because it happened while writing a
test whose name I was still composing in prose.

---

## What went well

- **Three bite-checks, all landing**, each injection verified before the suite ran:

  | Injection | Caught by |
  |---|---|
  | The serve seam stops filtering on status | **13 tests**, incl. the draft-never-served one |
  | `publish` defaults to `allowed=True` (fails open) | the shell-caller test |
  | `publish` stops archiving the previous version | 4 tests **and the database constraint** |

- **The migration's data step was written for a case that does not exist on production.** A row that
  existed before A3 *was* the live theme, so it becomes `active` rather than silently un-publishing
  a tenant. Production has zero rows — checked, not assumed — so it is a no-op there. It is in
  because a migration should express intent, not rely on being lucky.
- **The screen keeps live and draft apart in the copy, not just the code.** "Draft saved. Applicants
  still see the published colour." A bare "Saved" would have read exactly like the old behaviour,
  which *did* change what everyone saw.

---

## Numbers

| Gate | Before | After |
|---|---|---|
| pytest | 5738 | **5757** |
| jest | 1573 | **1583** |
| `tsc --noEmit` | 24 | **24** (baseline, TD-221) |
| `next lint` | 0 errors | **0 errors** |
| i18n parity | 4629 × 3 | **4636 × 3** (ms/ta first drafts) |
| `next build` | clean | clean |

This branch also carries **A2's held palette fix** (`9313025c`), parked rather than deployed a third
time for A2.

---

## At deploy

1. **MIGRATE-FIRST.** Apply `courses/0072` on production before the push — hand-written Postgres DDL
   in the migration's docstring, including the DROP of A1's `organisation_themes_organisation_id_key`
   and the two partial unique indexes. Record the `django_migrations` row.
2. Confirm the Security Advisor is still clean (no new table, so nothing new to secure).
3. Push (api + web).

**Nothing a visitor sees changes** — no organisation has a theme, so there is nothing to draft or
publish yet. The change is to what the Colours tab offers an `org_admin`. The palette fix riding
along is the only visible pixel, and it is on that same tab.

Post-check: as the BrightPath `org_admin`, open Programme → Colours and confirm the banner reads
"applicants are seeing the default colours", and that **Publish** and **Revert** are both asleep.

---

## Arc A is complete

| | |
|---|---|
| **A1** | a theme belongs to an organisation — stored, served, applied |
| **A2** | the picker, and a gate that refuses an unreadable colour |
| **A3** | draft, publish, revert |

**A4 (the full palette) stays deferred**, with its written trigger unchanged.

---

## Next

**F6 — the public course guide.** 36 files, plus ~78 colour literals returned as class strings from
`lib/` (`courseBadges.ts` 32, `applicationStatus.ts` 22, `requestStatus.ts` 14, `paymentStatus.ts`
6) — a codemod over `.tsx` never sees those, and they are exactly the status tones the vocabulary
should own.

**Then F7 — but it is blocked by two things**, both recorded with numbers: TD-222 (the dark ramp
cannot carry white button text) and the missing `AdminApplicationDetail` sandbox fixture.
