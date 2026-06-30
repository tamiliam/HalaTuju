# Bursary signing — go-live playbook

The whole post-award signing flow ships **dark** behind `BURSARY_AGREEMENT_ENABLED` (default
OFF). This is the ordered checklist to turn it on. Nothing here is reversible-by-accident: the
flag is one env var, but the Phase-0 gates below are real-world prerequisites.

## Phase 0 — owner prerequisites (must clear before flipping)

1. **Lawyer-vet the agreement wording.** `bursary.py` carries a DRAFT template; the rendered
   document still shows a "DRAFT — pending legal review" banner. The lawyer signs off the
   clause text (the comprehension quiz copy in `awardComprehension.ts` must stay in lockstep
   with whatever the final clauses say).
2. **Finalise the Foundation entity + signatory.** Set on `halatuju-api`:
   `FOUNDATION_SIGNATORY_NAME`, `FOUNDATION_SIGNATORY_TITLE`, `FOUNDATION_SIGNATORY_NRIC`.
3. **Provision the signers** — see `bursary-signer-provisioning.md` (a super account for the
   Foundation officer; a partner account + org `contact_email` for each referring org).
4. **Tamil copy pass** — the en/ms strings added across S2–S6 are final-ish; the **ta** strings
   are first-drafts and want the owner's eye before a real Tamil-preferring family sees them.

## Phase 1 — migrate-first (prod DB, before any deploy)

Apply the additive migrations to prod **before** pushing code (deploys do NOT run `migrate`):

- `0083_award_comprehension_passed_at` — `comprehension_passed_at`
- `0084_guarantor_phone_verify` — `guarantor_phone`, `guarantor_phone_verified_at`
- `0085_bursary_reminder_stamps` — `witness_reminded_at`, `countersign_reminded_at`

All additive (nullable columns) → the live old code keeps working after they land. Apply via the
usual local-checkout-against-prod path (DB creds from `gcloud run services describe halatuju-api`).

## Phase 2 — local dry-run (no prod exposure)

Walk the entire chain locally with every external seam mocked — **no Twilio, no email, no PDF,
no storage, no data left behind**:

```bash
python manage.py bursary_e2e            # full chain, with a referring partner
python manage.py bursary_e2e --no-org   # graceful path: no partner -> Foundation direct
```

Both must print "Bursary E2E walk completed OK". Also run the suite:
`python -m pytest apps/scholarship/tests/test_bursary_agreement.py`.

## Phase 3 — deploy + scheduler

1. `git push` (api rebuilds). The signing flow is still dark at this point.
2. Create the Cloud Scheduler job for the SLA cron (mirrors the existing cron pattern):
   - **`bursary-signing-reminders`** — daily, e.g. `0 9 * * *` Asia/KL → the cron endpoint with
     the `X-Cron-Secret` header. Tune cadence via `BURSARY_SIGN_REMINDER_DAYS` (default 3).
3. (Optional) set `FOUNDATION_NOTIFY_EMAIL` to target the countersign nudges, and confirm
   `ADMIN_NOTIFY_EMAIL` is set as the fallback.

## Phase 4 — flip the flag

```bash
gcloud run services update halatuju-api --region asia-southeast1 \
  --project gen-lang-client-0871147736 --account tamiliam@gmail.com \
  --update-env-vars BURSARY_AGREEMENT_ENABLED=1
```

This also un-hides the cockpit bursary panel (now showing accurate TD-144 ticks). Re-dark with
`BURSARY_AGREEMENT_ENABLED=0` at any time — no data is lost.

## Phase 5 — invite students to sign

Awarding does not auto-email. Send the "ready to sign" follow-up deliberately, to an explicit
list of awarded application IDs:

```bash
gcloud run services update halatuju-api ... --update-env-vars SIGN_INVITE_APP_IDS=16,42
# then run the cron job:
gcloud run jobs execute ...  # or trigger 'send-sign-invitation-emails'
```

Each student lands in `/scholarship/application` → Action Centre → comprehension quiz →
parent-PIN → sign. (`AWARD_ACCEPTANCE_ENABLED` controls the "View my award" panel separately —
turning it on un-hides the panel for ALL funded students at once, so prefer the targeted email.)

## The flow, end to end (what go-live switches on)

1. Owner emails an awarded student "ready to sign" (`SIGN_INVITE_APP_IDS`).
2. Student opens the Action Centre → **comprehension quiz** (8 checkpoints) → signing form.
3. Student types their signature; parent/guardian enters an **SMS PIN** sent to their locked
   phone (the gate); both sign in-session.
4. Chain notifications fire: **partner witnesses** (if a referring org) → **Foundation
   countersigns** → agreement **executed** → app flips to **active**; the student is emailed.
5. Anyone stalled is re-nudged daily after `BURSARY_SIGN_REMINDER_DAYS`.
6. Only after full execution does the student reach the portal/onboarding.

## Known scope boundaries (deliberate)

- The **parent/guarantor has no email** on file (phone only), so the "executed" email is
  student-only; the parent's touchpoint is the SMS PIN. (An SMS to the parent is a later option.)
- Real disbursement / toyyibPay is a separate track (TD-075).
- The optional "pending signatures" filter on the applications list was not built (S5 note).
