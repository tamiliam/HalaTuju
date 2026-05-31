# Phase E — Safeguarded Sponsor Marketplace (roadmap)

**Status:** approved 2026-05-31. **Sprint E1 ✅ DONE (v2.22.0, 2026-05-31)** — sponsor accounts + admin vetting,
no student data. ▶ next: **Sprint E2** (anonymised pool — PDPA-critical, lawyer-gated before real students).
**Supersedes** the one-line "Phase E (2 sprints)" entry in `post-shortlist-vision.md` — the
safeguarded marketplace is one slice larger (3 sprints).

## Product model (locked with user, 2026-05-31)

A **P2P-style anonymous marketplace.** Sponsors discover and choose students to support, but
**never** see anything that could identify a student — **no name, NRIC, street address, phone,
email, or photo — ever, even after a match.** The platform holds the identity and intermediates
(money will flow sponsor → programme → student in a later phase, keeping identity hidden end-to-end).

Decisions:
- **Sponsors self-register (open signup) but are admin-VETTED before any access** ("open to apply,
  approved to browse"). No student data until a human approves the sponsor.
- **Matching = sponsor browses & picks** (a marketplace), but only **anonymised** cards.
- **Permanent anonymity**, enforced by an **allowlist** sponsor-facing serializer (never a denylist —
  a new model field is invisible to sponsors until deliberately added). This is the load-bearing
  safety property; dedicated tests assert no identifying field can leak.
- **Sponsor-safe profile is GENERATED non-identifying, not scrubbed.** The Phase-D `final_markdown`
  contains the student's name; for sponsors we generate a parallel anonymous profile via
  `profile_engine` (fed only non-identifying inputs, instructed to say "the student"). Admin keeps
  the named version; sponsor only ever sees the anonymous one.
- **Consent = consent to the sponsorship arrangement**, not an identity reveal (there is none). For
  minors, guardian consent. A profile only enters the pool when published + opted-in + consented.

## Hard gates (cross-cutting)
1. **Lawyer review before real-student exposure.** E1 has zero student data → ships freely. **E2/E3
   may be built + tested on dummy data but must NOT go live to real students until the lawyer signs
   off** (same review covering the consent text).
2. **RLS + PDPA-minimal serializers on every new table** (service-role-only pattern, per
   incident-001-rls). Migrate-first via Supabase MCP throughout. No PII in logs or anonymous views.

## Lessons applied (from docs/lessons.md)
- Mirror `PartnerAdmin` / `PartnerAdminMixin` for the sponsor auth scope (Supabase-user-id keyed).
- **Check `Meta.db_table` before any raw/MCP SQL** — scholarship models use custom table names.
- New tables need RLS (service-role pattern); apply migrate-first.
- Frontend: hooks before any early return; one mockable seam for AI/external calls.
- Allowlist > denylist for the sponsor serializer (safety).

---

## Sprint E1 — Sponsor accounts + admin vetting *(no student data)* ✅ DONE (v2.22.0, 2026-05-31)
- **Shipped:** `Sponsor` model + migration `scholarship/0031` (table `sponsors`, migrate-first + RLS deny-by-default);
  `SponsorMixin`; `POST /sponsor/register/` + `GET /sponsor/me/`; admin `GET /admin/sponsors/[?status]` +
  `POST /admin/sponsors/<id>/review/`; **allowlist `SponsorSerializer`**; NRIC-gate whitelist. Frontend: `/sponsor`
  portal + `/admin/sponsors` vetting table + nav. 1408 pytest (+12) + 172 jest. **Not yet click-tested (TD-070).**
- **E1c follow-up ✅ DONE (v2.23.0, 2026-05-31) — sponsor self-serve auth.** Real account: `/sponsor/login` (email/pw
  + Google + forgot) + `/sponsor/register` (Full name as in NRIC/Passport, Email, Password w/ rules, Re-enter, Phone
  +60, Source, PDPA consent); Google → "complete your details" step. **Isolated sponsor auth stack** (`sponsor-supabase.ts`,
  `SponsorAuthProvider`, `/sponsor/auth/callback`) mirroring admin — **replaced E1's `KEY_SPONSOR_SIGNIN` student-client
  hack**. `Sponsor` + phone/source/consent (migration `0032`). Shared `AuthButtons` (Log in ▾ + Sign Up) on header +
  landing. Deferred: Turnstile (TD-071), MY-only phone + orphaned register-interest (TD-072). 1411 pytest + 178 jest.
- **Goal:** anyone can self-register as a sponsor → "pending approval" → an admin approves/rejects →
  an approved sponsor logs into an (empty) portal shell. Zero student data exposed.
- **Scope:** `Sponsor` model (supabase_user_id-keyed, status pending/approved/rejected/suspended) +
  migration + RLS; `SponsorMixin` auth gate (mirror `PartnerAdminMixin`); self-signup + "my sponsor
  status" endpoints; admin list/approve/reject endpoints + admin UI; sponsor portal shell (signup +
  pending/approved states). i18n. Tests (auth gate, signup, approval transitions).
- **Acceptance:** signup creates a *pending* sponsor; admin approval flips access; an unapproved
  sponsor is blocked from any sponsor endpoint; tests green.
- **Complexity:** Medium-High (new auth scope).

