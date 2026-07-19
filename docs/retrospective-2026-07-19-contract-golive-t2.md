# Retrospective — Contract Go-Live Transition, Sprint T2 (Sources UI + witness dropdown + deploy)

**Date:** 2026-07-19 · **The transition's single api+web deploy** (`eff5996c`) · Both flags remain OFF
**Plan:** `docs/plans/2026-07-19-contract-golive-transition-plan.md`

## What Was Built

The FE half of the go-live transition, Stitch-approved before any page code:

1. **Sources page** (`admin/sources/page.tsx`) — a super/org_admin registry of referral orgs
   (name · contact person · email · phone · active-in-apply toggle · student count) with inline
   edit + add, reached from a new **Sources** IconCard in Administration → ORGANISATION. Reuses
   `PartnerOrganisation.phone`/`contact_person`/`contact_email` (T1's decision).
2. **Witness-organisation dropdown** on the cockpit for a **sourceless** student — un-gated by the
   agreement flag so it is usable during go-live prep (runbook step 2, before the flip).
3. **admin-api** `getSources`/`createSource`/`updateSource`/`assignWitness`; `AdminApplicationDetail`
   serializer exposes `referred_by_org` + `witness_org`.
4. **i18n** `admin.sources.*` + the Administration card, en/ms/ta (Tamil flagged first-draft) +
   guard test + `sources-api.test.ts` (8 jest tests).
5. **Docs** — go-live runbook finalised in the playbook; apply-form defer noted.
6. **Prod cutover** — migrations `courses/0065` (+ seed) and `scholarship/0104` applied migrate-first
   via the Supabase MCP; single deploy; both flags stay OFF.

## What Went Well

- **The concurrent-work hazard resolved itself cleanly.** The funding-bar agent had committed AND
  pushed their work to `origin/main`; every "dirty" file in my tree was byte-identical to
  `origin/main` (0-line diff), so integrating was a conflict-free `git merge origin/main` with zero
  overlap on my files — no data at risk, no coordination stall.
- **Stitch worked on the retry** after a first empty run; the design was approved before any page
  code, so no UI was coded blind.
- The data-driven `show_in_apply` seed activated the correct **7** referral orgs on prod (every org
  with a referring student) rather than a hardcoded list — see below.

## What Went Wrong

- **The plan's "6 live referral orgs" undercounted the real referral graph (it is 7).** Symptom: I
  expected 6 activated sources; the seed activated 7 (cumig/smc/pptm/ewrf/mhm/hss + **hyo**, 1
  student). Root cause: the plan's "6" was the 32-student LIVE-COHORT subset, but the seed (and the
  apply form) should include every org that has EVER referred a student. Not a bug — the T1 seed was
  deliberately data-driven precisely to avoid a hardcoded-list drift; the divergence is the
  data-driven design being MORE correct than the plan's prose. Recorded in the cutover-SQL doc.
- **A first Stitch generate produced nothing** (timed out with no screen after 3 min of polling).
  Root cause: Stitch flakiness (documented in memory `stitch_mcp_workflow`). Fix: a single fresh
  retry (not a blind retry within the timeout) succeeded. No systemic change — the memory note
  already covers it.
- **`admin-api.ts` already had an `adminMutate` helper** — my first draft added a duplicate
  (TS2393). Root cause: I wrote the helper before grepping the file for an existing one. Caught
  immediately by the scoped typecheck. Fix: removed mine, reused the existing (identical-shaped)
  helper. Lesson reinforced: grep the target file for an existing utility before adding one.

## Design Decisions

- **Witness dropdown offers `show_in_apply` (active) sources, not all `is_active` orgs** — filtering
  by `is_active` alone would surface the tenant org (BrightPath) itself as a witness candidate;
  `show_in_apply` is exactly the curated referral-source set. (Trivially changed if the owner wants
  a wider set.)
- **Witness card is un-gated by `bursary_agreement_enabled`** — the owner assigns witnesses during
  go-live prep, which precedes the flag flip (runbook step 2 before step 3).

## Numbers

- Files touched (mine, T2): 13 committed + the cutover-SQL doc + this retro.
- Tests: pytest **4093** (scholarship+courses) green; jest **605** (+12: my 8 + concurrent's
  poolCard) green; `next build` clean (`/admin/sources` route built); runserver smoke → all new
  endpoints 401 (auth-gated).
- Migrations: `courses/0065` (+ 7-org seed) + `scholarship/0104` applied migrate-first + verified.
- Deploys: **1** (api + web, `eff5996c`) — the transition's single deploy.

## Carry-forward

Tamil first-drafts (`emails.AWARD_OFFER_SIGN_BODIES` from T1 + `admin.sources.*` from T2) await the
owner's review before the flag flip — the sign email + the source UI copy are part of the legal
journey. The go-live runbook (both flags together, witness assignment, armed clock, lapse-cron
timing) is the owner's to execute; this sprint leaves both flags OFF.
