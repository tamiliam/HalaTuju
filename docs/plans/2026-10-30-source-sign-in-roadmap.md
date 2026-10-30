# Source sign-in ("Source Partner console") — HalaTuju roadmap

## Context

Sources (bursary referral organisations, `referral_sources` table) have never had a login. The
Invitations page shows a disabled **Source** tab ("Sign-in for source partners is coming soon").
Today a source only gets emails, and only a super can record a contract witness for them.

Owner wants sources invited and signed in **like reviewers**, but with a small, mostly view-only
set of rights:
1. Invitation replaces Add source; the source edits its own details.
2. Each source user has a profile page.
3. They land on the Programme pages and see only the gifts they belong to.
4. Overview / Applications / Scholars show **only students whose application names them**.
5. They see basic details + profile only — nothing that could compromise review.
6. They witness the bursary contract from inside the platform.

Hard rule from the owner: **no conflict** with what exists. The conflicts found are listed below
and each one has a fix in a sprint.

## Conflicts found and how each is closed

| # | Conflict | Fix (sprint) |
|---|----------|--------------|
| C1 | No `source_partner` role; web `effectiveRole` maps an unknown role to **reviewer** | Add role on both sides in one change; drift test (S1) |
| C2 | `PartnerAdmin.org` is the platform *referral partner* link; sources now live in `ReferralSource` | New FK `PartnerAdmin.source` → `ReferralSource`; never reuse `org` (S1) |
| C3 | Staff lists read `PartnerAdmin` rows: Team roster, reviewer picker, review nudges, payment-chain and Foundation notify lists, permission editor | Audit every `PartnerAdmin.objects` query; exclude `source_partner` where it means staff; one regression test that plants a source user and checks every list (S1) |
| C4 | `invitations.accept_for_admin` closes `audience='staff'` only; `purge_expired` scrubs every non-staff invite after 60 days | Treat `source_partner` like staff in both (S2) |
| C5 | `Invitation.organisation` points at the tenant, not the source | New FK `Invitation.referral_source` (S2) |
| C6 | Add source / Edit source on the Sources page would fight the source's own edits | Add moves into the Source invite form; Edit **locks once the source has signed in** (owner ruling 2026-10-30; server 409 `managed_by_source`); Active toggle stays with the organisation (S2) |
| C7 | One email can only hold one staff row (CUMIG is referral partner AND source) | Invite refuses an email that already has any staff row (409 `already_staff`) (S2) |
| C8 | Owner ruling + tests: "no email may link to a partner console"; `test_NOTHING_SENDS_IT`; `invite_source` kept out of `CONSOLE_AUDIENCE_KINDS` | Revise the ruling in `docs/decisions.md` for invite + witness emails only; flip those tests on purpose in the same change (S2, S4) |
| C9 | `set-password` page hand-rolls its redirect (temp-password invitees) | Use `adminLanding` (S2) |
| C10 | Scope switcher (`AdminScopeListView`) gives non-supers every gift of their org | Source branch: only gifts that list the source or hold its students' applications (S1) |
| C11 | Existing application detail GET has side effects (can email the student) and exposes income, NRIC, documents, verdicts | Sources never touch existing views (permission resolver returns nothing for the role = deny by default); new allowlist endpoints under `admin/source/` (S3) |
| C12 | A source must not learn an outcome before the student | Stage shown = the same folded stages the partner emails already use (`partner_comms` stage lines: "recommended" shows as "under review") (S3) |
| C13 | Witness: only a super records it; recorded name is the officer's; executed-copy email links a page a source cannot open; `witnessForbidden` text is stale | Source user records own witness (typed name + declaration); super button stays as fallback for sources with no login; email links go to the source view of that application (S4) |
| C14 | Witness override can name a different source than the applicant's | Source scope = `application.source` **or** `witness_org` (witness case only shows the contract task) (S3/S4) |

## Roadmap — 4 sprints

### S1 — Role and access foundation (backend + role list; nothing visible)
- `courses/0089`: role choice `source_partner`; FK `PartnerAdmin.source` → `scholarship.ReferralSource` (nullable, PROTECT). Precedent: `PartnerAdmin.programme` (courses 0073).
- `apps/scholarship/source_access.py`: `applications_for(admin)` (org fence via `_org_scoped`, plus `source_id` or `witness_org_id` = `admin.source_id`), `programmes_for(admin)` (via `ProgrammeReferralSource` + applications).
- `staff_permissions.resolve()` stays empty for the role — explicit test that every existing B40 view returns 403/404 to a source user.
- `/admin/role/` adds `source_id`, `source_name`.
- `AdminScopeListView` (`views_admin/lifecycle.py:197`) source branch.
- C3 audit + regression test.
- Web: `ROLE_NAMES` in `lib/navigation.ts` (drift test `adminRoleDrift.test.ts`).
- Acceptance: full pytest + jest green; a planted source user sees nothing anywhere.