## Sprint E2 — Student opt-in + anonymised discovery pool *(PDPA-critical)*
- **E2a ✅ DONE (v2.24.0, 2026-05-31) — BACKEND, flag-gated, dummy data, NOT live.** `SPONSOR_POOL_ENABLED` (default
  OFF). **Eligibility = anon profile published + active `share_with_sponsors` consent** (consent IS the opt-in —
  decided with user; no separate toggle). `pool.py` (`is_pool_eligible`/`eligible_pool_queryset`/`pool_ref`/
  `academic_band`). **Generated (not scrubbed)** anon profile (`profile_engine.generate_anonymous_profile`, non-ident
  inputs only — no name/school/referees) → admin generate→review→publish (regenerate un-publishes). **Allowlist**
  `SponsorPoolCardSerializer`/`SponsorPoolDetailSerializer` (plain Serializer, explicit fields, zero passthrough,
  leak-tested). Endpoints `/sponsor/pool/[/<id>/]` (flag + approved-sponsor gated) + admin `…/anon-profile/generate|publish/`
  (reviewer-gated). Migration `0033` (additive `anon_*` on `sponsor_profiles`). 17 tests. **Conservative card:** alias ·
  state · field · academic band · funding categories · months.
- **E2b ✅ DONE (v2.25.0, 2026-05-31) — FRONTEND, dark deploy.** `/sponsor` approved → anonymised cards grid (or
  coming-soon shell on flag-off 404) + `/sponsor/pool/[id]` detail (summary + generated anon blurb via react-markdown +
  anonymity note). Admin `/admin/scholarship/[id]` "Anonymous profile" card: Generate (AI) → preview → Publish/Unpublish
  + badge (reviewer-gated). Client fns `getSponsorPool`/`getSponsorPoolDetail`/`generateAnonProfile`/`publishAnonProfile`;
  i18n `sponsorPool.*`/`anonProfile.*`. No migration. **▶ Phase E2 COMPLETE end-to-end (behind the OFF flag).** Next:
  lawyer review (gate to flipping the flag) + TD-074b pre-publish scan, then E3.
- **Goal:** a student/guardian opts a published, consented profile into the pool; approved sponsors
  browse anonymised cards with filters; a sponsor-safe anonymous profile is generated.
- **Scope:** pool opt-in + share-consent model (guardian consent for minors); eligibility rule
  (published + opted-in + consented); **allowlist anonymised card + profile serializers**;
  sponsor-safe profile generation (`profile_engine`, non-identifying); sponsor browse/search
  endpoint + UI; student opt-in toggle on /application. Migration + RLS.
- **Acceptance:** only eligible students opt in; cards/profile leak **zero** identifying fields
  (asserted); approved sponsors browse, unapproved can't.
- **Complexity:** High (anonymisation correctness is load-bearing).

## Sprint E3 — Match → consent → sponsorship
**REDESIGNED 2026-06-01 (with the user) into a wallet/donation model — supersedes the "express interest" sketch below.**
A sponsor **donates** into myNADI (final, never a bank refund) → spendable balance = donations − holding allocations.
The sponsor **funds a student IN FULL** for an admin-set **award amount** (1:1, full-or-nothing for now; many-sponsor
plumbing underneath) → award → the student/guardian **accepts** within a deadline → `Sponsorship` active, app
`sponsored`. Decline/lapse → the amount returns to the sponsor's balance (no money leaves myNADI). Anonymity holds
**both ways** (the student never sees the sponsor either — user's call). Money is a ledger; real toyyibPay + disbursement
+ tranches are a later, lawyer+gateway-gated slice.

- **E3a ✅ DONE (v2.26.0, 2026-06-01) — BACKEND, dummy data, mocked money, dark.** `Donation` + `Sponsorship` models
  (migration `0034`, migrate-first) + `award_amount` + `sponsored` status. `sponsorship.py`: `sponsor_balance` /
  `is_fundable` / `fund_student` / `respond_to_award` (guardian gate, reuses `record_consent`) / `lapse_expired_offers`.
  Endpoints: sponsor wallet/donate(mock)/fund/sponsorships/cancel (flag+approved gated); student `scholarship/award/`
  GET+accept/decline; admin award-amount + `admin/sponsorships/` oversight. **Allowlist both ways, leak-tested.** Pool
  excludes sponsored. +17 tests. **▶ E3b/E3c (TD-075):** real toyyibPay + disbursement + tranche schedule + lapse cron
  + the frontend. Lawyer reviews the donation/award terms before any real money.

### (Superseded sketch — kept for history)
- **Goal:** sponsor expresses interest → student/guardian consents to the sponsorship → `Sponsorship`
  created, app → `sponsored`, sponsor follows the **anonymous** profile + progress.
- **Scope:** `Sponsorship` model; "express interest" endpoint; per-sponsor consent-to-sponsor request
  + student approval screen; on consent → create Sponsorship + set status; sponsor "my students"
  view (anonymous profile + status only); admin oversight of matches. Migration + RLS.
- **Acceptance:** no sponsorship without consent; on consent the link exists + status flips; a sponsor
  can never see a non-consented OR an identifying field (asserted); tests green.
- **Complexity:** High.

**Deferred (later phase):** money/pledges/disbursement, sponsor↔student messaging, progress feeds,
multi-sponsor economics, mentor scope (Phase F).
