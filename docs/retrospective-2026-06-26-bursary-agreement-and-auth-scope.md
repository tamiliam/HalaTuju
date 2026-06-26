# Retrospective — Conditional Bursary Award Agreement (Phase 1) + auth scope policy + sponsor card

**Date:** 2026-06-26
**Commits:** `511259f` (sponsor card) · `63fec7c` + `bf832ce` (auth) · `a085774` (bursary backend) · `f596dd0` (bursary frontend)
**Migrations:** `scholarship/0071` (anon_blurb) · `scholarship/0072` (bursary_agreements) — both migrate-first via Supabase MCP
**State:** all on `origin/main`, both Cloud Build pipelines SUCCESS, bursary shipped **DARK**.

## What Was Built

1. **Conditional Bursary Award Agreement — Phase 1 (headline, DARK).** Award acceptance becomes a binding tri-partite
   contract that *preserves anonymity*: **student** (primary) + **parent/guardian as surety/guarantor** ↔ the
   **Foundation** (interim signatory "Suresh"), with the referring **partner org** as a **non-blocking witness**, and the
   **donor never a party or named**. New `BursaryAgreement` model snapshots the exact wording signed (`rendered_html` +
   `agreement_sha256`), freezes the particulars (amount + RM500/10×RM250 schedule + institution + course), records all
   four signatures, and stores a generated **PDF** (`xhtml2pdf`, `b40-documents` private bucket). The parent surety is
   hard-gated against the compulsory `parent_ic` Vision-OCR (reusing the consent-submit guardian gate, adults included).
   Wired into `respond_to_award` inside the existing cool-off transaction; admin counter-sign + partner witness endpoints;
   `/scholarship/award` rebuilt into the signing page (agreement body in a script-less `<iframe sandbox="">`).
2. **Auth: one active privileged scope per Google identity, super-exempt.** A `63fec7c` bug fix (partner-callback denial
   was a GLOBAL signOut, kicking the user's sponsor session) followed by `bf832ce`, the *intentional* policy via
   `lib/sessionPolicy.ts` — signing into partner *or* sponsor ends the other's local session; super admins keep both;
   kicked tab routes to its login with a "signed out elsewhere" note.
3. **Sponsor pool card redesign** (`511259f`): 4-region card (code·SPM·As·state / programme + target university /
   ≤20-word `anon_blurb` / amount·Support); the secondary school is no longer surfaced to sponsors.
4. **Asasi TVET (`FB0500001`) un-hidden** (data-only): removed an unsatisfiable `"ANY"` or-group on its requirements.

## What Went Well

- **The anonymity model held under a contract that originally broke it.** The owner's source draft was a bilateral,
  fully-identified Donor↔Student instrument. Restructuring the *parties* (Foundation as counterparty, donor never named)
  let us adopt the best clauses without ever exposing the donor — the rendered agreement and PDF carry no donor reference,
  and the new table's RLS + the witness endpoint are scoped to the referring org only.
- **Reuse over reinvention.** The guarantor identity gate is the existing `parent_ic` Vision OCR match; the signing slots
  into the existing `respond_to_award` → cool-off → `sponsored` path; storage + signed URLs are the existing helpers. The
  feature is large in surface but small in genuinely new plumbing.
- **Shipped dark and reversible.** Flag OFF = the accept flow is byte-for-byte unchanged, so the legal/entity gates can be
  cleared on the owner's timeline without holding code.

## What Went Wrong

1. **`next build` would not run in the JS worktree.** *Symptom:* the build failed resolving `@next/env`. *Root cause:* a
   git worktree has no `node_modules`, and pointing it at the main checkout's via a junction breaks Next's module
   resolution. *Fix / system change:* run a real `npm ci` inside each JS worktree — never junction `node_modules`. Add
   this to `parallel-work-isolation.md` so the next JS-worktree session doesn't rediscover it.
2. **Cloud Build poll returned empty rows.** *Symptom:* the build-status poll printed nothing for a known-running build.
   *Root cause:* I filtered builds on `substitutions.COMMIT_SHA`; the field GitHub-triggered builds actually populate is
   `substitutions.SHORT_SHA`. *Fix / system change:* always filter the build list on `SHORT_SHA` — captured in the
   lessons file so it isn't relearned per session.
3. **First RLS migration used FORCE.** *Symptom:* `bursary_agreements` with `FORCE ROW LEVEL SECURITY` would have blocked
   the app's own owner role. *Root cause:* reached for a generic "lock the table" RLS snippet instead of matching the
   existing working-table pattern. *Fix / system change:* for any new table, mirror the established pattern —
   `ENABLE ROW LEVEL SECURITY` but **NOT FORCE** (verify `relforcerowsecurity = false`), as `whatsapp_messages` /
   `course_data_status` already do. The `get_advisors` INFO row for an RLS-on/no-policy table is expected, not an error.
4. **I theorised the auth trigger before checking the data.** *Symptom:* I initially attributed Suresh's session-kick to
   the global-signOut path. *Root cause:* hypothesising a mechanism before pulling the actual identity/role rows — the
   global-signOut doesn't fire for him because he is `is_admin=true` across all three UIDs; the kick was Supabase
   same-identity session handling. *Fix / system change:* for an auth-behaviour report, pull the specific user's
   role/UID rows *first* and let the data pick the mechanism, before proposing a fix.

## Design Decisions

(Logged in `docs/decisions.md` — bursary record as a contract not a `Consent`; the anonymity-preserving party structure;
`xhtml2pdf` over weasyprint; the one-privileged-scope-per-identity auth policy.)

## Numbers

- **5 commits**, 2 migrations (0071, 0072), 1 data-only fix.
- **Backend:** 1515 scholarship pytest pass (+15 new in `test_bursary_agreement.py`); bursary backend ≈ 19 files,
  `bursary.py` ≈ 572 lines.
- **Frontend:** 371 jest pass (incl. +6 `sessionPolicy.test.ts` and i18n parity); `next build` clean.
- **i18n:** en/ms/ta at parity (Tamil first-draft for the new legal + auth strings).
- Both Cloud Build pipelines (api installed `xhtml2pdf`, web) SUCCESS; worktrees removed.
