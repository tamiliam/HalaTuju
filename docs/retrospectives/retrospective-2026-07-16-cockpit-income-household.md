# Retrospective — Cockpit income/household reconciliation + Pre-U institution tick (2026-07-16)

An owner live-review arc on the officer cockpit, driven entirely by real applicants (#66, #117,
#130, #132, #137). Six commits (`bfe3e000`, `2077937f`, `fb9647d6`, `8dbc55be`, `1da10538`,
`a32cd83d`), all display-or-soft, NO migration. Ran alongside a concurrent agent working the STR
salary-picture (their own retro); coordinated by holding my shared-file work until they closed.

## What Was Built

- **KM→Kolej Matrikulasi display + income document-verified-on-top + About-card tidy** (`bfe3e000`):
  a deterministic `expandMatricInstitution()` (display-only); household income now leads with the
  document-verified total + tick when confident, declared drops to a muted "Declared: RMx"; per-capita
  uses the documented income; call-language hidden, Email moved beside Phone.
- **Pre-U institution verified tick** (`2077937f` + fix `fb9647d6`): a new `institution_status` on the
  offer `pathway_check` compared against the SHOWN `pre_u_institution`; ticks only when a genuine
  offer's institution matches AND the offer isn't an overall pathway mismatch.
- **`confirm_pathway` updates the pre-U fields** (`8dbc55be`): on the student's "Yes, this is my
  pathway", `pre_u_institution` + `pre_u_track` are set from the confirmed offer (not just
  `chosen_programme`). Backfilled #117 & #14; flagged #43 (a pathway-type change, TD-161).
- **Income reconciliation covers all household earners + genuineness guard** (`1da10538`):
  `_income_earning_members` = salary-route ∪ anyone with a payslip/EPF; `_member_income_genuine`
  blocks a tick off a suspect/wrong-type doc.
- **Household-size confirmation query** (`a32cd83d`): a one-tap Check-2 confirm on an over-count; on
  confirm the cockpit shows the roster count + tick + muted "Declared: M" and per-capita uses it —
  non-mutating, no migration (confirmation = a student-resolved item).

## What Went Well

- **Every change was grounded in the real record first** (read-only Supabase MCP on #66/#117/#132/
  #137) before touching code — turned "is this a bug?" into a precise diagnosis each time (e.g. #132's
  tick was an SPM-slip match misattributed to STPM grades; #117's tick verified a different school than
  the one shown).
- **Reused existing seams, no new UI:** the household-size confirm rides the `pathway_confirm` one-tap
  card (`ONE_TAP_CONFIRM` set); the income document-on-top pattern was reused for size; the tick reuses
  `documentFacts`. No new component → no Stitch, no migration across the whole arc.
- **Concurrency handled cleanly:** with another agent editing `income_engine.py`/`check2_queries.py` in
  the same tree, I held all shared-file work until they committed, then built on their landed changes
  (their `_member_income_documented` sat right beside my reconciliation) with zero conflict.

## What Went Wrong

1. **The first Pre-U institution tick verified the wrong school.** *Symptom:* #117's tick sat on the
   displayed "SMK P Temenggong Ibrahim" while the offer was for "Kolej Tingkatan Enam Gombak". *Root
   cause:* `institution_status` compared the offer against `decl_inst` from `_declared_pathway`, which
   prefers a *confirmed* `chosen_programme` institution — so it diverged from the field being displayed.
   *Fix:* compare against `pre_u_institution` (the shown value) specifically, and suppress the tick on
   an overall pathway mismatch. Lesson added: attribute a verification badge to the exact value shown.

2. **The confirm flow only half-kept its promise.** *Symptom:* #117 confirmed its offer, but the record
   still showed the old school + a red stream clash. *Root cause:* `confirm_pathway` wrote only
   `chosen_programme` + the stamp, never the `pre_u_*` fields the cockpit actually displays for an
   institution pathway. *Fix:* update the pre-U fields on confirm + a backfill for the already-confirmed
   apps. Lesson: when a "we'll update your record" action writes a derived field, update EVERY field the
   UI reads for that fact, not just the canonical one.

3. **A test caught a fixture/prod data-shape divergence.** *Symptom:* the matric `confirm_pathway` test
   failed asserting "Kolej Matrikulasi Selangor" — the test DB seeds the college as "KM Selangor".
   *Root cause:* `catalogue_institution` returns the catalogue's own spelling, which differs between the
   test fixture and prod. *Fix:* assert the update happened + contains the state token, not an exact
   catalogue string. (Not a code bug — a reminder that catalogue-derived values are environment-specific.)

## Design Decisions

- **Household income/size verification is NON-MUTATING** — on a discrepancy we flag the documented/
  roster figure and (for a confirmed size) switch the *display*, never rewriting the student's declared
  value. The confirmation is recorded as a student-resolved ResolutionItem (no migration, no new field).
- **`institution_status` compares against the shown `pre_u_institution`, gated on the pathway not
  being a mismatch** — precise attribution over the combined `pathway` status.
- **Income reconciliation sums all documented earners (any route) with a genuineness guard** — the STR
  is the means-test, but a real payslip quantifies a member's pay regardless of route; a suspect doc
  can't confirm.

## Numbers

- +19 pytest across the arc (`test_confirm_pathway` ×3, `test_household_check` net +4, `test_household_
  size_confirm` ×5, `test_pathway_engine` +1, plus jest for `fieldVerification`/`scholarship`/
  `actionCentre`). Combined suite recorded at close (see MEMORY.md registry). NO migration.
- Deploys: web-only, api-only, and full-stack as each change dictated; every Cloud Build green. Local
  `next build` "Compiled successfully" throughout (the type-check-worker OOM after pytest is the
  documented 8 GB-box memory issue, not code — full `tsc` clean).
