# Sprint plan — B40 Assistance Programme, Phase E/F implementation

> **Source of truth:** `docs/scholarship/b40-phase-ef-prd.md` (committed `c85ddfc`) + the owner Boundary decision.
> **Status:** Approved 2026-06-07 — implementation roadmap. Build per sprint; no feature code committed until a sprint starts.

## Context

The PRD specifies nine features across sponsor/reviewer/student. The money-flow backend + anonymised pool exist but are
**dark behind `SPONSOR_POOL_ENABLED`** (lawyer-gated). This plan sequences the build to a demoable end-state.

**Scope decisions (2026-06-07; F7 re-added 2026-06-08):**
- **Build all nine features** — **F1–F9** + a boundary foundation + a go-live sprint. F7 (reviewer assignment/reassignment) was originally deferred as blocked on Check-2-at-submit; **Check-2 is now built on `main`** (`services.is_ready_for_assignment`, `query_response_sla_days`, migrations `0045`–`0047`, reviewer-scoping in `views_admin.py`), so F7 is **unblocked and back in scope**, sequenced into the reviewer cluster (Sprint 7).
- **Real money deferred** — toyyibPay donation-in, disbursement-out, tranche/withholding (**TD-075**) are a separate later track, gated on lawyer sign-off. Everything here uses the existing **mocked** money flow.
- **Granularity** — one feature per sprint; the big full-stack features (F8, F9) split into a **backend** sprint and a **frontend** sprint. ~one coherent deliverable / ~20 files / one session each (CLAUDE.md).
- **Ship dark** — all sponsor-facing work ships behind `SPONSOR_POOL_ENABLED` (off); student onboarding is gated on the award flow. Go-live (flag flip + consent-text sync) is the final, lawyer-gated sprint.

## Sprint sequence

| # | Sprint | Feature | Size | Depends on |
|---|--------|---------|------|------------|
| 0 | Boundary foundation (allowlist widen) ✅ **DONE + MERGED** to `main` 2026-06-07 | (cross-cutting) | S–M, BE | — |
| 1 | Sponsor landing + live counter ⭐ ✅ **DONE** on `main` 2026-06-08 (no migration) | F1 | M, FE+tiny BE | 0 (counter only) |
| 2 | Student post-match onboarding — backend ⭐ | F8a | M, BE | — |
| 3 | Student post-match onboarding — frontend ⭐ | F8b | M, FE | 2 |
| 4 | Sponsor notifications (real-time + digest) ⭐ | F3 | M–L, BE+tiny FE | 0 |
| 5 | Reviewer profile | F6 | M, BE+FE | — |
| 6 | Reviewer invite role selector | F5 | S, BE+FE | 5 |
| 7 | **Reviewer assignment / reassignment** (Check-2 unblocked) | F7 | M, BE+FE | 6, Check-2 |
| 8 | Sponsor profile + sponsored-students | F2 | M, BE+FE | 0 |
| 9 | Student profile + results + relay — backend | F9a | L, BE | 0, 8 |
| 10 | Student profile + relay — frontend | F9b | M, FE | 9 |
| 11 | Sponsor referral / invitation | F4 | M, BE+FE | 1 |
| 12 | **Go-live** (lawyer-gated) | — | S | lawyer sign-off |

⭐ = must-have-for-closure (done by Sprint 4).

---

## Per-sprint detail

### Sprint 0 — Boundary foundation (widen the allowlist) · BE  ✅ DONE + MERGED to `main` 2026-06-07 (was branch `feat/sponsor-boundary-foundation`; migration `0043`; 41 sponsor tests green)
**Deliverable:** the sponsor-facing allowlist reflects the owner Boundary decision, fail-closed, with the trusted gate.
- **Widen** `SponsorPoolCardSerializer` (`serializers.py:38`) + `SponsorPoolDetailSerializer` (`:80`): add academic results/CGPA, field/course, and **`institution` (trusted-gated)**. Keep every field explicit/derived.
- **Add** `Sponsor.is_trusted` (default `True`) — migration `0043` (scholarship is at `0042`). Institution field renders only when the requesting sponsor `is_trusted`.
- **Coarsen** the anon-profile generation prompt (`profile_engine.py:319 _build_anon_prompt`) on family/locality (quasi-identifier guard); `scan_anon_for_identifiers` (`pool.py:87`) stays the backstop.
- **Tests:** extend the existing allowlist assertions — blocked **parent** fields never appear; **institution absent for a non-trusted sponsor**; new fields present for a trusted one.
- **Ships dark** (pool still flag-off).

