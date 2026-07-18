# Contract Go-Live Transition — Implementation Plan

**Date:** 2026-07-19 · **Status:** Owner-approved · **Implementer:** Opus 4.8
**Context:** The Contract Module is deployed and inert (draft template on prod, both flags OFF).
This plan manages the switch from today's "grandfather arrangement" (awards administrative,
acceptance panel embargoed, students paid at `awarded`) to **contract mode** (accept → quiz →
sign → active → Vircle → first payment → maintenance), covering comms rewiring, the 31-student
grandfather cohort, offer-lapse redesign, and the new Sources module. Prior plan:
`2026-07-18-contract-module-plan.md`.

## Verified facts this plan stands on (prod, 2026-07-19)

- All **32 live sponsorships sit at `offered`** — no student has ever accepted in-app
  (`AWARD_ACCEPTANCE_ENABLED` OFF since 2026-06-29; env-var only, no deploy to flip).
- With `BURSARY_AGREEMENT_ENABLED` on, the accept flow already chains review → comprehension
  quiz → in-session signing (guardian co-sign incl. name/NRIC/relationship). The front door for
  contract mode exists behind the embargo.
- The payments engine already excludes unsigned students when the agreement flag is on
  (`agreement_unsigned`, payments.py D4-7) — the hard gate is built.
- `sponsorship.lapse_expired_offers()` is unit-tested but **unscheduled**; every open offer's
  14-day `accept_deadline` is long expired. If scheduled as-is it would lapse all 32 awards.
  (Remove/replace the tech-debt item proposing to wire it unchanged.)
- Sources: 20/32 students carry `referred_by_org` (SMC 9, CUMIG 4, MHM 2, EWRF 2, PPT6M 2,
  HSS 1); 12 have none. `PartnerOrganisation` has `contact_person`/`contact_email` **and an
  existing `phone` field (models.py:418; the plan's original "no phone field" claim was wrong —
  T1 correctly REUSED `phone` rather than adding a duplicate `contact_phone`)**. No UI edits
  organisation records apart from AdminProfileView's own-org phone.

## Owner decisions (locked, 2026-07-19)

1. **Option A gate**: unsigned = unpayable stays hard; the flip is TIMED right after a monthly
   run completes, invites go out the same day, chase via the run screen's greyed reasons.
2. **Both flags flip together** (`AWARD_ACCEPTANCE_ENABLED` + `BURSARY_AGREEMENT_ENABLED`),
   never separately. Grandfathered students go through the same accept → quiz → sign door as
   future students (this back-fills their acceptance + consent records).
3. **Offer lapse redesigned, tied to the contract**: the clock ARMS when the sign-invitation
   email is sent; it is FULFILLED when the guarantor co-signs (the agreement `binds`). The old
   offered_at+14d semantics are dead. An app with released disbursements can NEVER auto-lapse —
   it is flagged for admin review instead.
4. **Sourceless students**: the org admin assigns a witness organisation from a dropdown
   (private arrangements made outside the portal). Future apply forms (currently closed) will
   draw their source list from the Sources module — active organisations shown, plus
   social-media/other chips for unaffiliated students.

## Sprint T1 — Backend: comms, lapse rework, state flips, witness/source model (~20 files)

1. **Award email, flag-ON variant** (`emails.py` + `sponsorship.release_award_offer_emails`):
   when `BURSARY_AGREEMENT_ENABLED`, the good-news email carries "review and sign your
   agreement" (link to `/scholarship/award`) and NO Vircle content; `raise_setup_task` is NOT
   called on this path. Flag-OFF behaviour byte-identical (regression-tested).
2. **Vircle invite at execution**: where the agreement fully executes (`_maybe_activate` /
   countersign — same hook as `distribute_executed_agreement`), automatically send the Vircle
   install email + `raise_setup_task`, **skipping** any student with a resolved Vircle task or
   non-blank `vircle_id` (the grandfather skip). Idempotent; best-effort.
3. **Maintenance flip**: in `payments.complete`, a released item for an application at
   `'active'` flips it to `'maintenance'` (first payment only; never from `'awarded'`;
   mirrors `disbursement._flip_to_maintenance` semantics).
