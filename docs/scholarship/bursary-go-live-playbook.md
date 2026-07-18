# Bursary signing — go-live playbook

The whole post-award signing flow ships **dark** behind `BURSARY_AGREEMENT_ENABLED` (default
OFF). This is the ordered checklist to turn it on. Nothing here is reversible-by-accident: the
flag is one env var, but the Phase-0 gates below are real-world prerequisites.

> **Contract Module (2026-07-18) — the lawyer-vet gate IS the module's deployment gate.** The
> agreement TEXT (title, preamble, clauses, schedule, counterparty, quiz) is no longer hard-coded
> in `bursary.py` — those constants were removed in Sprint 5. It now lives in an org-owned,
> **versioned `ContractTemplate`** the org admin authors and deploys via
> `/admin/contracts` (Administration → Organisation → Contracts). Signing renders from the
> org's ACTIVE template; flag-on with no active template raises `no_active_template`, and a
> student must have passed the quiz for that exact version (`comprehension_stale` otherwise).
> So "lawyer-vet + finalise the signatory" (old Phase 0.1/0.2) is now done by **authoring the
> template, recording the vetting attestation, and deploying it** — see Phase 1b.

## Phase 0 — owner prerequisites (must clear before flipping)

1. **Lawyer-vet the agreement wording** — as the reviewed clause text of a **draft
   `ContractTemplate`** (the render-diff parity test proves the seeded BrightPath v1 reproduces
   today's clauses). Recording the attestation (who + date) and deploying the template IS the
   sign-off; the deployed document carries a "Vetted by {name}, {date}" footer, no DRAFT banner.
   The API-served comprehension quiz is generated from the template's own clauses (author-reviewed),
   so quiz↔contract lockstep is enforced at runtime (`comprehension_template`).
2. **Finalise the Foundation signatory as the template's counterparty.** Set
   `counterparty_name` / `counterparty_title` / `counterparty_nric` on the template in the UI
   (NRIC via the UI only — never seeded). (The legacy `FOUNDATION_SIGNATORY_*` settings are now
   only a fallback and unused once a template is active.)
3. **Provision the signers** — see `bursary-signer-provisioning.md` (a super account for the
   Foundation officer; a partner account + org `contact_email` for each referring org).
4. **Tamil copy pass** — the en/ms strings are final-ish; the **ta** strings (incl. the new
   `admin.contracts.*` + the quiz) are first-drafts and want the owner's eye first.

## Phase 1 — migrate-first (prod DB, before any deploy)

Apply the additive migrations to prod **before** pushing code (deploys do NOT run `migrate`).
The already-live signing schema:

- `0083_award_comprehension_passed_at` · `0084_guarantor_phone_verify` · `0085_bursary_reminder_stamps`

**Contract module (Sprint 5) — `0103_contract_module`** adds the three new tables
(`contract_templates`, `contract_clauses`, `contract_payment_schedule_rows`) + the FK columns on
`bursary_agreements` (`template_id`, `executed_pdf_emailed_at`, `drive_file_url`) and
`scholarship_applications` (`comprehension_template_id`). All additive → the live old code keeps
working after they land. Apply the DDL **+ enable RLS on the three new tables** in the same
transaction via the Supabase MCP, then record the `django_migrations` row (the established
migrate-first convention). Then deploy code (Phase 3).

## Phase 1b — author + deploy the contract template (the vetting gate)

After code deploy + migrate-first, and BEFORE flipping the flag:

1. `python manage.py seed_contract_template --org brightpath --template-version 2026-v1 --fixture
   apps/scholarship/fixtures/brightpath_contract_v1.json` — creates a **draft only** (no PII).
2. In `/admin/contracts/<id>`: the org admin (Suresh) fills the counterparty **NRIC**, reviews
   the clauses/quiz/schedule, records the **lawyer-vetting attestation** (who + date), and
   **Submits for deployment**. A **super** then **Deploys** (the previous active version, if
   any, auto-archives).
3. Verify a draft **payment run** matches the prior month, and that **Dec-2026 STPM rows grey
   out as `gap_month`** (the owner-confirmed exam-month skip — eyeball it before signing a run).
   `CONTRACTS_DRIVE_FOLDER` (default `04 Contracts`) must exist in the Workspace Drive for the
   executed-PDF filing to land.

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
   countersigns** → agreement **executed** → app flips to **active**. **Distribution** then runs
   (best-effort, idempotent): the **signed PDF is emailed** to the student (their "in effect"
   notice), the witness contact and the org admins, and **filed in Google Drive**
   (`CONTRACTS_DRIVE_FOLDER`, webViewLink stored on the agreement).
5. Anyone stalled is re-nudged daily after `BURSARY_SIGN_REMINDER_DAYS`; the same cron **retries
   any incomplete distribution** (a Drive/email hiccup) until both stamps are set.
6. Only after full execution does the student reach the portal/onboarding.

## Known scope boundaries (deliberate)

- The **parent/guarantor has no email** on file (phone only), so the "executed" email is
  student-only; the parent's touchpoint is the SMS PIN. (An SMS to the parent is a later option.)
- Real disbursement / toyyibPay is a separate track (TD-075).
- The optional "pending signatures" filter on the applications list was not built (S5 note).
