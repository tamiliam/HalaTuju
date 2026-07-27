# Retrospective — Sponsor module S1: one sponsor, whole (2026-07-27)

Plan `.claude/plans/snazzy-whistling-biscuit.md`; design of record
<https://claude.ai/code/artifact/9eec1f75-e38d-49d3-9df9-d4ad7a7b9fe3>.
Branch `feat/sponsor-detail` (worktree — another agent holds uncommitted work in the primary
checkout). Migration `0132`, additive. **Not deployed** (owner gates it, and `0131` must land
on prod first).

## What the investigation changed about the plan

The brief asked for four things. Reading the code first moved three of them:

1. **"Ability to add wallet credits" was already built.** The whole sign-off chain
   (`draft → admin_signed → [finance_checked] → confirmed`), the role gates, the typed-name
   match, three org-fenced endpoints — all shipped in P4b and live on prod since migration
   `0125`. What was missing was a frontend: `grep Credit src/lib/admin-api.ts` returned
   nothing. So the item is a screen, not a system, and it moved to S2 where it belongs. This
   is the `feedback_verify_shipped_before_rebuild` lesson paying for itself: had I taken the
   brief at face value I would have rebuilt a working control.
2. **Two items in "view sponsorship history" did not exist as data.** `last_seen_at` had no
   column, no field, no analogue anywhere (`grep last_login|last_seen|last_sign_in` → zero
   hits). Digest subscription and persons-invited *did* exist (`notify_frequency`,
   `SponsorReferral`), so only one of the four needed schema.
3. **A contradiction nobody had reported.** `sponsor_statement` lists `status='active'` gifts;
   prod has 0 active of 48 because award acceptance is switched off. So a sponsor's own
   statement read RM172,000 in / RM0 out beside a balance of RM73,000. Found by querying prod
   rather than reading the code — the code is correct in isolation and only wrong against the
   live flag state.

## What went well

- **The org-fence question was asked before the code was written.** A sponsor is
  platform-level; the money inside is not. Naming that split as its own fence category, and
  building `_SponsorScope` as one object rather than three filtered querysets, meant the three
  fenced reads cannot drift apart later. The two-tenant fixture is what makes the tests real —
  a single-org fixture would have passed with no fence at all.
- **Reusing `_credit_dict` and extracting `_wallet_programmes`** kept the money serialisation
  and the wallet-discovery query each in one place. Both were near-misses (see lessons).
- **The `_money()` bug was caught by a test asserting the exact string.** A numeric assertion
  would have passed and shipped two money formats side by side.

## What I got wrong

- **I hand-wrote a credits serialiser that already existed**, 3000 lines down the same file
  and a strict superset of mine. Caught only because a `Programme.name` AttributeError made me
  grep for how other code renders a programme name — which surfaced `_credit_dict` two lines
  away. Luck, not method. The method (grep for an existing serialiser of this model *before*
  writing one) is now a lesson.
- **My fault-injection test patched the wrong object** and failed for a reason that had nothing
  to do with the guard. Worse, it could have passed and proved nothing.
- **My test fixture reversed the maker and approver roles** on the second tenant's credit, and
  the service correctly refused it. The failure was mine, but it also demonstrates the role
  gate lives in the service rather than the endpoint — a shell caller gets the same refusal.
- **I planned a badge pair for S1 that would have opened an empty panel.** The Emails panel is
  S3. Shipping the badge first would have reproduced precisely the failure the partner-comms
  card was designed to avoid — a switch that looks like it works. Deferred to S3, stated in the
  CHANGELOG rather than silently dropped.

## Deliberately not done

- **The badges** (with S3, above).
- **Recording / signing / voiding a credit** — S2. The detail page draws the chain and says
  "recording and signing arrive next" rather than a disabled button, so nothing implies a
  capability the endpoint would refuse this sprint.
- **The sponsor-facing statement layout.** `total_committed` is on the payload; rendering it to
  sponsors is the deferred P4b-ii design pass. Adding a field is not the same as overturning a
  deferral, and the distinction is recorded in decisions.md.
- **Tax receipts.** Only meaningful with LHDN s44(6) status, which turns on the still-open
  Foundation entity question. Flagged in the plan, not scoped.

## Gates

- `pytest apps/scholarship` — **3598 passed**, 0 failed (+23 new in `test_sponsor_detail.py`).
- `pytest apps/courses/tests apps/reports/tests` — **1260 passed**; golden masters intact.
- `npx jest` — **802 passed**, 56 suites (+18 pure `sponsorDetail`, +4 list-column page tests).
- `next build` — compiled successfully; `/admin/sponsors/[id]` present.
- `makemigrations --check` — clean.

## At deploy — order matters

1. **`0131_billing_rates_and_hours` must be on prod first.** It is another agent's, sits on
   `main`, and prod is at `0130`. `0132` depends on it; applying mine first breaks the chain.
2. Apply **`0132`** migrate-first (one nullable timestamp on the existing `sponsors` table — no
   new table, so no RLS work).
3. Push (api + web rebuild).
4. Post-check: `last_seen_at` NULL on all 9 sponsors; the list's `given` totals RM172,000 for a
   super and RM172,000 for a BrightPath org_admin (one org today, so they agree — the fence is
   invisible until a second organisation exists, which is the point).

## Carry

- ms/ta first drafts for ~45 new `admin.sponsors.*` keys.
- S2: the credit interface against the live endpoints.
- S3: the eleven editable sponsor emails + the badge pair.
- S4: mandatory reject/suspend reason, per-sponsor email log, CSV export.