4. **Lapse rework** (`sponsorship.py` + `bursary.py`): new semantics per owner decision 3 —
   `accept_deadline` is re-armed (now + `SIGN_ACCEPT_DEADLINE_DAYS`, default 30) when the
   sign-invitation email for that application is actually sent (`send_sign_invitation_emails`);
   fulfilled (deadline cleared) when the agreement `binds`. `lapse_expired_offers` rewritten:
   only lapses offers whose ARMED deadline passed; **refuses** (flags, logs, admin-visible
   list) any application with released disbursements. Update `docs/technical-debt.md` (c) —
   the cron may be scheduled only AFTER this lands.
5. **Witness assignment + Sources model** (`courses` migration): `PartnerOrganisation` gains
   only `show_in_apply` (active-source flag, default False; seed the 6 live referral orgs
   True) — phone REUSES the existing `phone` field (see Verified facts; T2 FE reads/writes
   `phone`). `ScholarshipApplication` gains `witness_org` override FK (null =
   derive from `referred_by_org` as today); `bursary` witness resolution reads override →
   referral → none (straight to countersign). Admin endpoints: Sources CRUD
   (list+counts / create / PATCH contacts+active) + per-application witness assignment PATCH —
   `_AdminBase`-fenced, super/org_admin.
6. Tests throughout: flag-matrix regression (OFF path unchanged), execution-Vircle skip
   matrix, maintenance flip, lapse guard (paid app never lapses), armed-deadline lifecycle,
   witness resolution order.

*Accept:* full pytest green; a simulated grandfather student (offered + paid + Vircle-confirmed)
walks accept → quiz → sign → countersign → `active`, receives NO Vircle email, and flips
`maintenance` on the next completed run; a simulated new student gets the sign-flavoured award
email, Vircle invite only at execution; an armed-then-expired unpaid offer lapses, a paid one
is flagged instead.

## Sprint T2 — Sources UI + witness dropdown + runbook + deploy (~18 files)

1. **Stitch first**: one screen — Sources list/edit (name, contact person, email, phone,
   active-in-apply toggle, student count). Owner approves before page code. The witness
   dropdown is a small addition to the existing admin application page (no redesign; no
   separate Stitch screen).
2. **FE**: "Sources" card in Administration → ORGANISATION grid → `admin/sources/page.tsx`
   (list + inline edit + add); witness-org dropdown (active sources) on the admin application
   page for apps with no source; `admin-api.ts` fns; i18n `admin.sources.*` en/ms/ta.
3. **Docs**: go-live runbook update (below) + CHANGELOG + retrospective; note in the apply-form
   docs that the next intake's form must draw sources from this module (active orgs + social
   chips) — build deferred until the form reopens.
4. **Single deploy** (api+web; migrate-first via Supabase MCP for the T1 migration), then
   sprint-close. Flags remain OFF — the flip is the owner's runbook, not this sprint.

*Accept:* jest + build green; browser walkthrough — edit a source's contact, add phone, toggle
active, assign a witness to a sourceless student; org-fence tests on all new endpoints.

## Go-live runbook (owner-executed, after T2 deploys)

1. Complete a monthly payment run (both sign-offs) — the clock starts the day after.
2. Assign witness orgs to the sourceless students (dropdown) — or leave for Foundation-direct.
3. Flip **both** flags together on `halatuju-api` (env vars only):
   `AWARD_ACCEPTANCE_ENABLED=1` + `BURSARY_AGREEMENT_ENABLED=1` (Phase-0 lawyer/template gates
   per the playbook must already be satisfied — template deployed active in the module).
4. Send sign invitations (`SIGN_INVITE_APP_IDS`, batched as desired) — this arms each
   student's 30-day clock.
5. Chase via the next draft run's greyed `agreement_unsigned` list; signing-reminder cron
   nudges automatically.
6. Next monthly run: signed students pay normally (and flip to `maintenance`); unsigned are
   visibly excluded — the Option-A pressure. Only after the cohort is through consider
   scheduling the (reworked) lapse cron.

## Out of scope / future

Apply-form source integration (form closed; contract noted in T2 docs) · scheduling the lapse
cron (owner decision after the cohort signs) · multi-tenant fencing of shared source rows
(single tenant today) · `minor_only` / `witness_required` policies (unchanged from module plan).
