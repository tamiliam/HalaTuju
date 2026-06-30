# Bursary agreement — provisioning the signers (S5)

The Conditional Bursary Award Agreement has four parties. Two sign in-session on the
student's device (student + parent/guardian guarantor); the other two sign in the admin
cockpit. This note is the checklist for provisioning those two cockpit signers, plus the
Foundation signatory identity, before `BURSARY_AGREEMENT_ENABLED` is turned on.

> Everything here is a **go-live prerequisite** (Phase-0). Nothing below should be done on
> prod until the template wording is lawyer-vetted and the Foundation entity is finalised.

## 1. The Foundation signatory (the named counterparty)

The agreement names the **Foundation** as the counterparty (the donor is never named). Set
these env vars on `halatuju-api` (Cloud Run, `--update-env-vars`):

| Env var | Meaning | Current default |
|---|---|---|
| `FOUNDATION_SIGNATORY_NAME` | The person who countersigns for the Foundation | `Suresh` |
| `FOUNDATION_SIGNATORY_TITLE` | Their title on the agreement | "For and on behalf of the Foundation (interim signatory)" |
| `FOUNDATION_SIGNATORY_NRIC` | Optional NRIC printed on the agreement | (unset) |

These are read by `bursary.particulars_for()` and frozen onto each agreement at signing.

## 2. The Foundation officer account (who can countersign in the cockpit)

The **countersignature** is SUPER-ONLY (`AdminBursaryCountersignView` requires
`is_super_admin` / `role='super'`). So the Foundation officer (e.g. Suresh) needs a
**super** admin account:

1. As an existing super admin, go to **`/admin/invite`**, enter the officer's email,
   choose role **Super** (or POST `AdminInviteView` with `role='super'`).
2. They accept the Supabase invite → land on `/admin/login` → set a password (or Google).
3. They will then see the **Counter-sign (Foundation)** button on each awarded student's
   cockpit (`/admin/scholarship/<id>`).

Who gets the "please countersign" email nudge is controlled by `FOUNDATION_NOTIFY_EMAIL`
(comma-separated). If unset, the chain emails every active super admin, then falls back to
`ADMIN_NOTIFY_EMAIL`. Set `FOUNDATION_NOTIFY_EMAIL` to the officer's address to target only them.

## 3. The partner-organisation witness account (optional, non-blocking)

The **witness** is the referring partner organisation and is NON-BLOCKING (an attestation,
not a party — the Foundation can countersign and activate without it). A partner admin can
witness only for **their own org's** referred students (`AdminBursaryWitnessView` enforces
`admin.org == application.profile.referred_by_org`; a super may also witness).

To provision a partner witness:

1. Ensure the student's `profile.referred_by_org` is the correct `PartnerOrganisation`, and
   that org has a **`contact_email`** set (that address receives the "please witness" nudge).
2. Invite the partner contact via **`/admin/invite`** with role **Partner**, and ensure their
   `PartnerAdmin.org` is set to that organisation.
3. They sign in → see the **Witness** button on their referred students' cockpit.

If a student has **no referring org** (or it has no contact email), the chain skips the
witness and emails the Foundation directly — no one stalls.

## 4. Sanity check before flipping the flag

- [ ] Template wording lawyer-vetted (the rendered agreement still carries the DRAFT banner).
- [ ] `FOUNDATION_SIGNATORY_NAME/_TITLE/_NRIC` set to the real signatory.
- [ ] At least one **super** account exists for the Foundation officer.
- [ ] `FOUNDATION_NOTIFY_EMAIL` set (or super admins' emails are correct).
- [ ] For each referring org in play: `contact_email` set + a **partner** account invited.
- [ ] Walk the full chain locally first (see the S6 local E2E driver).

Then: migrate-first (`0084`), deploy, and flip `BURSARY_AGREEMENT_ENABLED=1`. TD-144 is
resolved — the cockpit four-party ticks now read from the real loaded agreement.