### Sprint 1 — F1 Sponsor landing page + live counter · ✅ DONE on `main` 2026-06-08 (no migration; ships dark)
Shipped: public `/sponsor` marketing landing (`components/SponsorLanding.tsx`) shown to signed-out visitors when the
programme is live; public `GET /api/v1/sponsor/pool/count/` → `{count, enabled}` (count-only, `AllowAny`, flag-gated);
`getStudentsWaitingCount()` client; trilingual `sponsorLanding.*` (40 keys × en/ms/ta); +3 tests. No tax claims.
Stitch-prototyped + owner-approved before coding. Retro `docs/retrospective-sprint1-sponsor-landing.md`; TD-091 (Tamil
refine) + TD-092 (live click-through at go-live).

### Sprint 2 — F8a Student post-match onboarding (backend) · BE ⭐
**Deliverable:** the accept→onboard→questionnaire backend, on the existing award path.
- **Hook** `respond_to_award` (`sponsorship.py:83`): on accept (after the consent + status flips at `~:110–121`) call new `send_award_confirmed_email(...)` (sponsor identity **never** included — B4).
- **Gate field:** add `ScholarshipApplication.onboarded_at` (migration), mirroring `profile_completed_at` (`models.py:272`, set by `confirm_profile` `services.py:414`); surface in `ApplicationReadSerializer` (`serializers.py:247`).
- **Consent:** new `consent_type='student_onboarding_ack'` recorded via `record_consent` (`services.py:853`); **bump `CONSENT_VERSION`** (`services.py:799`). Onboarding is `granted_by='self'`.
- **Endpoint:** `POST /api/v1/scholarship/applications/<id>/onboarding-complete/` — records the consent, sets `onboarded_at`, stores questionnaire (**new `OnboardingResponse` model** — recommended over JSON for auditability). **Hard gate:** the student must complete this before the first disbursement.
- **Email:** `send_award_confirmed_email` via `_send` (`emails.py:282`) with trilingual `AWARD_CONFIRMED_SUBJECTS/BODIES` (mirror `PASS_*`).
- **Provisional staged-release card copy** (PRD, ⚠️ lawyer-to-vet) lives in the onboarding content.
- **Tests:** accept fires the email + gate; onboarding-complete writes the consent (new type + version) + `onboarded_at`.

### Sprint 3 — F8b Student post-match onboarding (frontend) · FE ⭐
**Deliverable:** the student-facing award + onboarding UI.
- New routes: `app/scholarship/award/page.tsx` (consume `StudentAwardView` `GET/POST /api/v1/scholarship/award/`; guardian modal for minors) and `app/scholarship/onboarding/*` (welcome → acknowledgement cards → questionnaire → confirmation), mirroring the `app/scholarship/apply` wizard.
- API client: `getStudentAward`, `respondToAward`, `submitOnboarding` in `lib/api.ts`.
- i18n `scholarship.award.*` + `scholarship.onboarding.*` (en/ms/ta).
- `app/scholarship/application/page.tsx` gains a "Next: accept your award / complete onboarding" panel.
- **Stitch-prototype first.**

### Sprint 4 — F3 Sponsor notifications · BE + tiny FE ⭐
**Deliverable:** real-time (hourly-batched) + weekly-digest sponsor emails, preference-controlled.
- **Model:** `Sponsor.notify_frequency` (`realtime|weekly|off`, default `weekly`) + `last_digest_sent_at` (migration).
- **Publish hook:** in `AdminPublishAnonProfileView.post()` (`views_admin.py:390`, after `anon_published=True` at `~:414`) enqueue/mark the student for notification (no synchronous fan-out).
- **Commands:** `send_sponsor_realtime` (hourly batch of newly-published students → `realtime` sponsors) + `send_sponsor_digests` (weekly → `weekly` sponsors, students since `last_digest_sent_at`). Register both in `CronRunView.JOBS` (`views.py:711`); add two Cloud Scheduler jobs (X-Cron-Secret / `CRON_SECRET`, mirroring `halatuju-application-reminders`).
- **Emails:** `send_sponsor_new_student_email` + `send_sponsor_digest_email`, trilingual, **rendered through `SponsorPoolDetailSerializer`** so the body is allowlist-safe by construction. Respect Brevo daily-quota.
- **Preference UI:** `PATCH /api/v1/sponsor/notifications/` (`SponsorMixin`) + a toggle in the `/sponsor` account view.
- **Tests:** digest body contains no blocked fields; `off` sends nothing; real-time is batched not per-event.

