# B40 Redesign — Sprint 11a Retrospective (2026-05-24)

The admin **verify-&-accept** gate + NRIC lock + mentoring flag. Backend + admin frontend, branch
`feature/b40-redesign`, not deployed. (Applicant application-page states + login banner split to S11b.)

## What Was Built
- `AdminVerifyAcceptView` — the human verification gate: admin confirms a 4-item checklist (NRIC / name / results /
  document) against the uploaded MyKad → sets `profile.nric_verified` (**locks** the NRIC), stamps
  `verified_at` / `verified_by` / `verify_checklist`, advances **shortlisted → accepted**. Guarded to shortlisted only.
- New **`accepted`** status (shortlisted = passed the auto-screen; accepted = human-verified & confirmed).
- Mentoring-candidate toggle via PATCH on the admin detail endpoint.
- Admin detail page: a Verify-&-accept checklist card (Accept enabled only when all four ticked; locked/accepted +
  verified-by state otherwise) + mentoring toggle. `admin-api.ts` mutations + detail-type fields. EN/MS/TA i18n.
- Migration `0009` (audit fields + the `accepted`/`verdict` choice alters); serializer exposes the NRIC (full, for
  comparison), `nric_verified`, the audit fields, `mentoring_candidate`, and the S10 plans/support intake.

## What Went Well
- The S6a MyNadi admin (auth via `PartnerAdminMixin`, list/detail/profile views, `_AdminBase`) was a clean seam —
  `AdminVerifyAcceptView` dropped in as another `_AdminBase` subclass and the admin detail page gained one more card.
  No auth plumbing, no new admin-frontend scaffolding.
- **TD-054 dissolved rather than patched.** The soft-NRIC decision (S7) said uniqueness should surface at
  verification; implementing verify-&-accept made that the natural single enforcement point (409 on a verified
  duplicate), so the old claim transfer-path collision stopped being load-bearing. The right fix was architectural,
  not a patch to the buggy path.
- Backend-first then build the admin UI to the live endpoint: 5 targeted tests (happy path, conflict, guard,
  mentoring, auth) all green on first run; full suite 1100, golden masters intact.

## What Went Wrong
- Nothing notable. The migration's `AlterField` on `status` **and** `verdict` (both share `STATUS_CHOICES`) was an
  expected, harmless no-op (choices are validation-only, not DDL) — flagged here so a future reader doesn't mistake
  the `verdict` alter for an unintended change.

## Design Decisions
- Verify-&-accept is the single NRIC-uniqueness enforcement point; new `accepted` status — see `docs/decisions.md`.

## Numbers
- Backend **1095 → 1100**; frontend jest unchanged (**49**); i18n **1101 keys × 3** (parity); `next build` clean.
  ~9 files + migration `0009`. Admin card approved via local screenshot.
