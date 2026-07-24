# Retrospective — Billing & usage v1 (Sprint 13a — usage meter + org-facing usage screen), 2026-07-25

Brief: `docs/plans/2026-07-25-billing-usage-v1-brief.md`; design source
`docs/plans/2026-07-24-billing-sources-investigation.md`. Executor: Opus 4.8. **Status: SHIPPED +
DEPLOYED 2026-07-25** — commits `be06153c`..`27562de0` (4 feature commits + a test-clock fix),
migration `0116` applied migrate-first with RLS, both Cloud Builds SUCCESS for `27562de`, smoke
green. **The meter is LIVE and recording; the org-facing usage screen stays flag-dark
(`BILLING_USAGE_ENABLED` unset/off) with a scheduled flag-on of 1 August 2026** (owner-approved,
so an org admin's first visible month is a complete one).

## The same-day arc: investigation → build

This sprint is unusual in how fast it moved from "should we build this" to "it's live": the
billing-sources investigation (`docs/plans/2026-07-24-billing-sources-investigation.md`) landed
2026-07-24, established that every billable call site is already org-resolvable at the existing
Rule-6 seams but that literally zero metering existed, and closed the roadmap's "Billing & usage"
gate the same day it opened. The owner triggered the build immediately rather than waiting for the
originally-scoped trigger (a second-tenant prospect) — Sprint 13a jumped the Phase-4 queue because
the *investigation* gate, not the *tenant* gate, was what had actually been blocking it. Brief,
build, and deploy all landed 2026-07-25, one calendar day after the gate closed.

## What shipped

**The meter — unconditional, no flag, live from this deploy.** New `UsageEvent` (table
`usage_events`, migration `0116`, additive; org FK `PartnerOrganisation` PROTECT null=platform-base
work, application FK SET_NULL, service/model/source/quantity/tokens, index (organisation,
created_at)). `apps/scholarship/usage.py` logs one best-effort row per billable provider call at the
sanctioned seams — Gemini (`vision._call_gemini_json`, `profile_engine._call_gemini_text`,
`contracts._gemini_generate`, `report_engine`), Cloud Vision OCR, OpenAI fallback, every `_send*`
email primitive, and Twilio WhatsApp — with per-path source tags threaded via a `usage_context`
contextvar. **Metering is genuinely unconditional**: it runs from deploy with no flag, and it is
fault-injected to prove a failing `UsageEvent.create` can never break the user-facing call it's
riding alongside. `BILLING_USAGE_ENABLED` (default OFF) gates only the read endpoint/UI.

**The screen — flag-dark, org-facing.** `GET /api/v1/admin/scholarship/billing/usage/?month=YYYY-MM`
(`AdminBillingUsageView`, 404-first while dark). org_admin sees ONLY its own organisation (fenced by
construction — no platform row, no other org can appear in that payload); super sees every
organisation plus a platform (NULL-org) reconciliation row. Plain allowlist dict, units + tokens
only, no prices in v1. A live Supabase document-storage snapshot rides alongside per org. Classified
in `test_org_fence.py` (dual-shape: exact-key snapshots for both audiences, plus a leak test proving
an org_admin payload can never carry another org or the platform row). FE `/admin/billing` — month
picker, per-org cards (+ platform section for super), stat tiles + a service breakdown table,
storage, and a non-metered free-services footnote (Google Workspace + Cloudflare Turnstile).
Administration hub Billing card goes live for super + org_admin when the flag is on (same probe
pattern as Requests); Finance stays "Coming soon". i18n `admin.billing.*` en/ms/ta (ms/ta
first-drafts) + namespace parity guard.

**Test-clock fix (`27562de0`).** Five payment-window owner-case tests were fixed the same day —
detail under What Went Wrong below.

Backend **4496 → 4523 pytest**, frontend **719 → 738 jest** (+1 known Node-26 local fail, TD-171,
held constant). Exactly one migration.

## The mid-sprint org-facing redesign

The brief scoped the usage screen as **super-only**. Per the standing lesson from the Requests
Sprint 15 process note ("present the UI artifact BEFORE the first flag-on ask"), the executor built
an artifact mock and presented it for owner review before wiring the flag live. The owner's
feedback on that artifact (v2) changed the audience: the screen became **org-facing** — an
org_admin should see their *own* organisation's usage, because that transparency is the natural
lead-in to future per-org invoicing (an org that can already see what it's using will not be
surprised by an invoice line derived from the same numbers). Super gained an additional, org_admin
never sees, **platform-only section** on top of the per-org view. This was implemented as part of
the same sprint, not deferred — the org fence, the dual-shape serializer snapshots, and the
org_admin/super split in the FE all reflect the redesigned scope, not the original super-only brief.
Two other refinements arrived the same way: a live document-storage snapshot (not originally
scoped, added because "usage" without storage told an incomplete cost story) and service labels
naming the actual providers (Gemini/Cloud Vision/Brevo/Twilio, with a greyed paused-SMS row) instead
of generic category names.

## What Went Well

- **Investigation-to-ship in one day** without skipping rails — migrate-first + RLS, full test
  gates, org-fence classification, and an artifact-first UI review all happened inside that window.
- **Metering-is-unconditional held up under fault injection.** The single scariest failure mode for
  a "log everything" feature — a logging bug taking down a real user action — was tested directly,
  not just asserted in prose.
- **The org fence generalised cleanly to a third payload shape.** Requests (Sprint 15) already
  proved the org-vs-platform allowlist-serializer pattern; billing reused it directly for a
  dual-audience (org_admin / super) endpoint without inventing a new mechanism.

## What Went Wrong

**1. Five payment-window tests carried literal near-future dates that expired on the calendar
(external to this sprint, but discovered and fixed within it).**
- **What happened:** on 2026-07-25, five tests from the 2026-07-22 payment-window sprint — written
  against owner-verified cases pinned to literal dates like `date(2026, 7, 26)` — went red. The
  dates were meaningful the day they were written ("a run dated in the near future") but the
  calendar caught up to them, turning "future" into "today or the past" and breaking the intended
  edge-case shape.
- **Why it happened:** the root misjudgement was writing a date-sensitive test against a literal
  calendar date instead of freezing the clock — a pattern the codebase already has a convention for
  elsewhere in the suite, just not applied consistently to these five.
- **What system change prevents recurrence:** fixed same-day with the existing localdate-freeze
  convention (`27562de0`) — no test *logic* changed, only the clock became explicit rather than
  ambient. A repo-wide lint/CI guard for unfrozen `date(202X, ...)` literals near date-sensitive call
  sites was **considered and declined** (TD-175) — this is the first occurrence, and the fix pattern
  already exists as convention; a bespoke guard is disproportionate machinery for one incident. If a
  second, unrelated instance appears, promote the TD entry from a note to an actual guard.

**2. Two reds visible in the test run were both external to this sprint's own code, and needed
explaining so they aren't mistaken for regressions.**
- **The five date-rot payments tests above** — external to billing (they belong to the 2026-07-22
  payment-window sprint), surfaced only because the calendar happened to turn over during this
  sprint's window. Explained and fixed in the same close, so the final state is 4523 green, not
  4523-with-an-asterisk.
- **The pre-existing `scholarship.test.ts` local Node-26 failure (TD-171).** Unrelated to billing,
  environment-only (a native `localStorage` global shadowing jsdom's on a very new local Node
  version; green on CI). Held constant through this sprint (719→738, +19, this one unchanged) —
  called out explicitly so "738 jest, 1 known fail" reads as intentional, not overlooked.

## Design Decisions

See `docs/decisions.md` ("Billing & usage v1", Sprint 13a, 2026-07-25) for the full log: metering
unconditional / flag gates UI only; org-facing usage transparency (org_admin sees own usage);
platform row super-only; storage as a live snapshot rather than a `usage_events` row; units-only v1
(no prices); the 1 August 2026 flag date.

## The GCP cost pass that landed alongside

Not part of the Sprint 13a build itself, but performed the same day and directly relevant to why
Billing & usage matters: July 2026 month-to-date GCP spend was **RM84** against a RM50 budget — a
story **inverted** from the March 2026 baseline (then: Gemini RM61.71 dominant, everything else
near-zero). Now: **Gemini ≈RM0** (free tier covers normal volume), **Cloud Run RM39** (a legitimate
new baseline — 2GiB api + campaign traffic + 13 crons), **Artifact Registry RM39** (accumulated
deploy images — waste, not usage), Scheduler RM5. This validates the platform-fee billing model the
investigation proposed (§4): infrastructure, not AI, is now the dominant real cost, which is exactly
the kind of cost a flat platform fee is meant to cover rather than per-unit metering. Two fixes
applied same day: an **Artifact Registry cleanup policy** (delete images >30 days, keep the most
recent 10 per package — the RM39 AR line is expected to collapse to ~RM3–5 within days, rollback
depth stays 10 deploys per service) and the **budget raised RM50 → RM80/month** (thresholds
unchanged at 50/90/100%). Detail in memory `gcp_cost_monitoring.md`.

## Numbers

- Backend: **4496 → 4523 pytest** (0 fail, 0 skip after the test-clock fix).
- Frontend: **719 → 738 jest** (+19; 1 known pre-existing Node-26 local fail, TD-171, unchanged).
- Migrations: **1** (`scholarship/0116`, additive, migrate-first with RLS).
- Deploys: 1 (api + web, both Cloud Builds SUCCESS for `27562de`).

## Carry

- **Flip `BILLING_USAGE_ENABLED=1` on 1 August 2026** (owner-approved date; `--update-env-vars`, not
  a deploy).
- ms/ta review of `admin.billing.*` first-drafts.
- TD-174 (email usage rows mostly org-NULL — v1-permitted, resolve when real per-org invoicing
  needs sender-level org threading).
- Second-tenant meeting week-of 28 Jul 2026 — the trigger to watch for Phases 3–4 (superadmin
  portal, per-org verification-fact selection, second-tenant rehearsal, the required off-boarding
  sprint before any real DPA).
