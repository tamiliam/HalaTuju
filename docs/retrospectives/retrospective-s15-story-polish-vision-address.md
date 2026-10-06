# S15 Retrospective — Story tab polish + Vision MyKad address + single-instance docs (2026-05-29)

## What Was Built

Composite sprint after S14 ship. Six commits, four discrete pieces:

1. **Vision OCR — surface MyKad address** (`69cb1d0`, `0fb08a3`, `4baae5f`).
   Built on S13's NRIC+name OCR; now also extracts the registered home
   address from the IC photo. Soft signal only — no automated matcher; the
   admin verify-&-accept card surfaces `vision_address` alongside the
   student-entered `profile.address` for eyeball cross-check at interview
   time. Migration `scholarship/0018` adds the column; `_extract_address`
   in `vision.py` uses a postcode-anchor heuristic. **Three real-MyKad
   deploys** to converge on a clean output:
   - Pass 1: street + postcode/city only — missed `KEDAH` (state sits
     BELOW postcode in Vision's text order, my walk stopped AT the
     postcode line).
   - Pass 2: state picked up via a Malaysian-state allow-list, but
     `TAMAN SEMANGAT` got filtered out as "looks like the name" (my
     all-caps no-digit filter was too aggressive — many address parts
     have that shape: TAMAN/KAMPUNG/BANDAR/LORONG X).
   - Pass 3: replaced the name filter with a parentage-marker filter
     (BIN / BINTI / A/L / A/P / S/O / D/O / @) — addresses never have
     those tokens. Full 4-line address now extracts cleanly.
2. **Single-instance doc-type replace on re-upload** (`2ee7d5d`).
   `DocumentListCreateView.POST` now sweeps existing rows of the same
   single-instance doc type (DB row + Supabase Storage blob) before
   creating the new one. STR / salary_slip / EPF stay multi-instance for
   monthly slip stacking. Explicit `DELETE` also sweeps the Storage blob
   (previously leaking on every Remove click). UI label flips
   "Add more" → "Replace" for single-instance types. New `delete_objects`
   helper in `storage.py`. TD-062 logged for the historical orphan blobs
   from pre-fix Remove clicks.
3. **Post-shortlist vision doc** (`87404e1`).
   Direction-setting `docs/scholarship/post-shortlist-vision.md`: four
   user types (student done / admin needs role categories / sponsor + mentor
   to do), funnel through interview→sponsorship→in-programme, three-engine
   gap model (deterministic + Vision + Gemini), two-stage profile
   (draft → interview findings → final), standardisation under manpower
   scarcity as the north star, recommended phased build A→F. No code.
4. **Story tab polish on /application** (`53afbad`).
   Four UX/UX-data items: checkboxes → slide toggles (firstInFamily +
   Consent agreement) matching /apply; siblings boolean → numeric count
   ("How many of your siblings are also studying?") with migration
   `scholarship/0019` + profile_engine prompt fallback; placeholder ghost
   text + collapsible "Need ideas?" tips on all 6 open textareas; `*`
   asterisks on required fields (FieldLabel extracted from /apply to
   shared component) + dropped "(Optional)" labels everywhere.

## Numbers

- 17 files changed in the headline S15 commit; 6 commits across the
  sprint, totalling roughly 700 lines added / 100 removed.
- Backend tests: **1188 / 1188 pass** (+19 from 1169 at S14 close).
  Composition: 5 `_extract_address` (simple block, Alamat label, no
  postcode, empty, dedup) + 3 state-pickup (state below postcode, non-state
  rejected, W.P. prefix) + 2 taman regression + 3 docs single-instance
  (IC replace, multi-instance keeps, DELETE sweeps Storage) + 4 siblings
  count (PATCH writes, null clears, negative rejects, legacy boolean
  back-compat) + 2 profile_engine (count when set, boolean fallback).
- Frontend jest: **110 / 110 pass** (+4 from 106).
- i18n parity: **1310 × en/ms/ta** (+34 keys: 1 vision-address-* admin
  pair, 1 docs.replace, ~31 story-tab placeholder/tips).
- Next build: EXIT=0 each pass.
- Migrations applied to prod via Supabase MCP (migrate-first, TD-058
  workaround): `scholarship/0018_applicantdocument_vision_address` (1
  column), `scholarship/0019_scholarshipapplication_siblings_studying_count`
  (1 column). Both additive, 0 rows touched.
- Cohort-billable Vision OCR calls: ~3-4 this sprint (real MyKad
  re-uploads to test extraction), running total ~7-8 of 1000/month free.
- Deploys: 5 (3 vision-address tuning + 1 single-instance docs + 1 S15
  polish).

## What Went Well