### Sprint 5 — F6 Reviewer profile · BE + FE
**Deliverable:** a reviewer's own credentials + contact profile.
- New `ReviewerProfile` 1:1 to `PartnerAdmin` (recommended over fields-on-PartnerAdmin, for staff-PII segregation): `highest_qualification, university, graduation_year, field_of_study, phone, address`. **No password field** (hashed by auth, never modelled).
- Self-edit endpoint (scoped to self) + a profile page under `/admin`. **`phone`/`address` are sensitive PII** — reviewer + super only; in the PDPA retention policy; never exposed to students/sponsors.

### Sprint 6 — F5 Reviewer invite role selector · BE + FE (small)
**Deliverable:** invite a reviewer with the right role.
- Extend `/admin/invite` (`app/admin/invite/page.tsx`) + `AdminInviteView` to set `role='reviewer'` (selector: super|reviewer|viewer) and prompt **Reviewer profile** (Sprint 5) completion on first sign-in.
- *(Could merge with Sprint 5; kept separate per one-feature-per-sprint.)*

### Sprint 7 — F7 Reviewer assignment / reassignment · BE + FE
**Deliverable:** super-admins assign a submitted application to a reviewer; reassign it; reviewers see only what's assigned to them.
- **Unblocked:** Check-2 is built on `main` — the assignment gate `services.is_ready_for_assignment(application)` (`services.py:397`), the SLA clock `query_response_sla_days` (`models.py:79`, default 5), Check-2 migrations `0045`–`0047`, and reviewer-scoped lists `qs.filter(assigned_to=admin)` + `has_role(admin,'reviewer')` (`views_admin.py:69` ff) already exist. F7 builds the **assign/reassign action** on top.
- **Field:** `ScholarshipApplication.assigned_to` (FK → `PartnerAdmin`, null) + `assigned_at` if not already present — confirm at sprint start (the reviewer-scoping filter implies `assigned_to` exists; verify before adding a migration). Add an `AssignmentEvent` audit row (or reuse the resolution-ticket audit pattern) so reassignment is traceable.
- **Gate:** assignment is only permitted once `is_ready_for_assignment` is true (no open queries **or** SLA elapsed). Reassignment allowed any time by a super-admin; logs who/when/from→to.
- **BE:** `POST /api/v1/scholarship/applications/<id>/assign/` (body: `reviewer_id`) + `POST .../reassign/` — both `has_role(admin,'super')`-gated; validate the target has `role='reviewer'`; never let a reviewer self-assign. Surface `assigned_to` (name only, staff-internal) in `AdminApplicationDetailSerializer`.
- **FE:** an "Assign reviewer" control in the officer cockpit (`/admin`) — reviewer dropdown (from `AdminInviteView`/reviewer list), shows current assignee + reassign; disabled with a reason tooltip when `is_ready_for_assignment` is false.
- **Tests:** can't assign before ready; super-only; reassign writes an audit row; a reviewer sees only their assigned applications (extends existing scoping tests).
- **No new sponsor-facing surface** — staff-internal; no anonymity-allowlist impact.

### Sprint 8 — F2 Sponsor profile + sponsored-students list · BE + FE
**Deliverable:** a signed-in sponsor's home with their (anonymised) students + progress.
- **Field:** `progress_state` enum (`on_track | semester_completed | needs_attention | graduated`) — add to the allowlist card (built on Sprint 0). Derivation stub here; real derivation lands in F9a.
- **BE:** surface the sponsor's sponsorships via `SponsorSponsorshipSerializer` (`serializers.py:90`) incl. `progress_state`.
- **FE:** "My students" view extending the `/sponsor` portal — account block (`SponsorSerializer`), giving balance (`sponsorship.sponsor_balance`), and the anon cards + progress.

### Sprint 9 — F9a Student profile + results + graduation relay (backend) · BE
**Deliverable:** the student-profile data + the anonymity-preserving thank-you relay.
- Student-profile endpoints: basic details, institution/field, CGPA, **latest-semester results upload** (reuse `ApplicantDocument` `results_slip` + the OCR path). The slip is **myNADI-only**; the **values** cross per the Boundary decision.
- **`progress_state` derivation** from the results upload (feeds F2).
- **`promotional_use` consent** (new `consent_type`, **18+ gate server-side**, version bump) via `record_consent`.
- **Graduation relay:** new `GraduationMessage(application, raw_text, scrubbed_text, scan_result, status, approved_by, ...)`. Pipeline: submit → `scan_anon_for_identifiers` (`pool.py:87`) **blocks on any leak** → myNADI human-approve → surface **linked to the anonymous `ref`** (owner decision) in the sponsor profile. **Never a direct channel.**
- **Tests:** relay blocks planted identifiers; promotional consent enforces 18+; results slip never appears in sponsor output.