### S2 — Inviting a source (Invitations + Sources pages)
- Backend: `KIND_ROLES['source'] = ('source_partner',)`; `accept_for_admin` / `purge_expired` fixes; `scholarship/0189` adds `Invitation.referral_source`.
- Invite path (reuse `AdminInviteView`, `courses/views_staff.py:188` — Google / temp password / existing branches): role `source_partner` + either `source_id` (existing source not yet joined) or new source `name` + `code` (creates the `ReferralSource` in the tenant, same rules as today's Add source). Super and org_admin only. Wire `send_source_invitation_email` from `emails/invitation_mail.py`.
- Sources API: POST create removed (moved to invite); PATCH refuses detail fields once joined; list gains `joined` + user count.
- Web: Invitations Source tab form (pick existing or new source; person name, email) + table; Sources page — "+ Add source" becomes "Invite a source →"; Edit only before joining; "Joined" badge; Active toggle unchanged. Fix `set-password` landing.
- Decisions entry (C8). Tests updated.

### S3 — The source console (read-only)
- **Stitch screens first** (mandatory): Overview, Applications list, application view, Scholars, profile. Owner approves before UI code.
- Backend endpoints under `admin/source/`: `profile/` (GET/PATCH: own name; source name, contact person, contact email, phone), `overview/?p=`, `applications/?p=`, `applications/<id>/`, `scholars/?p=`, `scholars/<id>/`. Allowlist serializers, modelled on the sponsor serializers (`serializers.py:99,253,314`). Out of scope = 404. Each view classified in `test_org_fence.py`.
- **What a source sees:** student name, **phone and email (owner ruling 2026-10-30)**, gift, school, state, qualification level, submitted date, folded stage, missing items (names only — already in their emails); for scholars: institution, course, scholar status, contract stage. **Never:** NRIC, address, income, family, essays, documents, scores, merit, verdicts, reviewer names, notes, money.
- `programme_overview.SECTIONS_BY_ROLE` gets `source_partner: ('source',)`.
- Web: nav registry rows for `source_partner` (Programme: Overview, Applications, Scholars; Utility: Profile); landing = `/admin/programme/overview`; the three pages switch to `Source*` components for this role; profile page Organisation card becomes editable for a source.

### S4 — Witness from the console
- `scholarship/0191` (0190 went to S2's `Invitation.referral_source`): `BursaryAgreement.witness_ip` (parity with student / guarantor) + `witness_admin` (which source user).
- `admin/source/applications/<id>/agreement/` (GET the **full contract** PDF — owner ruling 2026-10-30 — only to the named witness source, only on the witness step and after) and `.../witness/` (POST typed name + tick "I confirm…"). Allowed only when the caller's source = `_resolve_witness_org`, the guarantor has signed and no witness yet. Calls existing `bursary.record_witness` (`bursary.py:556`) with `by_name` = user, `witness_name` = typed name. Chain after that is unchanged.
- Super cockpit button stays (fallback).
- Witness-pending email (`emails/signing.py:172`): restore the button when the source has a signed-in user; else keep "reply to this email". Executed-copy link now lands on the source view.
- Overview shows "Waiting for your witness".
- Fix `witnessForbidden` text (en/ms/ta).
- Note: `BURSARY_AGREEMENT_ENABLED` is OFF in production and 0 agreements exist; this ships ready but quiet. Tested with `bursary_e2e`.

### Close (end of S4)
- Guide/FAQ text for sources; `docs/decisions.md`, `.claude/ARCHITECTURE_MAP.md`, CHANGELOG, technical-debt.
- **Adversarial review before push** (identity / PII rule).
- Deploy: migrate-first (courses 0089, scholarship 0190, 0191), then API, then web. **Owner says go before deploy.**
- Web and api deploy in the same push; with BURSARY_AGREEMENT_ENABLED off no witness email is sent anyway. (The witness emails' link `/admin/scholarship/<id>` needs the web to route a source user to its own view — review M2.)

## Verification
- `pytest` full suite + `jest` full suite each sprint; `next build` before push.
- New tests: deny-by-default sweep for the role; scope (own source / witness-only / other source / other org); allowlist field test (no sensitive key ever in a source payload); stage folding; invite branches + refusals; Sources PATCH lock; witness permissions + chain.
- Local run: invite a source with a temp password, sign in, land on Overview, check lists, edit profile, witness a contract made by `bursary_e2e`.

## Doors (sprint-start 3b — identity rule)

Every path that can make someone a signed-in source, widen what a source sees, or take it away.
Each builder covers the doors in its sprint with tests; the adversarial reviewer hunts for one not listed.

- **Become a source user:** invite (existing source / new source), resend, re-invite after a revoke
  (`courses/staff_reinvite.py` — must not resurrect a revoked worker as a source, nor a source as staff),
  first sign-in (`_touch_seen` → `accept_for_admin`), temp-password expiry (`expire_temp_passwords`).
- **Change role:** any staff edit / permission editor path that writes `PartnerAdmin.role` — a row may
  not become `source_partner` without a `source`, and a `source_partner` may not be turned into staff
  by an edit that keeps its `source`.
- **Lose access:** staff deactivate (`is_active=False`), invitation cancel, source switched off
  (`ReferralSource.is_active=False` → its users see nothing); `show_in_apply=False` only hides it on
  the apply form and does NOT remove sign-in.
- **What widens the view:** `ScholarshipApplication.source` (written once at submit), the witness
  override `witness_org` (super/admin/org_admin set it — a witness-only case shows the contract task,
  not the application list row), `ProgrammeReferralSource` (gift links → which gifts appear).
- **Readers that must not count a source user as staff:** Team roster, reviewer pickers/assignment,
  review nudges, payment-chain recipients, Foundation notify list, permission editor, billing/usage,
  staff counts on dashboards, Requests.

## Owner rulings 2026-10-30
- Edit on the Sources page locks once the source has signed in.
- A source sees its students' phone and email.
- The witness source sees the full contract on the witness step.