- **Pure-helper testability paid off again.** `_extract_address` is a
  pure function over text — pytest fixtures cover synthetic OCR strings,
  no Vision API key needed in CI. The matcher tweaks (state allow-list,
  parentage-marker filter) each landed with a regression test against the
  exact failure mode the user reported. The tests document the heuristic
  decisions in executable form.
- **Migrate-first via Supabase MCP is now a smooth muscle memory.** Two
  additive migrations this sprint, both applied + `django_migrations` row
  recorded in a single transactional `execute_sql` before the code push.
  Zero migration-related friction.
- **The post-shortlist vision doc landed cleanly.** Captured a deep
  design conversation as a durable artefact in ~200 lines. Future
  sessions (and the user's future planning) have a single referenceable
  source instead of needing to re-discover the model. The plan-mode flow
  for S15 itself (Explore + Plan agents + plan file + ExitPlanMode) also
  worked — the Plan agent caught two factual errors in my brief (model
  name + back-compat scope) before any code was written.
- **The doc-replacement fix was a 30-min change with structural
  ripple.** Cleaned up an admin-confusing UX, an orphan-Storage bug, AND
  the "Add more" misleading label, all in one focused commit. The kind
  of high-leverage cleanup that's easy to defer but easy to do right
  when scoped together.

## What Went Wrong

1. **Vision address extraction took 3 deploys instead of 1.**
   - **Symptom:** I wrote pure-function tests against synthetic OCR text
     before deploying. Tests passed. User uploaded real MyKad → output
     was missing the state. Re-uploaded after fix #1 → output was
     missing TAMAN SEMANGAT. Third deploy got it right.
   - **Root cause:** My synthetic test fixtures didn't match the actual
     visual order Vision produces on a real MyKad layout. I'd assumed
     "address ends at the postcode line" (so the state below was outside
     my walk window), and "all-caps no-digit = name" (so the taman line
     would always be skipped). Both assumptions sounded reasonable in
     isolation; both were wrong against the real document.
   - **System change:** when shipping an OCR-derived heuristic, the
     verification protocol must include "user uploads one real document
     and we look at the output," not just unit tests. This is now
     captured as a lesson. The pattern is similar to S13's "ship-then-
     flip" for billable APIs — but with OCR, the trip-wire is heuristic
     quality, not cost. **Practical action for the next OCR heuristic:**
     before shipping, ask the user to send a representative real-document
     screenshot, dump the Vision text output for it, and validate the
     heuristic against THAT text — not against my imagined version.
2. **Tamil-pending queue is now 7 batches deep.**
   - **Symptom:** Every sprint that adds user-facing strings adds Tamil
     first-draft mirrors. The pending refine batch has grown to: S4 docs
     labels + S5a panel + /scholarship copy + 5 partner orgs +
     quiz.returnToApplication + S14 13 keys + S15 31 keys ≈ 60+ strings.
   - **Root cause:** No batching gate — drafts ship inline with each
     sprint, and the user has to context-switch into language work at
     unrelated times. The previous S14 retrospective flagged this; we
     didn't act on it.
   - **System change:** flag this loudly at every sprint close (already
     in the close summary) and offer to surface the batch as a single
     refine session before the next big sprint. I'll proactively surface
     the full English+Tamil side-by-side on demand so the user can
     review in one sitting.
3. **The plan-mode brief had a factual error the Plan agent caught.**
   - **Symptom:** My brief said `siblings_studying` lives on
     `StudentProfile`. It's actually on `ScholarshipApplication`. The
     Plan agent flagged it before any code was written.
   - **Root cause:** I'd internalised the field as a "profile-ish"
     concept (family attribute) without checking the model. The
     reconnaissance Explore agent confirmed the surrounding context but
     I didn't ask it to verify the model location.
   - **System change:** when scoping a model change in plan mode, the
     Explore agent's brief must explicitly include "confirm which model
     the field lives on" rather than relying on my mental model. Worth
     building this into the standard plan-mode brief template for any
     migration-class task.

## Design Decisions

See `docs/decisions.md` (new entries).

## Tamil-pending (carried, growing)

Now spans 7 batches; ~60+ strings total. Queued for a single refine
session when the user wants it:
- S4 documents tab labels
- S5a "What happens next" panel
- /scholarship overview copy refresh
- 5 new partner-org labels
- `quiz.returnToApplication`
- S14's 13 new keys (`profile.householdIncome*`, `householdSize*`,
  `scholarship.nextSteps.story.cardAddress.*`)
- S15's 31 new keys (Story tab placeholders + tips × 6 fields +
  siblings count label + 1 admin vision-address pair + 1 docs.replace)

Sprint close will offer the user a consolidated side-by-side view if
they want to do the refine pass before the next sprint lands.