### Sprint 10 — F9b Student profile + relay (frontend) · FE
**Deliverable:** the student profile + thank-you compose UI + the sponsor-side surface.
- Student profile page (details, institution/field, CGPA, results upload, 18+ promotional toggle).
- Graduation thank-you compose UI (with the same "we'll check for identifying details" UX as the publish gate).
- Sponsor profile shows the approved note as **"a message from a student you supported"** linked to the anon `ref`.
- **Stitch-prototype first.**

### Sprint 11 — F4 Sponsor referral / invitation · BE + FE
**Deliverable:** sponsors invite prospective sponsors to the F1 landing page.
- `SponsorReferral` model (`inviter, invitee_email, invitee_name, note, code, status, registered_sponsor`) — *or* lightweight `referred_by` (decide at sprint start, PRD Q-6).
- Invite email (sponsor's note + pitch) → `/sponsor?ref=<code>`; attribution on register; **PDPA:** purge unconverted invitee emails after a short window (PRD Q-7).
- WhatsApp share = later.

### Sprint 12 — Go-live (lawyer-gated) · S
**Deliverable:** flip the programme live once the lawyer signs off.
- Sync the **live consent text + `CONSENT_VERSION`** to the lawyer-vetted bundle wording (A3 / Q2 / Appendix B revisions).
- Final anonymity/allowlist audit (run the full serializer + relay + scan test suite).
- Flip `SPONSOR_POOL_ENABLED` **on**.
- **Out of scope (separate TD-075 track):** real toyyibPay, disbursement-out, tranche schedule/withholding — real money is last.

---

## Cross-cutting discipline (every sprint)

- **Migrate-first** (HalaTuju): each schema change = a new migration (`0043+`); apply the migration before the code deploy (via Supabase MCP), per the project's migrate-first rule.
- **Tests alongside** — especially the allowlist/relay/consent assertions; never defer to "a later phase."
- **i18n parity** — en/ms/ta updated together; grep-parity check before deploy.
- **Ship dark** — sponsor-facing behind `SPONSOR_POOL_ENABLED`; nothing sponsor-visible goes live before Sprint 11.
- **Deploy discipline** — ≤2 deploys/feature; **Stitch-prototype** new pages (F1, F8b, F9b) before coding templates.
- **Sprint close** — CHANGELOG + retro + `git push`; update the project CLAUDE.md "Next Sprint".
- **Secrets** — `CRON_SECRET` / email creds in Cloud Run env only.

## Verification (per sprint, end-to-end)

- **Allowlist (0, 4, 8, 9):** serializer + digest-email tests assert no name/NRIC/address/phone/email (student **and** parents); institution absent for non-trusted sponsor.
- **Assignment (7):** can't assign before `is_ready_for_assignment`; super-only; reassign writes an audit row; reviewer sees only assigned applications.
- **Relay (9):** `scan_anon_for_identifiers` blocks planted identifiers in a thank-you note.
- **Consent (2, 9):** `record_consent` writes `student_onboarding_ack` / `promotional_use` at the bumped version; 18+ gate enforced.
- **Notifications (4):** run `send_sponsor_digests`/`send_sponsor_realtime` via the cron endpoint with `X-Cron-Secret`; assert `off` sends nothing, digest body is allowlist-safe.
- **Onboarding (2, 3):** accept an award (mocked) → award-confirmed email → onboarding-complete sets `onboarded_at` + blocks until done.
- **Local-first:** `manage.py runserver` + the relevant page before any deploy; full `pytest` + `jest` green.

## Open items folded from the PRD (decide at the owning sprint)
- F9: confirm `promotional_use` consent type + version (Sprint 9).
- F4: referral model shape + invitee-email retention window (Sprint 11).
- F7: confirm `assigned_to`/`assigned_at` already exist (Check-2 scoping implies it) before adding any migration (Sprint 7).
- Impl details: questionnaire storage = `OnboardingResponse` model (Sprint 2); reviewer-profile = `ReviewerProfile` 1:1, address free-text (Sprint 5).
