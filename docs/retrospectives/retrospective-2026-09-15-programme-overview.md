# Retrospective — A gift now has an overview, and reviewers land on their own cases (2026-09-15)

## What Was Built

The Programme group had four rows and no answer to *"how is this gift doing?"*. It now opens with
**Overview** — the page a gift card lands on, open to every console role and shaped by role on the
server.

- **Endpoint** `GET /api/v1/admin/scholarship/programme-overview/?programme=<code>` over the pure
  module `programme_overview.py`. `SECTIONS_BY_ROLE` decides which keys are BUILT: a reviewer's
  payload has no `money` key to hide; finance's has no `funnel`. Fenced by `application_scope`,
  registered in the org-fence guard, module scanned.
- **One clock for the verdict SLA** — `review_sla.py` replaced three inline copies (nudge sweep,
  `services.py`, interview reminders) in the same commit, each with a bite test.
- **Page** `/admin/programme/overview`: funnel (all thirteen statuses), money strip byte-equal to
  the Payments footer, attention counts, six hand-drawn SVG charts on theme tokens, intake state;
  reviewer and QC see their own queue and pace; finance the money charts. Reviewers and QC land
  here after sign-in.
- **Docs**: role matrix column, five manual chapters, five FAQ answers, two decisions, TD-249 and
  TD-250. No migration.

## What Went Well

- **Role shaping on the server, pinned by `test_the_key_set_per_role_is_exact`.** The page renders
  only what arrives, so there is no client-side subset to get wrong.
- **Two reconciliation tests** call the neighbouring endpoints on one fixture: the money strip
  equals the Payments footer and `spent` equals the Spending total. The `Decimal('0.00')` seed
  that makes SQLite and Postgres agree is documented at the seed.
- **The S5 decision named its own revisit trigger** ("when a second chart appears, build the
  primitive") and it fired exactly as written. `Charts.tsx` is that primitive.
- **Two Opus agents in parallel** — one built the screen, one wrote the docs — against a plan with
  the payload shape fixed first. 11 bite-checks (7 backend, 4 web), each reddened one named test.
- **Merging `main` before the gates**, once corrected (see below), caught the debt-number
  collision and the org-fence list clash before anything was pushed.

## What Went Wrong

1. **Stitch saved no screen, for the third time.**
   - *What happened:* `generate_screen_from_text` timed out as usual and nothing appeared in the
     project after eight minutes of polling.
   - *Root cause:* known failure mode (memory note of 2026-07-21; the tenant-invoices retro of the
     same day). The rule was followed literally once more before falling back.
   - *System change:* already recorded that day by the sibling sprint — one Stitch attempt, then
     an Artifact mock-up is the design of record. The mock-up was approved and built to.

2. **My debt numbers collided with a parallel sprint's.**
   - *What happened:* I raised TD-247 and TD-248; the tenant-invoices sprint had taken both and
     reached `main` first.
   - *Root cause:* the same fault as the migration-number collision on 2026-09-11 — a sequence
     number allocated from the worktree's copy of the register instead of from `origin/main`.
   - *System change:* renumbered to TD-249 / TD-250 at merge time and every cross-reference
     updated; lesson recorded (one lesson covering migrations and TD numbers both).

3. **I started the gates before merging `main`, and had to kill and re-run them.**
   - *What happened:* the backend suite was fifteen minutes in when the merge changed
     `views_admin.py`, `urls.py` and the org-fence test underneath it.
   - *Root cause:* the plan's sequencing put "gates" before "merge origin/main in", and I
     followed it. A gate run on a tree that is about to change proves nothing about what ships.
   - *System change:* merge first, then gate, then push — written into the lesson and into the
     sprint's own `CLAUDE.md` step.

4. **The mock-up drew five funnel tiles the server does not send.**
   - *What happened:* the approved mock showed aggregates ("Awarded", "In review") that would
     have to be summed client-side from statuses the server sends individually.
   - *Root cause:* the mock-up was drawn before the payload contract was final, so it showed a
     reading of the data rather than the data.
   - *System change:* the frontend agent rendered the thirteen statuses the server sends rather
     than inventing sums, and said so. Next time the contract's own field list is the mock's
     source; anything aggregated on the mock must be a field the server returns.

## Design Decisions

Recorded in `docs/decisions.md` (2026-09-15): the donut becomes a shared primitive (closing S5's
revisit clause; a charting library refused again with a concrete reason — the jest harness has no
ESM transform and no `ResizeObserver`); finance sees aggregate spending on the Overview though not
the Spending page.

## Numbers

- 41 files, +4,610 / −64; no migration.
- **6666 pytest** (+49: 36 overview, 12 review-SLA, 1 workloads) · **2281 jest** (+64) · tsc 24
  baseline · lint 0 errors · `check-i18n` pass (86 leaf keys ×3) · `next build` exit 0 — all after
  merging the tenant-invoices sprint from `main`.
- Bite-checks: 11 injected, 11 caught.
- Deploy: `main` at `77b88408`; builds api `dafe2491` + web `e567f025` SUCCESS; serving
  `halatuju-api-01041-t8n` / `halatuju-web-00890-2xw`, digests matched; Overview 200, endpoint 401
  unauthenticated, no api ERROR logs after the deploy.
- No time estimate was given for this sprint, so there is no planned-versus-actual figure.
