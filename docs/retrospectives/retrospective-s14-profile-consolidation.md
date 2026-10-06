# S14 Retrospective — /profile schema consolidation + required address (2026-05-29)

## What Was Built

Closed four /profile gaps the user surfaced after live-testing, in a single push (`4aca9ae`, web `…00228-…`,
api `…00187-…`):

1. **/profile family card.** `family_income` range dropdown → open RM input bound to the shared
   `household_income` column. `siblings` count → `household_size` (same column /apply uses, "everyone in your
   home" semantics). One source of truth for finance + household composition across /apply and /profile.
2. **Phone consolidation.** Dead `phone` input dropped from /profile Contact & Location. The visible Contact
   Phone in Contact Details is the canonical `contact_phone` — already aliased to /apply.
3. **Contact Email auto-default.** `ProfileView.get` now falls back to the auth-user email when
   `profile.contact_email` is blank, and reports it as verified (Google/Supabase already verified that mailbox).
   Read-time fallback — DB row stays empty; a user-set contact email still wins and uses its real verification
   flag. The "Not set — tap to add" UX confusion (when the system was in fact already using the auth email for
   decision comms) is gone.
4. **/application Story tab — new "Where you live" sub-card.** Street + postcode + city inputs under Family.
   State stays read-only ("from your application"). `save_application_details` writes the address to the profile
   in the same Save call. `application_completeness` gains `address_done`; `complete` is now **6-part**
   (quiz + story + funding + docs + consent + address). Story tab tick requires both narrative + address.

**Backfills** (Supabase MCP, before push): 41 rows `family_income` range midpoints → `household_income`;
42 rows `household_size = siblings + 2`; phone-promotion no-op; contact_email read-time so no DB write needed.

**TD-061 logged**: drop the three replaced columns (`family_income`, `siblings`, `phone`) next session under
expand-contract.

## Numbers

- 14 files changed, +378 / −59
- Backend tests: 151/151 scholarship pytest pass (+3 new — `address_done`, address PATCH writes to profile,
  contact_email auto-default × 2)
- Frontend tests: 106/106 jest pass (+4 new — buildDetailsPayload address, applicationToDetailsForm address
  pre-fill + defaults)
- i18n parity: 1276 keys × en/ms/ta (was 1263 → +13 keys per locale)
- Next.js build: EXIT=0
- Deploys: 1 web + 1 api (well under budget — clean local checks)
- Backfill scope: 41 income + 42 household-size rows mutated; 0 errors

## What Went Well

- **Backfill-before-deploy worked cleanly.** Inspected the legacy-column distribution first (5 distinct
  `family_income` ranges, 49 populated rows), then ran the UPDATEs via MCP before pushing the new code that
  stops writing those columns. No moment where users with old data see a blank field.
- **Read-time fallback for contact_email beats a DB backfill.** 574 of 615 profiles have blank `contact_email`.
  Backfilling them would be a one-off mutation that locks decisions; doing it at read time in `ProfileView.get`
  is reversible, cheaper (no migration), and means a future change to "always require an explicit contact
  email" can be made by removing one fallback line.
- **The /apply ⇄ /profile sync verified itself.** Before coding, I traced every /profile field's read+write
  paths back to the DB column and the /apply form field. The income/siblings/phone duplications were obvious
  once the mapping was on paper. No guesswork during implementation.
- **Story tab Save remained one button.** Extending `ApplicationDetailsUpdateSerializer` with the three
  address fields and having `save_application_details` write them to the profile keeps the single-Save UX
  intact — no second updateProfile call from the frontend, no orphan partial-save state.

## What Went Wrong

1. **Trip-up in the original phone-consolidation framing.**
   - **Symptom:** my initial S14 plan said "drop the contact phone duplication" — which the user reasonably
     read as "drop the phone /apply writes". User pushed back: "But the student does fill up the phone number
     in /apply page."
   - **Root cause:** I labelled the dead column ambiguously. Said "drop phone" when the precise truth is "drop
     `phone` (dead column, /profile-only) while keeping `contact_phone` (canonical, /apply ⇄ /profile)".
   - **System change:** when proposing a column-or-field deletion, name the **exact column** + state both
     readers and writers. Same applies to UI fields with similar names. Captured as a lesson.

2. **i18n catch-up: 13 new keys per locale, Tamil drafts pile up unrefined.**
   - **Symptom:** This is the 4th sprint in a row that ships with Tamil first-drafts pending user review (S4
     docs labels, S5a panel, /scholarship copy, new partner orgs, `quiz.returnToApplication`, plus today's 13).
   - **Root cause:** No explicit batching gate. Each sprint ships its Tamil as "first-draft for refine" and
     the pending list grows; the user has to context-switch into language work at unrelated times.
   - **System change:** at sprint-close, summarise the current Tamil-pending list explicitly in the user
     message + offer to consolidate them for the user when they want a single review session. (Workflow change
     not necessary — handled in the user-facing summary.)

3. **`+2` household_size backfill is a rough heuristic for the legacy `siblings` data.**
   - **Symptom:** Migrated 42 rows assuming "2 parents + siblings" (so `household_size = siblings + 2`).
     Single-parent households, students living with grandparents, or those who didn't include themselves in
     `siblings` will have a number that's off by 1.
   - **Root cause:** The legacy `siblings` semantics were never tightly specified — there's no clean rule.
   - **System change:** the field is editable + non-blocking, so any student can fix it on /profile or
     /apply. Documented in the TD-061 entry. If we ever depend on `household_size` for an automated decision
     (currently used for per-capita income calc), spot-check the migrated rows first.

## Design Decisions

See `docs/decisions.md` (new entry).

## Tamil-pending (carried)

Now spans 6 batches; all queued for a single refine session when the user wants it:
- S4 documents tab labels
- S5a "What happens next" panel
- /scholarship overview copy refresh
- 5 new partner-org labels
- `quiz.returnToApplication`
- S14's 13 new keys (`profile.householdIncome*`, `householdSize*`, `scholarship.nextSteps.story.cardAddress.*`)
