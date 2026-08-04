# Retrospective — the invitation emails, corrected off the live screen (2026-08-04)

The second half of the day. The four-letter sprint closed at `91316497`; everything here came from
the owner opening the result and reading it.

Commits `761d9641` (three corrections), `9e1eeb28` (docs), `b760c5a2` (two UI fixes).
**No migration.** Three deploys, each scoped by path filters to the services that changed.

`pytest` **5533** · `jest` **1419** · `next lint` **0 errors** · i18n **4525×3** · `tsc` clean ·
ledger reconciled: scholarship **146/146**, courses **69/69**, no gaps.

## What was built

**The read-only reviewer emails show the SHAPE.** `HT-0000` and a September date read as real
particulars. Each letter now renders twice through the *same builder the sender calls* — once with
`{ref}`, `{applicant_name}`, `{interview_time}`, once with a worked sample — and the screen shows
the shape with the example beside it. The anti-drift proof survives intact: `_fmt_myt` gained a
string passthrough for exactly this caller, and `test_the_preview_IS_the_email` now compares a real
send against the SAMPLE render.

**The caveats stopped repeating.** The locked-sign-in note appeared on three of four rows; the
source row said it was unsent twice. Both are stated once in the header now, worded to scope
themselves.

**The joining letters say something.** The reviewer's went from 180 to 807 characters: what
reviewing involves, where the Guide and FAQ are, and that handing a case back is normal. The
admin's says what the console holds and that their role decides what they may change.

**Three names, three levels.** HalaTuju is the platform, BrightPath the organisation, the
BrightPath Bursary the programme. All three now resolve from branding rather than literals.

**Two UI corrections.** Singular labels on "Invite as"; the pagination moved inside the table's
inset.

## What went well

- **The owner's naming correction landed as one edit because branding already had all three.**
  `org_short_name`, `programme_name` and `team_signoff` existed; nothing needed inventing, and a
  second tenant inherits its own names for free.
- **Rendering the letters and reading them end to end caught the sign-off** before it shipped — the
  habit from request #3 paying for itself a third time.
- **The golden diff was read rather than accepted.** Regenerating rewrites all 113 snapshots; the
  diff confirmed exactly two moved, both intended.

## What went wrong

**1. A deploy reported success while the change reached nobody.**

*Symptom:* the owner asked "Has this been deployed? I do not see any change." Both builds were
SUCCESS and the seed had run, and the sponsor letter still carried the old wording.

*Root cause:* the seed keeps an existing row by design — an org_admin may have edited it. That rule
is one-directional, so **a rewritten built-in never reaches a row that already exists**. Every
signal read as success: green build, `kept` in the log, no error anywhere. The blunt fix was
unavailable for the same reason the rule exists — six production rows carry real human edits.

*System change:* the reset is now scopeable (`--kind`, and `PARTNER_EMAIL_RESET_KINDS` for the cron
endpoint, which passes no arguments). The command docstring states the trap at the top, and the
settings entry carries the gcloud custom-delimiter syntax a comma-separated value needs. Six tests,
scoping bite-checked. **The wider habit: after a copy change, verify the CONTENT in production, not
that the job ran** — `kept` and `reset` both look like success.

**2. A build watcher that could never fire, twice.**

*Symptom:* I reported "still building" about builds that had finished, and the owner had to ask.

*Root cause:* the first watcher filtered on an 8-character SHA against Cloud Build's 7. Re-armed
after the next push, it then waited for two builds when the change was backend-only and just one
would ever run. Both times a predicate that cannot match is indistinguishable from slow work.

*System change:* sanity-check the query once before wrapping it in `until` — confirm it returns rows
today — and count the triggers the change will actually fire. Applied for the remaining two deploys,
both of which resolved correctly.

**3. A guard tried to stop a correct change, and nearly got silenced.**

*Symptom:* `test_no_email_points_at_a_partner_console` failed on the new admin letter.

*Root cause:* the guard excluded reviewer kinds by TABLE. Its own docstring had the principle right
— *"a surface that does not exist for the reader"* — but the implementation encoded the table, so
the staff invitations (whose readers do have a console) tripped it.

*System change:* the exclusion follows the reader now, and `invite_source` is deliberately left
INSIDE the guard with a test asserting it stays there — it describes a console that does not exist,
and its safety is that nothing sends it. **Same shape as the voice-guard gap found that morning:
a rule scoped by container rather than by what it protects.** Twice in one day is a pattern, and it
is now in `lessons.md`.

## Design decisions

Recorded in `docs/decisions.md`: the three-level naming; shape-plus-example rendering; a caveat
stated once. Plus the morning's: one letter per group via `KIND_ROLES`; the shared
`UNIVERSAL_BANNED`; the source letter written but unwired.

## Numbers

| | |
|---|---|
| pytest | 5533 |
| jest | 1419 |
| i18n leaves | 4525 × 3 |
| Migrations | none (0146 shipped in the morning half) |
| Deploys | 3 |
| Files touched | 24 across the arc |

## Carried

- **ms/ta for the new strings are my first drafts** — the six invitation labels, the two panel
  labels, and the singular button set. Owner's eye owed, especially நன்கொடையாளர் for "donor".
- **TD-215 raised**: the donor pitch is English-only while the peer letter is trilingual.
- **TD-213 resolved**, and its stated prohibition answered rather than ignored — see the entry.
- **TD-212's trigger has now fired once without being taken**, and that is recorded against it.
- Unchanged: quote on request #2, `paused_by`, the `source_partner` role name, the dormancy
  threshold, Divya Adinarayanan's phone number.
