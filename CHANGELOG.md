# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Verification-accuracy pass (5 live-testing fixes; no migration).** Upstream gaps the owner surfaced while
  reviewing real applicants:
  - **(#4) An optional wrong-person income doc no longer hard-blocks submission.** A father's payslip dropped onto a
    mother-STR cluster (where the STR is the income proof and the slip is optional), or a mismatched EPF, previously
    added `income_document_mismatch` to `document_red_blockers` and trapped the student. Now only a **compulsory**
    salary-route slip for a selected member gates; the cluster coach nudges removal instead. Gopal's
    `income_proof_person_mismatch` copy is **earner-aware** — it names the expected earner (the STR recipient) via the
    firewall-safe `context` seam, says the slip is optional on the STR route ("upload nothing if she has none"), and
    advises removing the wrong file (replacing the misleading hardcoded "father's payslip" example).
  - **(#2) Transliteration-tolerant relationship name matching.** New `vision.relationship_name_match` folds
    Malaysian-Tamil/Indian romanisation (w↔v, doubled letters, trailing silent h) + a single-char OCR slip on longer
    tokens, fixing the false `mismatch` on *Saravanan* vs *Sarawanan* (the "Sarawanan A/L Supramaniam" call).
    `income_engine` uses it for every name comparison (relationships, earner-IC↔proof, STR-recipient↔IC, BC names) —
    all the SAME person across two documents; **identity (student IC vs typed name) still uses the exact matcher**, so
    it is never weakened. Differential audit on prod earners: 0 false merges across 16 distinct names.
  - **(#3) Utility-bill address match tolerates a missing postcode.** A real bill often omits the 5-digit postcode
    (Swetha's water bill), which made `address_present` return `not_found` despite the street + city matching. It now
    falls back to a strong overlap of distinctive **street** tokens (road name + numbers + taman) + the city, via a new
    address-aware tokenizer that keeps numbers and drops generic road words (jalan/jln/taman/tmn/no). Soft, never gates.
  - **(#1) The salary-route "who works" default stays reactive to the family roster.** The income wizard seeded
    `income_working_members` from `earningMembers(app)` only once (useState), so a roster filled/refetched after the
    income step mounted never flowed through. A `useEffect` now re-derives the default whenever the roster changes,
    until the student explicitly customises the selection.
  - **(#5) An approved STR is current without needing a year.** The MySTR "Semakan Status" / Dashboard pages show
    "Status Permohonan **Semasa**: Lulus" with NO printed cohort year — *Semasa* (current) is the currency signal.
    `_str_currency` previously demanded an approval word AND a readable year, falsely marking 5 of 14 submitted STR
    students as unconfirmed for a valid Lulus screenshot. Now an approval word alone → current; a year only adds the
    ability to catch a stale prior-year STR; a no-approval-status SALINAN is still unconfirmed. STR extraction gains a
    closed-set **`source_type`** (letter / semakan_status / dashboard / unknown) so each layout's fields read from the
    right place + the officer sees the source, and reads the year off Tarikh-Kredit / letter dates when present. Gopal +
    i18n copy stop implying a date/year is needed — a plain screenshot showing "Lulus" is enough.
  - **(#5b) SARA is not STR — the `source_type` bucket now GATES the verdict.** A standalone SARA (Sumbangan Asas
    Rahmah) document — e.g. a Perdana Menteri greeting letter saying the recipient is *"terpilih untuk terus menerima
    bantuan SARA"* (app #63's letter) — is a different programme from STR and is **not** valid STR proof, but it was
    auto-passing because `_str_currency` looked only at an AI-inferred status word. Now `_str_currency` takes the
    `source_type`: a positively-classified **`unknown`** source returns `unconfirmed` whatever status text was read;
    SARA's **"Layak"** is removed from the STR approval words (STR uses "Lulus"); and the extraction prompt classifies a
    SARA-only letter as `unknown` and does **not** infer an approval status from SARA-recipient wording. A blank/legacy
    `source_type` (docs extracted before classification existed) still falls through to the status check so existing
    approvals aren't retro-broken. Gopal/i18n tell the student we need their **STR (Sumbangan Tunai Rahmah)**, not a SARA
    letter. (App #63's existing record is corrected post-deploy — its extraction predates classification.)
  - Gates: **1010 scholarship + 1063 courses/reports pytest, 282 jest, next build clean, i18n parity 2474×3**; golden
    masters intact (SPM 5319 / STPM 2026). No migration. Retro `docs/retrospective-verification-accuracy-fixes.md`.

### Added
- **Action Centre Phase 2 — Cikgu Gopal nudges a totally off-topic answer.** When a student types an answer to a
  query, a flag-gated relevance check (`help_engine.judge_answer_relevance` → one cheap Gemini JSON call, firewalled to
  the question + answer text only) decides whether to accept it. It is **deliberately very lenient** (owner D2): only a
  **completely unrelated** answer is nudged — anything with any bearing is accepted as the student's answer. On a nudge,
  the task **stays open** and Gopal gives one warm, one-line steer (reusing the `CoachCard`); editing the answer clears
  it. Behind `CHECK2_ANSWER_RELEVANCE_ENABLED` (**default off** — a billable knob); **AI-off/error always accepts**, so
  it never traps a student. The resolve endpoint takes the displayed `question` and returns `{resolved:false, nudge}`
  when off-topic. +7 scholarship pytest (engine reduction + the view's nudge/resolve/flag-off paths); new i18n
  `actionCentre.relevanceNudge` (en/ms/ta). No migration.
- **Action Centre live-testing polish (from the click-through).** (1) **The student's queue shows ONLY
  deliberately-raised items** — a reviewer's (officer) request or an AI clarify query — **never the system's own verdict
  gaps** (those stay on the officer cockpit). This fixes the duplicate where a mismatched/unreadable upload spawned a
  `system` ticket beside the reviewer task + Gopal's coach (`ResolutionItemListView` excludes `source='system'`).
  (2) **Completed tasks stay on the page as green "Done" cards** (check + strikethrough + DONE badge) below the open
  ones, instead of vanishing — the satisfaction of seeing what you've cleared; the progress bar moves with them. New
  i18n `actionCentre.done`.
- **Action Centre documents are now "smart" — scan-on-upload + contextual Cikgu Gopal (Phase 1).** Uploading a
  requested document now runs **that document's specific scan** (reusing the Documents-tab engines:
  `birth_certificate`→relationship, `salary_slip`→income, `results_slip`→academic, `offer_letter`→pathway, `str`,
  `ic`, …). A clean scan **ticks the task done**; a confirmed **mismatch/unreadable keeps the task open and surfaces
  Cikgu Gopal inline** with the specific fix (the same `DocumentHelpCoach` as Documents), inviting a clean re-upload.
  This **also fixes a real bug**: a reviewer/AI-raised *document request* (`officer` resolution item) never cleared on
  upload — only auto-verdict (`system`) items did — so a student could upload exactly what was asked and the task stayed
  stubbornly open. New `resolution.doc_match_verdict(doc)` (mirrors the consent-gate per-doc red/unreadable
  classification, so the Action Centre and the gate never disagree; only a confirmed mismatch / unreadable keeps a task
  open — uncertain/soft/pending are accepted, D1) + `resolve_doc_items_for_upload(app, doc)`, wired into the upload
  endpoint (`recordDocument` returns a `match_verdict`). The **static Cikgu Gopal footer is removed** — he's now
  contextual (appears only when an uploaded document needs a fix). +17 scholarship pytest (`doc_match_verdict` reduction
  per doc-type + the resolve-on-match/keep-open gate); reuses existing `scholarship.docs.help.*` copy (no new i18n).
  FE-only contract change + a 2-line backend wire; no migration. 982 scholarship pytest + 276 jest + next build clean +
  i18n parity 2472. *(Phase 2 — a conservative Gopal nudge on typed answers, only when totally off-topic — is planned
  next.)*
- **Action Centre now mounts for submitted students (post-submit query/document surface).** Previously
  `/scholarship/application` only rendered the interactive follow-up (which hosts the Action Centre) for
  `shortlisted`; a `profile_complete` student — exactly when queries/document-requests are raised — fell through to a
  dead-end "received" card and had nowhere to respond. Now `profile_complete` / `interviewing` / `interviewed` render
  the **Action Centre** (`ActionCentre formLocked`) as their whole surface. **The application is locked** — having
  consented, reviewed the final values and submitted, the student can no longer see or edit the 5-step form; they can
  only **respond to queries** (AI/human) and **upload requested documents**, all resolved **in place** (`doc` → upload,
  `explanation`/`clarify`/non-pathway `confirm` → typed reply, `pathway_confirm` → "Yes"). The new `formLocked` prop also
  swaps a `confirm` ticket's "Review → jump to form tab" for a typed reply (no form to jump to post-submit), and when
  **nothing is pending** shows a calm *"You're all set — your application is with our team, we'll be in touch"* message
  instead of rendering nothing. **The email notification + AI clarify-queries stay switched off**
  (`CHECK2_STUDENT_QUERIES_ENABLED` untouched); flag-off, the Action Centre still surfaces system verdict doc/confirm
  tickets and officer(human)-raised items — so it works end-to-end without turning Check 2 on. New i18n
  `scholarship.actionCentre.{lockedTitle,lockedIntro,awaitTitle,awaitBody}` (en/ms/ta; Tamil first-draft). FE-only, no
  backend/migration. `next build` clean; 276 jest; i18n parity 2436×3.

### Changed
- **B40 income gate: gross household income is now the primary test; per-capita is a safety net (deployed 2026-06-09).**
  Following the DOSM 2024 update (B40 line = RM5,860), a non-STR applicant whose **gross** monthly household income is
  at or below the cohort `income_ceiling` is shortlisted **regardless of household size**. The per-capita ceiling
  (RM1,584) no longer gates everyone — it now only **rescues households *above* the gross ceiling** that have many
  dependents. STR recipients still pass directly. Added `rescore_pending_decisions` (service + `rescore-pending` cron
  job) which re-applies the engine to **un-released** decisions only; ran once on deploy → one pending applicant
  (RM5,500 gross, family of 2) flipped rejected→shortlisted before their decision was sent. Migration `0056` (help-text).
- **Invite an already-registered user instead of failing; search applicants/students by phone + email (deployed 2026-06-09).**
- **Admin roles realigned to super / admin / partner / reviewer (deployed 2026-06-09).** Replaced the old
  super/reviewer/viewer model. **Super** = owner (everything); **Admin** = sees all pages, read-only for now;
  **Partner** = own-organisation's students only (Dashboard + Students + Profile); **Reviewer** = only the
  applicants assigned to them (B40 Applications + Profile), and makes the final accept/reject decision.
  - **Scoping enforced everywhere:** `get_partner_students` (Students/Dashboard/CSV export) is role-aware;
    every B40 endpoint — list, detail, and all actions (verify-accept, verdict, interview, reject, award,
    profile generation, run-vision, …) — routes through `_scoped_application`, so a reviewer can neither see
    nor act on an unassigned applicant; partners get 403 on B40. Covered by leak tests.
  - **Nav** is role-driven; **invite page** rebuilt (role-first selector, dynamic title, organisation is
    Partner-only, super is not invitable); **profile page** redesigned — fixed a bug where a super admin saw
    reviewer-credential fields, made it responsive, added qualification/field dropdowns (+ Other), a public
    university autocomplete (20 IPTA, acronym + EN/BM alias matching, free-text fallback), a +60 phone mask,
    and a structured address split (street / postcode / city / state).
  - Migrations: courses `0053` (role choices) + scholarship `0055` (ReviewerProfile structured address, additive).
- **"B40 Aid" nav is now an umbrella dropdown for both audiences (students + sponsors).** The top-nav "B40 Aid" item
  (`AppHeader`) became a hover/focus dropdown with two paths — **"Apply for assistance"** (`/scholarship`) and **"Become a
  sponsor"** (`/sponsor`) — active on either side; the mobile menu shows the two as an indented section. The previously
  orphaned sponsor landing (`/sponsor`, signed-out) now uses the **main `AppHeader`** instead of its own bespoke top bar,
  so there's one consistent header + the unified Student/Sponsor/Partner "Log in" dropdown everywhere (sponsor auth stays
  on its own isolated client — presentation only). The `/scholarship` "support a student" CTA's dead
  `mailto:…Sponsor enquiry` now links straight into the `/sponsor` funnel. New i18n `scholarship.subnav.{apply,sponsor}`
  (en/ms/ta). `next build` clean; 276 jest; tsc clean. (Built in an isolated git worktree alongside the parallel
  admin-search work.)

### Deployed — B40 sponsor programme GO-LIVE (2026-06-09)
- **The whole B40 Phase E/F sponsor programme went live** (Sprint 12, lawyer-gated go-live, owner-authorised with the
  current draft consent wording — the lawyer-vetted text + a `CONSENT_VERSION` bump land as a follow-up). The 25
  held-local commits (Sprints 1–11: F1 landing, F8 onboarding, F3 notifications, F6/F5/F7 reviewer cluster, F2 sponsor
  "My students", F9a/b in-programme + graduation relay, F4 referral) were deployed in one batch. Sequence: (1) migrations
  `0049`–`0054` applied **migrate-first** to prod via Supabase MCP (additive columns + 6 new tables) with **RLS enabled**
  on every new table (`onboarding_responses`, `reviewer_profiles`, `assignment_events`, `graduation_messages`,
  `semester_results`, `sponsor_referrals`) in the same transaction, verified table-by-table; (2) `git push` → both Cloud
  Build deploys SUCCESS (api `…00325` then `…00326`, web rebuilt); (3) **`SPONSOR_POOL_ENABLED=true`** flipped on
  `halatuju-api` via `--update-env-vars` (pool count endpoint now `enabled:true`); (4) **3 Cloud Scheduler jobs** created
  + ENABLED — `halatuju-sponsor-realtime` (hourly), `halatuju-sponsor-digests` (weekly Mon 09:00), `halatuju-purge-referrals`
  (daily 03:00, F4 PDPA purge), the last smoke-tested green; (5) live smoke — new endpoints return 401 (clean auth gate,
  not 500), web `/sponsor` 200. Resolved TD-093/095/098/100/102/106/107. **Still open (post-lawyer):** Tamil refine
  (TD-091/094/096/097/105/108), the lawyer consent-text + `CONSENT_VERSION` bump, real toyyibPay money (TD-075). Retro
  `docs/retrospective-sprint12-go-live.md`.

### Changed
- **Partner admin tables — MySkills-style header + search/filter row (Students + B40 Applicants).** Both
  `/admin/students` and `/admin/scholarship` now lead with a title + count subtitle and a filter row that starts with a
  debounced (300 ms) search box. **Students:** title "HalaTuju Students" + "{count} students" subtitle; filters Search ·
  Exam (SPM/STPM) · Source. **B40:** title renamed to "B40 Assistance Applicants" + "{count} applicants" subtitle;
  Search added in front of the existing All statuses · All buckets · Anyone filters. Backend (no migration): the students
  endpoint (`PartnerStudentListView`) gains `?q` (name/NRIC icontains), `?exam`, `?source` and returns distinct
  `source_options` for the dropdown (`.order_by()`-cleared DISTINCT so it's Postgres-safe); the applications endpoint
  (`AdminApplicationListView`) gains `?q` (matched against `profile.name`/`profile.nric`). Search resets to page 1 and
  composes with the existing filters. The shared `Pagination` footer was also reskinned to the MySkills layout (Show
  [n] per page · Page X of Y · jump-to-page · First/Previous/Next/Last), replacing the numbered-page window (orphaned
  `lib/pagination.ts` `pageWindow` helper + test removed). +14 backend pytest (8 students search/filter, 6 B40 search);
  i18n en/ms/ta parity (ms/ta first-drafts). No migration.
- **Server-side pagination for both partner admin tables — Students + B40 Applications (MySkills-style).** Both
  `/admin/students` (`PartnerStudentListView`) and `/admin/scholarship/applications` (`AdminApplicationListView`) now
  paginate server-side via a new shared `FlexiblePageNumberPagination` (`halatuju_api/halatuju/pagination.py`; `?page`
  + `?page_size` up to 100, default 25) instead of returning every row for the browser to slice (or, for B40, never
  paginating). Its `.envelope()` helper keeps each view's existing top-level fields (`org_name`/`is_super_admin` for
  students; `total_count` kept as a backward-compatible alias of the total filtered count for applications) and adds
  `count`/`total_pages`/`page`/`page_size`/`next`/`previous`. Pagination is opted in **per view** — no global
  `REST_FRAMEWORK` default — so existing full-list endpoints are untouched; the CSV export stays unpaginated. On the
  B40 view, the status/bucket/assigned filters are applied before paging, so they compose. Frontend gains a reusable
  stateless `<Pagination>` control (`components/Pagination.tsx` + pure `lib/pagination.ts` `pageWindow()` helper) with
  windowed page buttons (no more 67-button row), a 10/25/50 page-size selector, and an overridable `rangeKey` so each
  table shows the right noun; changing a filter resets to page 1. Both pages fetch one page at a time. New i18n keys
  `admin.perPage` + `admin.scholarship.showingRange` (en/ms/ta). +12 pytest (7 courses, 5 scholarship) + 7 jest; `tsc`
  clean. Built on branch `feature/partner-pagination` (held local, no push). Rollout notes:
  `docs/partner-pagination-plan.md`.

### Added
- **Sponsor referral / invitation (B40 Phase E/F Sprint 11, F4, BE+FE, held local; migration `0054`).** An approved
  sponsor can invite a prospective sponsor to the F1 landing. **Owner decision (2026-06-09): the full `SponsorReferral`
  guest-book** (not a lightweight `referred_by`) with a **60-day** PDPA retention window. New `SponsorReferral` model
  (`inviter, invitee_email, invitee_name, note, code, status, registered_sponsor`); new module
  `apps/scholarship/referrals.py` — `create_referral` (validates email `bad_email`, generates an opaque code, sends the
  invite email best-effort; a duplicate still-pending invite to the same email is idempotent), `attribute_referral`
  (a `/sponsor?ref=<code>` register flips the matching referral to `joined` + links the new account; self-/unknown-code
  is a safe no-op), `purge_expired_referrals` (scrubs `invitee_email`/`invitee_name` + marks `expired` for still-invited
  rows older than 60 days). Trilingual invite email (`send_sponsor_referral_invite`, sponsor's note + pitch →
  `/sponsor?ref=<code>`). Endpoint `GET/POST /api/v1/sponsor/referrals/` (approved sponsors only; `SponsorReferralView`);
  `SponsorRegisterView` now attributes a `ref` on join. Daily PDPA purge wired as `purge-referrals` in `CronRunView.JOBS`
  + a `purge_sponsor_referrals` command (TD-107 = the Cloud Scheduler job at deploy). **Frontend** `/sponsor` (approved):
  an "Invite a friend" form + a "Your invitations" list with Joined/Invited/Expired pills; the invite link's `?ref=` is
  captured to `sessionStorage` (`KEY_SPONSOR_REF`) on arrival and passed through `register` so attribution survives the
  sign-in round-trip. New api clients `getSponsorReferrals`/`createSponsorReferral` + `ref` on `registerSponsor`.
  Trilingual `sponsorPortal.referrals.*` (i18n parity 2416, +17; Tamil first-draft, TD-108). **+12 scholarship pytest**;
  `next build` clean (`/sponsor` 7.21 kB); 283 jest. **Migration `0054`** (new model → MCP + contenttypes workaround +
  RLS at deploy, TD-106). Retro `docs/retrospective-sprint11-sponsor-referral.md`.
- **Student in-programme + graduation relay — frontend (B40 Phase E/F Sprint 10, F9b, held local, ships dark; no
  migration).** The student/sponsor UI for F9a's backend. **New student page `/scholarship/in-programme`** ("My
  progress"), Stitch-approved, shown once the award is accepted (`status='sponsored'`), three cards matching the
  apply/onboarding style: **(1) Semester results** — a live progress pill (on track / semester completed / needs
  attention / graduated, derived client-side to mirror the server band) + a list of past results + an inline "Add result"
  form (semester, CGPA 0–4 with `bad_cgpa` handling, "final/graduating" checkbox); **(2) Sharing your story** — the
  18+-only `promotional_use` toggle (greyed with "Available once you turn 18." for a minor, driven by the server's
  `is_minor`); **(3) Thank your sponsor** — a compose box that, on a `blocked` submit, shows an amber banner naming the
  identifying fields the scan caught ("your name, your town or city") so the student edits + resends, then a status chip
  ("Awaiting review" → "Shared with your sponsor"). **Sponsor `/sponsor`** gains a "Messages from students you
  supported" section — the staff-approved notes, each shown anonymously against the student's `ref` only (never identity,
  never a reply channel); 404s while the flag is off so it stays dark. New api-client functions
  `getSemesterResults`/`addSemesterResult`, `getPromotionalConsent`/`setPromotionalConsent`,
  `getGraduationMessages`/`submitGraduationMessage`, `getSponsorGraduationMessages` + types. Trilingual
  `scholarship.inProgramme.*` + `sponsorPortal.graduationMessages.*` (i18n parity 2399 ×en/ms/ta, +48; Tamil first-draft,
  TD-105). `next build` clean (`/scholarship/in-programme` 2.9 kB); 283 jest (render-only pages). TD-104 (optional
  results-slip upload control deferred — CGPA is the driver). Retro `docs/retrospective-sprint10-in-programme-frontend.md`.
- **Student in-programme results + progress + graduation relay — backend (B40 Phase E/F Sprint 9, F9a, held local, ships
  dark; migration `0053`).** The in-programme student lifecycle, backend-only. New module `apps/scholarship/in_programme.py`
  owns the writes (one-way import `in_programme → pool → models`, no cycle). **(1) Semester results → real progress.** New
  `SemesterResult` model (application, semester, cgpa 0.00–4.00, graduated, optional myNADI-only `results_slip` link);
  `record_semester_result` gates on `status='sponsored'` (400 `not_in_programme`) + validates CGPA (400 `bad_cgpa`).
  **`pool.derive_progress_state` is now REAL** — derived from the latest `SemesterResult` (graduated → `graduated`; CGPA
  ≤ 2.00 → `needs_attention`; a CGPA → `semester_completed`; else `on_track`), the single source of truth (no stored
  column to drift). The slip stays myNADI-only; only the coarse band crosses. **(2) 18+-only promotional consent.** New
  `promotional_use` consent via `grant_promotional_consent` — a hard server-side 18+ gate (`is_minor` → 400
  `minor_not_allowed`), **no guardian path** by design; `CONSENT_VERSION` bumped `2026-draft-4` → `2026-draft-5`.
  Withdrawable (PDPA). **(3) Graduation thank-you relay (scan → staff-approve → anonymous).** New `GraduationMessage`
  model; `submit_graduation_message` runs `pool.scan_anon_for_identifiers` as a STRUCTURAL gate — a message leaking the
  student's own name/school/city/NRIC/phone/email is saved `blocked` with the offending fields (edit + resubmit), a clean
  one is `pending`; staff approve (re-scanning any `scrubbed_text` edit → 400 `scrubbed_leak`) or reject. An approved
  message surfaces to the funding sponsor via a plain allowlist `GraduationRelaySerializer` ({ref, text, approved_at}),
  linked ONLY to the anonymous `pool.pool_ref` — never the student's identity, never a reply channel. Endpoints: student
  `GET/POST .../semester-results/`, `GET/POST/DELETE .../promotional-consent/`, `GET/POST .../graduation-message/`; admin
  `GET /admin/graduation-messages/` + `POST .../<id>/review/` (reviewer/super); sponsor `GET /sponsor/graduation-messages/`
  (behind `SPONSOR_POOL_ENABLED` + approved). **+26 scholarship pytest** (service gates, 18+ enforcement, relay
  leak-block + endpoint smokes; the S8 `TestProgressState` extended with the real bands). **Migration `0053`** (two new
  models → apply via MCP + contenttypes workaround + RLS at deploy, TD-102). No FE this sprint (F9b/Sprint 10). TD-103
  (results-slip OCR auto-fill deferred — CGPA is student-entered). Retro `docs/retrospective-sprint9-in-programme.md`.
- **Sponsor profile + "My students" (B40 Phase E/F Sprint 8, F2, held local, ships dark).** A signed-in, approved
  sponsor's `/sponsor` home now shows the anonymised students their giving supports + a coarse progress signal. New
  **`progress_state`** on the allowlist card (`SponsorPoolCardSerializer`) — `pool.derive_progress_state` is a stub
  (null until the student is `sponsored`, then `on_track`; the real band, from semester results, lands in F9a/Sprint 9)
  and is non-identifying, so it flows safely through the existing wallet/sponsorship endpoints. FE: a "My students"
  view extending the approved `/sponsor` portal — an account + giving-balance header, then a grid of anonymised student
  cards (alias · state · field · academic · award) with a colour-coded progress badge (green on-track / blue
  semester-completed / amber needs-attention / indigo graduated), plus an "awaiting acceptance" card for an unaccepted
  offer. `getSponsorWallet` client + `SponsorWallet`/`SponsorSponsorship` types; trilingual `sponsorPortal.myStudents.*`.
  Stitch-approved (`Sponsor Dashboard — My Students`). **No migration** (`progress_state` is derived). +3 tests incl. the
  allowlist leak test (1960 backend pytest; 283 jest; `next build` clean; i18n parity 2351). Behind `SPONSOR_POOL_ENABLED`
  (wallet 404s while off → the section simply doesn't render). Ships in the held Phase E/F batch (no push).
- **Reviewer assignment / reassignment (B40 Phase E/F Sprint 7, F7, held local).** A super admin assigns a submitted
  application to a reviewer, reassigns it, or unassigns — via a new **super-only, audited** `POST
  /api/v1/admin/scholarship/applications/<id>/assign/` (body `{reviewer_id}`; `null` = unassign). `services.assign_reviewer`
  validates the target is an active reviewer/super (never a viewer → `not_reviewer`), gates the **first** assignment of
  an unassigned app on `is_ready_for_assignment` (no open queries **or** the SLA lapsed → else `not_ready`), allows a
  reassignment/unassignment any time, and writes an **`AssignmentEvent`** audit row (from → to, by-whom) on every change;
  adds `ScholarshipApplication.assigned_at`. The loose reviewer-gated `PATCH assigned_to` branch is **removed** (single
  audited path). Cockpit "Assign a reviewer" card is now super-only, lists only reviewers, disables the first assignment
  with a reason until the app is ready, shows the current assignee, and surfaces the server error codes. Trilingual
  `admin.scholarship.assign.*`. **Migration `0052`** (`assigned_at` + new `AssignmentEvent` model). +18 tests (1945
  backend pytest; 276 jest; `next build` clean; i18n parity 2338). Ships in the held Phase E/F batch (no push).
- **Reviewer invite role selector (B40 Phase E/F Sprint 6, F5, held local).** A super admin now picks the new admin's
  role at invite time — `AdminInviteView` accepts `role` (`super`/`reviewer`/`viewer`; defaults to `reviewer`, an
  invalid value falls back to `reviewer`) and keeps the legacy `is_super_admin` flag in lockstep when `role=super`;
  `AdminListView` returns each admin's effective role. The `/admin/invite` page gains a role `<select>` + a one-line
  hint per role, and the admin-list table gains a colour-coded role badge column. Trilingual `admin.role.*` /
  `admin.roleHint.*`. No migration (the `PartnerAdmin.role` field already existed). +7 tests (1936 backend pytest; 276
  jest; `next build` clean; i18n parity 2333). Ships in the held Phase E/F batch (no push).
- **Reviewer profile (B40 Phase E/F Sprint 5, F6, held local).** A reviewer can record their own credentials +
  contact details, surfaced as new cards on the existing `/admin/profile` page (rendered only for `reviewer`/`super`;
  a `viewer` never sees them). New `ReviewerProfile` model in `apps/scholarship` — a OneToOne to `courses.PartnerAdmin`
  (mirroring the app's existing cross-app FK to `courses`) holding `highest_qualification`, `university`,
  `graduation_year`, `field_of_study`, and the sensitive staff PII `phone`/`address`; **no password field** (auth is
  Supabase's). Self-scoped `GET/PATCH /api/v1/admin/reviewer-profile/` (always the calling admin's own row — one
  reviewer can never read or edit another's) with its own narrow `ReviewerProfileSerializer`. The PII lives in its own
  table (`reviewer_profiles`, own RLS at deploy) and is reachable by **no** outward student/sponsor serializer.
  Frontend: `getReviewerProfile`/`updateReviewerProfile` + a role-gated two-card section ("Reviewer credentials" +
  "Contact details 🔒") saved by the page's single Save button; trilingual `admin.reviewer.*` (Tamil first-draft,
  TD-097). **Migration `0051`** (new model — apply via MCP + enable RLS at deploy, TD-098). Stitch-approved
  (`My profile — Reviewer Settings`). +10 tests (892 scholarship pytest; 276 jest; `next build` clean; i18n parity
  2325). Ships in the held Phase E/F batch (no push).
- **Sponsor notifications — real-time + weekly digest (B40 Phase E/F Sprint 4, F3, ships dark).** A sponsor chooses how
  often they hear about newly-published anonymised students: `realtime` (an hourly-batched alert), `weekly` (a digest),
  or `off` — `Sponsor.notify_frequency` (default `weekly`) set via `PATCH /api/v1/sponsor/notifications/` and a
  preference toggle on `/sponsor` (trilingual). New `sponsor_notifications` service + two management commands
  (`send_sponsor_realtime` hourly, `send_sponsor_digests` weekly) registered in `CronRunView.JOBS`; the publish view
  resets `SponsorProfile.realtime_notified_at` so a (re)published student is alerted exactly once, and each sponsor's
  `last_digest_sent_at` advances so a digest never repeats. **Email bodies are built only from
  `SponsorPoolDetailSerializer` dicts — allowlist-safe by construction** (no student identity can reach a sponsor); a
  soft `SPONSOR_NOTIFY_MAX_PER_RUN` cap keeps a run inside the Brevo quota. Migration **`0050`** (3 additive fields).
  +9 tests (882 scholarship pytest; 276 jest; `next build` clean). Cloud Scheduler jobs to be created at deploy
  (TD-095). Retro `docs/retrospective-sprint4-sponsor-notifications.md`.
- **Student award + onboarding — frontend (B40 Phase E/F Sprint 3, F8b, ships dark).** New `/scholarship/award` page
  (accept or decline a funded-studies offer; a guardian modal for minors reusing the consent relationship list +
  `formatNric`) and `/scholarship/onboarding` wizard (welcome acknowledgement cards → a short questionnaire → a
  confirmation that auto-submits via `submitOnboarding`). The sponsor's identity is never shown — the student sees only
  the amount + accept-by date. New `getStudentAward`/`respondToAward`/`submitOnboarding` API clients + `onboarded_at` on
  the application type; an "accept your award / complete onboarding" panel on `/scholarship/application` that appears
  only when an offer exists and disappears once onboarded. Trilingual `scholarship.award.*`/`scholarship.onboarding.*`
  (Tamil first-draft, owner to refine). `next build` clean; 276 jest green. Naturally dark — no award offer exists until
  a sponsor funds a student, which requires `SPONSOR_POOL_ENABLED`. Built by a delegated subagent, orchestrator-reviewed
  + re-built. Retro `docs/retrospective-sprint3-onboarding-frontend.md`.
- **Student post-match onboarding — backend (B40 Phase E/F Sprint 2, F8a, ships dark).** When a student/guardian
  accepts an award (`respond_to_award`), they now receive a trilingual **award-confirmed email** that carries **no
  sponsor identity** (B4 two-way anonymity) and points them to onboarding. New `complete_onboarding(...)` service +
  `POST /api/v1/scholarship/applications/<id>/onboarding-complete/`: records a new `student_onboarding_ack` consent
  (`granted_by='self'`; bumped `CONSENT_VERSION` → `2026-draft-4`), stores the questionnaire on a new
  **`OnboardingResponse`** model (one per application, JSON answers, audit trail), and stamps a new
  `ScholarshipApplication.onboarded_at` — the hard gate before any first disbursement. Onboarding is refused until the
  award is accepted (status `sponsored`, else `400 not_awarded`). `onboarded_at` surfaced in `ApplicationReadSerializer`.
  Migration **`0049`** (additive: `onboarded_at` column + `onboarding_responses` table) — apply migrate-first at deploy;
  the new table needs RLS enabled at deploy (TD-093). +5 tests (873 scholarship pytest). Retro
  `docs/retrospective-sprint2-onboarding-backend.md`.
- **Sponsor landing page + live "students waiting" counter (B40 Phase E/F Sprint 1, F1, ships dark).** A public,
  persuasive marketing page for prospective sponsors at `/sponsor` (shown to signed-out visitors only while the
  programme is live): hero with a live counter, three promise cards (complete anonymity / every ringgit tracked /
  real verified impact), a four-step "how it works", an FAQ, and a closing call-to-action — all trilingual
  (`sponsorLanding.*`, en/ms/ta, 40 keys each). New public endpoint `GET /api/v1/sponsor/pool/count/` →
  `{count, enabled}`: count-only (exposes no student data), no auth, and gated by `SPONSOR_POOL_ENABLED` — while the
  flag is off it returns `{count: 0, enabled: false}`, so signed-out visitors keep the plain sign-in card and the whole
  programme stays dark until the lawyer-gated go-live (Sprint 12). New `components/SponsorLanding.tsx` +
  `getStudentsWaitingCount()` API client; the `/sponsor` page renders the landing for signed-out visitors when enabled,
  otherwise the existing portal/auth flow is unchanged. No migration. +3 sponsor-pool tests (count hidden when flag off,
  count reflects the eligible pool when on, response leaks nothing). Tamil copy pending the owner's refinement pass.
  Prototyped in Stitch and visually approved before coding. Retro `docs/retrospective-sprint1-sponsor-landing.md`.
- **"About your family" structured roster — backend foundation (branch `feature/family-section-redesign`, NOT
  deployed).** Replaces four overlapping family fields (`first_in_family` toggle + legacy `siblings_studying_count` +
  `siblings_in_school`/`tertiary` steppers split across the Story + Income tabs + free-text `parents_occupation`) with
  one structured roster: Father/Mother (name as in IC + coded profession) + an optional brother/sister/guardian pool,
  plus two sibling steppers and a *derived* "first in family" (no toggle). `apps/scholarship/family.py` holds a
  40-option B40/lower-M40 profession taxonomy — **validated against the 33 real `parents_occupation` entries on prod,
  ~95% coverage** — and the pure derivations. 7 additive model fields + migration `0048` (additive, no data loss,
  migrate-first at deploy). `save_application_details` makes the roster the INPUT; `first_in_family` (= no sibling
  in/through tertiary) and `parents_occupation` (= roster summary) are kept correct as OUTPUTS, so every downstream
  reader (profile_engine, anomaly_engine, ledger, check2) works unchanged and the old contradiction-flag +
  clarify-email become inert-by-construction. Serializers + the admin serializer accept/expose the roster;
  `lib/familyRoster.ts` mirrors it for the (pending) form. **Compulsory** rules agreed: father/mother profession
  required (name required unless deceased/no-contact), sibling steppers required via a blank-`—` (null) default.
  +9 tests (854 scholarship pytest). **▶ Remaining (S2, not started): the form rebuild + i18n (40×3) + the
  `family_done` completeness gate + income-wizard stepper-removal/earner-prefill + cockpit Family card.** Plan:
  `docs/scholarship/family-section-redesign-plan.md`; retro `docs/retrospective-family-section-redesign.md`.
- **Sponsor allowlist widened to a trusted-sponsor boundary (B40 Phase E/F Sprint 0, ships dark).** Per the 2026-06-07
  owner Boundary decision, the anonymised sponsor card (`SponsorPoolCardSerializer`) gains an `institution` field that
  crosses **only** to a **trusted** sponsor (`context['is_trusted']`); absent by default (fail-closed). New
  `Sponsor.is_trusted` (BooleanField, default True; migration `0043`, additive). The anon-blurb prompt is coarsened
  (quasi-identifier guard). Leak tests extended: parent identifiers never cross; institution absent-for-non-trusted /
  present-for-trusted. Reads only under `SPONSOR_POOL_ENABLED` (off) — no user-visible change.
- **Check 2 — submission review → queries → SLA → claim-gated profile (Sprints 2–5).** The post-submit pipeline that
  turns a raw application into a sponsor-ready profile without ever asserting an unverified claim
  (`docs/scholarship/check2-design.md`). **STEP 1 — facts ledger** (`submission_review.py`): on submit, a deterministic
  ledger of every assertable claim tagged with how well the verification layer backs it (verified / reported /
  student_words / unverified), plus fundable-profile completeness gaps and consistency flags. **No LLM** — verification
  is the deterministic layer's call. Exposed read-only on the admin serializer. **STEP 2 — clarify queries** (model:
  `ResolutionItem.kind` += `clarify`/`human`, `source` += `check2`, migration 0045; `check2_queries.py`): factual,
  one-line, non-sensitive completeness gaps (course / sibling level / device / transport — *not* motivation) become a
  capped (≤3, most-material-first) student query stream on the existing Action Centre; idempotent, auto-resolves when the
  gap clears, never re-asks an answered query; `human` items stay reviewer-only. The student answers by text; the officer
  sees the queries in their resolution queue. **STEP 2/3 — the 5-day SLA clock** (`ScholarshipCohort.query_response_sla_days`
  default 5, `ScholarshipApplication.query_reminder_at`, migration 0046): `is_ready_for_assignment` = no open clarify
  queries OR the window lapsed (proceed-as-is, flagged); a daily `send_query_reminders` sweep nudges open-query students
  once ~2 days before the deadline (new trilingual email + `query-reminders` cron); the cockpit shows the clock
  (`query_sla`: deadline / lapsed / days_left / ready / proceeding-with-open-queries). **STEP 3 — claim-gated generation**
  (`profile_engine.py`): both profile prompts now feed the facts ledger and assert only verified claims — the
  first-to-university claim is gated on the sibling split (else *"not established — do not claim"*), killing the live
  "first-generation" over-claim bug; a tone guardrail bans hardship-mining clichés, requires the real grade band mix, and
  forbids invented specifics; `generate_ready_profile` (shared by the admin action) + a flag-gated
  (`CHECK2_AUTO_GENERATE`, default off) `autogenerate_ready_profiles` sweep + cron draft the profile once an application
  is ready. The structural dual-profile *retirement* (merge anon/named storage; final redaction wording) is deferred to
  the award-stage alignment (design Q4) + cross-agent coordination. Gates: 826 scholarship pytest + 274 jest + next build
  clean; i18n parity 2105; migrations through 0046 (renumbered above the sponsor branch's 0043).
- **Check 2 — Sprint 1 prerequisites (P1–P3): the submission review can now "use all the information".** Three small,
  independent backend fixes so the upcoming Check‑2 submission review (`docs/scholarship/check2-design.md`) reads every
  signal the form already captures. **P1 — read the letter of intent.** The `statement_of_intent` was uploaded and
  **never OCR'd**; it now routes through a new `vision.read_text_document` (plain‑text OCR → `vision_fields['text']`,
  `student_verdict:'read'`) on upload and on the admin **re‑run‑vision** action — making the student's motivation in her
  own words available downstream. New `TEXT_READ_DOC_TYPES`. Soft, never blocks. **P2 — the sibling school/tertiary
  split is authoritative.** The income wizard's `siblings_in_school` / `siblings_in_tertiary` counters now drive the
  *first‑to‑university* check instead of the legacy combined `siblings_studying_count`: a sibling in **tertiary** is a
  genuine contradiction (flag), but siblings only in **school** no longer falsely contradict the claim — it
  **auto‑resolves** (`_sibling_tertiary_count` helper). Migration `0044` backfills the unambiguous legacy‑0 case (data
  only, no schema change); both counts now show in the officer cockpit (admin serializer + FE + en/ms/ta). **P3 —
  utility‑spend‑high‑vs‑income reviewer flag.** A new deterministic anomaly fires when utility bills exceed ~20% of the
  declared monthly household income, carrying the actual numbers (RM bills / RM income / %) so the reviewer can ask how a
  low‑income household sustains the spend — soft, never a gate (`utility_monthly_total` + `_detect_utility_high_vs_income`
  + i18n). 785 scholarship pytest + 274 jest + next build clean; i18n parity 2097.
- **Post‑consent "Review & submit" page (lock‑at‑Continue).** A new **post‑consent page** in the shortlisted application
  flow (reached via a **"Review & submit"** CTA after the 5 wizard steps — **not** a navigable tab) shows the student a
  read‑only recap of everything they entered before they commit, in seven sections: **About you**
  (identity + the non‑editable household facts: income, size, STR, JKM) · **Your results** · **Your story** (family
  narrative + address + the story narrative) · **Funding** (chosen study + programme length + support) · **Household
  income** (the income‑wizard route/earner) · **Documents** (a simple "✓ Uploaded" list) · **Consent** — with per‑section
  **Edit** links that jump back to the relevant step (Household income jumps straight to the income wizard). The **Submit application** button now lives here and is the *only* commit
  (`confirmScholarshipApplication`); the consent step's CTA becomes **"Review & submit →"** and no longer submits. Built
  from data already on the client (the application + the student profile + `listDocuments` + `getConsentStatus`) — **no
  backend change, no migration**. New `ScholarshipReview.tsx`; the 5 wizard steps stay in `NEXT_STEP_ORDER` while Review
  is a separate post‑consent page; `scholarship.summary.*` i18n in en/ms/ta. Visual approved via an in‑code mockup (Stitch
  generation timed out on the dense page). 267 jest + next build clean; i18n parity 2073 (since raised — see below).
- **Review & submit flow — live‑testing refinements (5 commits `1cc5f65`→`a533637`, FE‑only, no migration).**
  (1) Review became a **post‑consent page** rather than a 6th navigable tab — `NEXT_STEP_ORDER` reverts to the 5 wizard
  steps; the page is reached only via the **"Review & submit"** CTA after consent, Back returns to the steps, Submit there
  is the only commit (`handleConfirm` hands the updated application up to the parent via `onSubmitted`, which renders the
  post‑submit "received" screen — no page reload; resolves TD‑090 within the same cycle). (2) The **Consent step is read‑only once
  given** — the dead‑end Edit link is gone; instead it now shows the **full consent text read‑only** plus who gave it and
  when (`givenHeading`/`givenMetaSelf`/`givenMetaGuardian`). (3) The step counter is **dynamic** ("Step n of {total}").
  (4) **"What happens next"** moved off the pre‑submit wizard to the **post‑submit "received" screen**, and now reads
  review → **email query** (we may ask for more documents/clarification — Check 2 / reviewer, by email) → **may‑call** →
  decision; the doubled email note was de‑duped (`nav({email})`). (5) Submit‑flow copy made **consistent on "submit"**
  across the "all set" banner, the review subtitle (now with a scroll cue), and the button; the banner no longer says
  "submit for review" (it opens the student's own read‑back, not a third‑party review); the lock note reworded so it no
  longer implies editing reopens after contact. (6) De‑duped the doubled "Your application" title on the Review page.
  267 jest + next build clean; i18n parity 2084.

### Fixed
- **"Your story" save silently failing for students who wrote a real answer (prod incident, app #30).** The
  "What do your parents or guardians do for a living?" field (`parents_occupation`) was a `varchar(255)` column with **no
  length guard on the web form or the API** — a student writing a sentence or two (e.g. "My mother is a Grab driver and
  the sole breadwinner…") overflowed 255 chars, the DB raised `value too long for type character varying(255)`, and
  (under atomic requests) the **entire Story save rolled back** — narrative, funding and address included — surfacing only
  as the generic *"Could not save your details. Please try again."* **Fix:** `parents_occupation` is now a `TextField`
  (migration `0042`, backward‑compatible widening); every free‑text Story field gains a generous **anti‑spam cap**
  (`STORY_TEXT_MAX = 5000` ≈ ~900 words) enforced on both the web form (`maxLength`, so over‑long input is stopped at the
  keyboard) and the API serializer (clean `400` instead of a DB rollback). The `parents_occupation` input became a small
  textarea (it always held a sentence). Also closed the same latent trap on the address **city** field (`varchar(100)`):
  capped at 100 on the form + serializer. +2 regression tests (long answer now saves; over‑cap is a clean 400).
- **Actionable "too long" message instead of the generic save error.** When a Story/Funding answer is rejected for
  length, the student now sees *"Your answer to "{question}" is too long. Please shorten it and try again."* (en/ms/ta)
  naming the exact question — not the blanket "Could not save your details". The API client now carries DRF
  field‑level validation errors through to the caller (`err.fieldErrors`); a pure `firstTooLongField()` helper walks the
  (possibly nested) error body and a `STORY_FIELD_LABEL_KEYS` map resolves the field → its question label. Also gave the
  Funding **"Anything else about funding"** note (`funding_note`) the same `STORY_TEXT_MAX` anti‑spam cap (form +
  serializer) for consistency — completing the audit of every student‑typed Story/Funding field. +5 tests
  (`firstTooLongField` ×4, funding_note over‑cap 400 ×1); i18n parity 2089.
- **Same length‑trap audit + fix on the /apply form.** Two genuine rollback risks found: **name** and **school** —
  both free‑text (school is a type‑your‑own combobox) writing to `StudentProfile` `varchar(255)` columns via
  `sync_profile_fields` → `setattr` → `save` with **no validation** (the application's own fields were already protected
  because `ApplicationCreateSerializer` is a *ModelSerializer* that derives `max_length` from the model, but the
  write‑only profile fields were declared as plain `CharField` with no `max_length`). **Fix:** `name`/`school`/
  `contact_phone`/`preferred_state`/`preferred_call_language`/`referral_source` now carry `max_length` matching their
  profile columns, so an over‑long value is a clean field‑400, never a DB‑overflow rollback. Web form: `maxLength` on the
  name (255), school combobox (255 via a new `SchoolSelect` prop), parent name (255), declaration signature (200),
  other‑scholarships note (300), and the two free‑text plan/support boxes (5000 anti‑spam). The apply submit now shows the
  same actionable *"Your answer to "{question}" is too long…"* message (via `firstTooLongField` + `APPLY_FIELD_LABEL_KEYS`)
  instead of the blanket "Something went wrong". (`contact_phone` was already safe — `formatPhone` caps to 11 digits; the
  state/org/language dropdowns can't overflow.) +3 tests; i18n parity 2090. No migration.

### Removed
- **Orphaned `str_claimed_no_doc` anomaly rule.** The pre‑interview flag "student says the family receives STR but
  hasn't uploaded the letter" is superseded by the income wizard, which now *requires* the STR document on the STR route
  (consent gate v2). Removed the detector + its `_DETECTORS` registration, the `resolution.py` ticket mapping, the
  `actionCentre` known‑code, and its i18n in all three namespaces ×3 languages; tests updated. No migration.

### Changed
- **Documents — removed the redundant "Vision OCR (soft signal)" + "Parent/guardian IC (Vision OCR)" blocks.** They
  were legacy display (S13/S17) that the cockpit now reproduces everywhere else: the NRIC/Name match pills duplicated the
  IDENTITY document row's green "Name · IC No" labels (same `vision_*_verdict` fields), the "Re-run Vision" button
  duplicated each row's own Re-run (same `doReRunVision(doc.id)` call), and any real mismatch already surfaces as a flag
  in Outstanding (`address_state_mismatch`, `declaration_name_mismatch`). FE-only; the OCR data + per-doc Re-run are
  unchanged. i18n parity 2137.
- **Decision panel — removed the whole Verify-&-accept step; "Save verdict" is now the single accept.** Per owner
  review: the programme does not re-verify the IC here — identity is already verified at the **consent gate**
  (`services` IC check: `nric_match`, blocks `ic_nric_mismatch`), and the NRIC is locked to the student by then, so a
  second verify-and-lock step was redundant. The separate "Verify & accept" button + the dead "Log phone-call outcome"
  tool are gone. **Save verdict & generate final profile** now accepts the applicant in one click when Identity = Pass,
  nothing is failed, and the profile is complete (the button relabels to "Save verdict & accept"); the right-hand area
  shows just the accepted record + the Decline path. FE-only — reuses the existing accept endpoint (status → accepted;
  the NRIC `verified` flag is still set as silent plumbing for uniqueness + to stop post-accept edits, no manual step,
  nothing re-checked). i18n parity 2137.
- **Decision panel — dropped the redundant Verify-&-accept checklist + the mentoring toggle.** The 4 MyKad
  checkboxes (NRIC / name / results / MyKad-clear) only re-asked what the four-fact verdict audit above already
  captures — NRIC + name are OCR-verified deterministically (the Identity fact), and the slip is the Academic fact +
  `completeness`. Accept is now gated on a **complete profile + a recorded verdict** (the backend already required
  `verdict_decided_at`; the FE button now reflects it, with a "Record your verdict above to enable accept" hint), so a
  reviewer makes one judgement, recorded once — no manual re-confirmation. The "Flag for mentoring" toggle was removed
  from the panel (the `mentoring_candidate` field is retained on the model). FE-only; no backend/migration change
  (`verify_checklist` simply stores empty now — the decision lives in `officer_verdict` + reason). i18n parity 2135.
- **Officer cockpit consolidated — ~11 action panels → ~7, two clean columns** (`feature/cockpit-consolidation`;
  spec `docs/scholarship/cockpit-consolidation-plan.md`; retro `docs/retrospective-cockpit-consolidation.md`; Stitch
  mockup approved). No more overlapping/duplicated questions. **Outstanding** is one panel = Caveats + Pre-interview
  flags, split into "Student to-do" (Resolve/Ask) vs "Ask at interview" (deterministic flags + AI gaps); identity
  `vision_nric_mismatch`/`vision_name_mismatch` are **deduped server-side** (`get_anomalies`) since the verdict tile +
  identity caveat own them. **Decision** is one panel = the four-fact verdict audit + Verify-&-accept, with the
  audit→accept gate preserved verbatim (accept stays gated on a complete profile + every checklist box; NRIC lock
  intact). The IC/parent-IC **OCR display moved into Documents**; the **Consent** panel was removed (the consent record
  + sponsor-share gating are untouched). The student's raw **Note/Story/Funding** now collapse behind a "Show the
  student's own words" reveal under the Sponsor profile (factual About cards stay visible). **Estimated need** sits at
  the top of the right column beside **Decision**; **Assign a reviewer** sits below it (reviewer/super only —
  viewer-hidden). Left column order: Verdict · Profile · Outstanding · Interview · Documents. FE + one additive
  serializer filter (+ test); **no migration**. Gates: next build clean, 276 jest, 845 scholarship pytest, i18n parity
  2134.
- **Income with no information yet reads 🔴 Can't verify, not 🟡 Unsure** — consistency with the other facts, where
  "nothing provided" is always red (no IC / no slip / no offer). A not‑walked income wizard (STR route, no earner/route)
  or no working member declared (salary route) now returns `gap` instead of `review`. The 🟡 cases stay as they should:
  income the engine can't document‑prove (informal/no‑EPF, an unprovable relationship, or salary *above* the B40 line)
  is `recommend` → the officer places it at interview. Backend‑only, no migration; verdict tests updated; 766 scholarship.
- **Two facts now hard‑stop weak evidence instead of passing it to manual review** (policy: don't pass a student we
  can't actually support — re‑upload beats us struggling with unusable documents).
  - **(1) A results slip in a different name is a hard stop.** A positive slip‑name **mismatch** now makes Academic
    🔴 **Can't verify** *and* fails the submission bar (`documents_done`) — the student must re‑upload the correct slip.
    Matching grades on someone else's slip can't be credited to the student; the slip's name is its ownership anchor.
    ('pending' / 'unreadable' / 'match' still pass the gate — only a positive mismatch blocks.)
  - **(2) No offer letter → Pathway 🔴 Can't verify.** The offer letter was already a submission blocker
    (`offer_letter_missing` in `consent_blockers`); the **verdict** now reflects it — a pathway with no offer reads red,
    not amber/blue. We support a *confirmed place*: income can be settled at interview, a pathway cannot. New
    `offer_letter_missing` verdict item + Action Centre re‑upload ticket + `CODE_TO_TICKET` mapping (en/ms/ta).
  Backend + i18n; no migration. 766 scholarship pytest + 274 jest + next build clean.
- **"Probable" (blue) now requires a verified value — a fact with nothing green reads "Unsure" (amber), not "Probable".**
  A self‑declared pathway (no offer letter yet) and an un‑walked income wizard were showing 🔵 Probable despite **zero
  verified evidence** (seen on a bare application). `factTileTone` now takes the whole fact: a `review` fact is blue only
  when it has **≥1 genuinely‑verified** evidence item; backed only by a declaration (`pathway_declared`) or a soft signal
  (utility per‑capita / hardship) — or by nothing — it drops to 🟡 **Unsure**. `verified`→green, `recommend`→amber,
  `gap`→red unchanged. FE‑only, no migration; 270 jest + next build clean.
- **Verdict tiles now read as a confidence scale (Kent's words of estimative probability).** Each tile shows the
  estimative word it stands for, with a legend under the row, on a collapsed 4‑band scale: 🟢 **Certain** (`verified`) ·
  🔵 **Probable** (`review` — likely sound, confirm the one flag) · 🟡 **Unsure** (`recommend` — even odds; the
  coordinator places the verdict, e.g. salary‑route B40) · 🔴 **Can't verify** (`gap` — missing/unreadable). **Blue and
  amber swapped** from before so colour temperature tracks certainty: blue is the higher‑confidence "probable" band,
  amber the "unsure / your call" band (amber reads as caution). `factTileTone`: review→blue, recommend→amber; new
  `TONE_BAND_KEY` + `admin.scholarship.verdict.band.*` i18n (en/ms/ta). FE‑only, no migration; 268 jest + build clean;
  i18n parity 2088.
- **Officer cockpit polish (live testing).** (1) The **Documents** drawer is now fixed‑height with a vertical scrollbar
  (`max-h-[28rem] overflow-y-auto`) — a long list (11+) no longer pushes the rest of the cockpit down; the header stays
  put and the groups scroll. (2) The **Pre‑interview flags** card moved to sit **just below "Caveats to resolve"** — the
  two belong together (caveats are things to resolve, flags are questions worth asking at interview). (3) **Referees**
  capture is hidden for now (`SHOW_REFEREES = false`; the add/delete handlers stay wired so it's a one‑line re‑enable and
  nothing goes unused); the **Consent** status in that card stays visible. Pure layout/JSX in
  `admin/scholarship/[id]/page.tsx`; no logic or data change.
- **Officer cockpit reordered — "About the student" now sits above "Review & actions".** The reviewer reads the
  applicant's facts (About · Family & finances · Academic · Support) first, then the verification verdict + action
  panels below. The sticky **"Record your verdict"** panel stays attached to the Review & actions section (bottom‑right),
  so it's beside the checks it records. Pure JSX reorder of `admin/scholarship/[id]/page.tsx` (two sibling blocks
  swapped); no logic/data change. Mobile order: About → Review → verdict panel.
- **De‑duplicated `formatNric` (TD‑088).** The two admin students pages each carried their own `formatNric`; both now use
  a single null‑safe `formatNricDisplay()` in `lib/scholarship.ts` (returns an em‑dash for a missing IC). FE‑only.
- **Cikgu Gopal (income cluster) — two live‑testing refinements.** (1) **Salary‑route sequencing:** once the earner's IC
  is in and matches, Gopal now nudges the **salary slip** (the income proof) as the logical next step before the birth
  certificate — previously it jumped straight to the BC and never mentioned the slip (new `income_proof_needed` verdict,
  placed before the relationship‑doc check on the salary route). (2) **Mother‑route mismatch message:** when the
  relationship check clashes on the **mother** route, the message now points at the **birth certificate ↔ MyKad**
  mismatch (and leans toward re‑checking the birth certificate, since the IC usually already matches the income document)
  rather than the father‑route "re‑upload the MyKad". The cluster help view passes the relationship‑doc label into the
  mismatch + proof messages so the coach names the real document. **(2b)** When the earner's MyKad is *already corroborated*
  by their income document, the mismatch message now commits — *"your mother's MyKad is confirmed by her salary slip, so
  the birth certificate is the one to re‑check"* — instead of still hedging "double‑check the MyKad" (the view passes an
  `ic_matches_income_doc` flag into the coach context). No migration; 771 scholarship pytest + 267 jest + build clean;
  i18n parity 2027.
- **An STR now only counts as B40 proof when it shows it was APPROVED and current — a self‑filled application record
  (SALINAN) no longer auto‑passes.** Previously the STR currency check was "valid unless clearly rejected", so a status‑less
  SALINAN/printout (which any applicant can generate) was given the benefit of the doubt and marked `current` → income
  verified. It now requires a positive approval signal (`Lulus` / `Diluluskan` / SARA `Layak`) **and** a readable current
  year; anything else — no approval shown, or approval we can't tie to a current year — is a new **`unconfirmed`** state.
  An `unconfirmed` STR no longer verifies income: Check‑1 raises the `str_not_current` caveat and Cikgu Gopal asks the
  student to upload proof of approval — *"a MySTR 'Semakan Status' screenshot showing your parent's name, their IC, the
  status 'Lulus', and the payment dates; or your official STR approval letter"* (or switch to the salary route). The STR
  document chip shows an amber "Approval not shown" instead of a green "Current". The consent gate is unchanged
  (presence‑based, by design) — the student can still submit, but the caveat now travels with the application for the
  officer/reviewer. No migration; 766 scholarship pytest + 267 jest + build clean; i18n parity 2026.

### Fixed
- **Identity verdict no longer goes amber on an IC registered‑address state difference (a false yellow).** A MyKad shows
  the *registered* state (e.g. KEDAH), which is the **least‑current** address on file — people relocate and the IC isn't
  reissued; fresher addresses come from the offer letter / bills / STR — and it is **not an identity key** (name + NRIC
  are). `_verdict_identity` was folding `address_state_mismatch` into the identity fact's `unresolved`, flipping it to
  `review` (amber) even with name + NRIC both matched — contradicting the Documents panel (green) and the student's own IC
  card (address shown as a neutral "from your IC"). Identity now reads `verified` (green) when name + NRIC match; the state
  difference stays a **pre‑interview flag** ("ask which is current", `_detect_address_state_mismatch`) — its proper home —
  and is no longer a "Caveat to resolve" (removed the address append from the verdict + its now‑dead `CODE_TO_TICKET`
  entry). Identity still **never auto‑fails**: name/NRIC mismatches are amber‑to‑confirm, red is reserved for a
  missing/unreadable IC. Backend‑only, no migration; verdict + resolution tests updated; 762 scholarship pytest.
- **Academic "fix this" tickets now open the grades editor, not the Documents tab (TD‑082).** A student Action Centre
  `confirm` ticket on an academic fact (`academic_missing_subjects` — "add Moral + Tamil Literature" — or
  `academic_grade_mismatch`) sent the student to **Documents**, which is for *uploading files*, not editing entered
  subjects/grades (those live in the onboarding grades flow; `/application` has no grades surface). `confirmTargetFor`
  now routes academic facts to a new `'grades'` target, while the results **slip** (a document) stays on Documents;
  `handleConfirmNav` deep‑links the grades case to `/onboarding/grades` with a return marker
  (`setOnboardingReturn('/scholarship/application')`) so the onboarding final step brings the student back to
  `/application` (new `popOnboardingReturn`; grades rehydrate from the profile via auth‑context, so the editor isn't
  blank). FE‑only, no migration; actionCentre test updated (academic→grades, slip→documents). 268 jest + build clean.
- **Completion reminders now land on the named day, not a day late (TD‑087).** The cadence compared
  `floor((now − reminder_anchor_at))` in raw days against the 2/9/23/53 thresholds, but the daily job ticks at a fixed
  09:00 Asia/KL while the anchor carries the clock‑time it was set — so an afternoon anchor's R2 (+9) first crossed the
  threshold one tick late (e.g. fired 14 Jun for a 4 Jun anchor, not 13). Now compares **calendar dates in Asia/KL**
  (new `_elapsed_days_local`) so each reminder fires on its nominal day regardless of the anchor's time‑of‑day. The
  auto‑close gate is unchanged (it compares two 09:00‑job timestamps, so it never had the slip). Backend only, no
  migration; +2 regression tests (afternoon anchor fires on calendar‑day 9; the day before does not). 762 scholarship.
- **Birth certificate no longer warns about the (always‑absent) child IC number.** A Malaysian birth certificate
  carries no "No. Kad Pengenalan" for the child — they're issued one later — yet the field‑extraction prompt asks Gemini
  to note every empty field, so it flagged *"Child's NRIC not explicitly labelled…"* as an orange warning on a perfectly
  good certificate. The BC hint now tells Gemini to leave `bc_child_nric` empty without warning, and a deterministic
  `_drop_expected_warnings` filter strips any child‑NRIC note that slips through (belt‑and‑braces). Re‑running a BC clears
  the stale warning. No migration; 762 scholarship pytest.
- **Officer cockpit: an uploaded birth certificate no longer shows as "Missing" in the income panel.** `docTypeToFact`
  mapped the parent IC / STR / salary slip / EPF / bills to the income group but omitted `birth_certificate` (and
  `guardianship_letter`), so a BC fell into "other" and the income `incomeDocLayout` never saw it — leaving a false
  "Missing" placeholder on a doc the student had actually uploaded. Both relationship docs now group with income. FE-only;
  267 jest + next build clean.
- **Birth certificates are now actually read (child + mother names) — the mother income route's relationship check
  finally works.** The BC's extraction schema existed, but `birth_certificate` was in neither `SUPPORTING_NAME_CHECK_TYPES`
  (OCR) nor `GEMINI_EXTRACT_DOC_TYPES` (field extraction), so the upload handler skipped it entirely: `bc_child_name`/
  `bc_mother_name` were *always* blank ("Child: —, Mother: —"), the mother‑relationship verdict could never confirm, and
  (downstream) the unreadable‑BC nudge could never fire. The BC is now routed through the pipeline and **always**
  field‑extracts (a new `RELATIONSHIP_DOC_TYPES` set bypasses the cost knob, since its verdict needs the structured
  fields). A guard test asserts the BC stays in all three sets. (The guardianship‑letter route has a separate, deeper gap
  — logged as TD‑089.) No migration; 761 scholarship pytest.
- **Cikgu Gopal (income cluster coach) now rides directly beneath the document the student just uploaded, and speaks
  when the birth certificate is unreadable.** Two live-testing issues on the income cluster: (1) on the STR route the
  coach was pinned to the *foot* of the cluster, which sat below the water + electricity bills — so it sank far from the
  income documents. It now anchors under the **most recently uploaded cluster document** (by `uploaded_at`) and moves
  down to the next one when another is added (new `clusterAnchorKey`/`clusterDocKey` helpers; utility bills aren't cluster
  docs so it never lands there). (2) When the relationship doc (birth certificate / guardianship letter) was uploaded but
  unreadable — unclear, or the wrong document (an IC sent as a birth cert) — `income_cluster_advice` returned nothing
  (it's neither a name *mismatch* nor a *missing* doc), so Gopal went silent. New verdict **`income_rel_doc_unreadable`**:
  once the doc is uploaded and its vision has run but the link still can't be read, Gopal asks for a clear copy of the
  correct document. No migration; 760 scholarship pytest + 266 jest + next build clean; i18n parity 2025.

### Changed
- **IC numbers now display in the canonical `XXXXXX-XX-XXXX` format everywhere they're shown.** The student
  document checklists (identity IC, income earner IC, income proof, STR recipient) and the officer review cockpit
  (header NRIC, the NRIC verify‑checklist row, and the Vision‑extracted lines on the identity + parent IC drawers)
  were rendering the raw OCR/stored digit string; they now pass it through the existing shared `formatNric()`
  (display‑only, idempotent) so every IC reads the same way. No data is mutated; the profile's privacy masking
  (`maskIc`) and the consent NRIC‑match validation are untouched, and the admin students list/detail pages already
  formatted correctly so were left as‑is. No migration; 262 jest + next build clean.
- **Income earner IC now shows whether it MATCHES the income document (the point of uploading it), and Gopal guides
  IC → birth certificate.** On the student's income cluster (e.g. an STR in the mother's name), the earner‑IC card used
  to show source labels ("from your IC") and a relationship‑pending name ("We'll review this"). It now cross‑checks the
  IC against the cluster's income proof and shows **"Matches the STR document" (green)** on the IC No + Name when they
  agree (red on a clash) — `income_engine.student_income_ic_check` gains `proof_kind`/`proof_name_status`/
  `proof_nric_status`. The **relationship to the student moves off the IC card** (it's the birth certificate's job): a new
  cluster verdict **`income_rel_doc_needed`** makes Cikgu Gopal nudge for the **birth certificate** (mother) / guardianship
  letter (guardian) as the last step once the IC is in, then go silent. The income coach copy is fixed too — it was a
  hardcoded **"father's payslip / not blocked"** example regardless of the actual earner; the cluster coach now passes
  non‑sensitive **member + document specifics** so it names the real earner + doc ("your **mother's** MyKad alongside her
  **STR document**"), and is honest that these compulsory income docs **are required** under gate v2 (no more false
  "nothing's blocked"). Earner‑IC labels also corrected "from **your** IC" → "from **their** IC". 758 scholarship pytest +
  262 jest + next build clean; no migration; i18n parity 2024.

### Added
- **Application completion reminders + auto-close (the daily reminder job).** Shortlisted students who haven't completed
  their application now get an escalating reminder sequence, and stalled applications are eventually closed. Cadence (days
  from `reminder_anchor_at`, normally = the shortlist invitation): **R1 +2 · R2 +9 · R3 +23 · R4/final +53**, where the
  final reminder warns *"complete within 5 days or we'll close it; you'd need to start a new application."* Then a 5-day
  grace and **auto-close** → new `expired` status. The 55‑min/48‑h initial reveal was already live (cohort delays). New
  `ScholarshipApplication` fields `reminder_anchor_at` / `reminder_stage` / `last_reminder_at` / `expired_at` + the
  `expired` status (**migration `0041`**, additive columns + the per‑cohort/profile unique constraint made **partial** so an
  `expired` row never blocks a fresh application — students may restart). `services.send_application_reminders` (idempotent,
  one stage per run, close gated on the final reminder having actually gone out ≥5 days earlier — never on raw elapsed
  days); 5 new trilingual emails (R1–R4 + closure), each linking to `/scholarship/application`; new
  `send_application_reminders` management command wired into the cron whitelist (`application-reminders`); each reminder
  also points the student to the built-in AI helper (**Cikgu Gopal**) and a human fallback (`tamiliam@gmail.com`); one-time
  `backfill_reminder_anchors` command (anchors the existing shortlisted‑incomplete cohort to *today − 2 days* so R1 fires
  on the first run). Needs a new daily Cloud Scheduler (~9am Asia/KL). 753 scholarship + 1037 courses/reports pytest.

### Changed
- **Cikgu Gopal for income — one coach per earner, anchored at the cluster foot, aware of the whole cluster.** Income is
  the one *cluster* fact (the earner's IC + STR / payslip + relationship doc), unlike the single-document Identity /
  Academic / Pathway. Gopal now speaks **once per earner** — pinned to the foot of the cluster (after the relationship‑proof
  card: father → IC, mother → birth certificate, guardian → guardianship letter; per ticked member on the salary route) —
  instead of one nudge per file. It reads the whole cluster and **fires even before the IC is uploaded**: the STR‑currency
  warning and the "add the earner's IC" nudge that used to pop on separate rows are folded into this single voice, with a
  clear precedence (relationship → unreadable IC → STR stale/rejected → payslip‑isn't‑the‑same‑person → missing IC). The
  per‑file coloured status chips stay for instant feedback; only the *coach* consolidates. Backend
  `income_engine.income_cluster_advice` rewritten + new `IncomeClusterHelpView` (`GET scholarship/income/<member>/help/`);
  FE shared `CoachCard` shell + new `IncomeClusterCoach` + `clusterDocsFor`/cluster cache; per‑file coaches suppressed for
  cluster docs. No migration, no new i18n (reuses the existing verdict copy). 738 scholarship pytest + 262 jest + build clean.
- **Cikgu Gopal — leaner, diagnose-then-advise tone across every document message.** Gopal was spending words motivating Gopal was spending words motivating
  the student ("don't worry!", "you've got this!", "you're doing great!") instead of using the available signals to name
  the problem and say what to do. The prompt now mandates **diagnosis first, action second, stop** — warm in wording but
  economical — and explicitly bans cheerleading openers/sign-offs (at most one short reassurance, and only when it carries
  real information, e.g. "nothing is blocked"). All 19 pre-written fallback strings (en/ms/ta) were rewritten to the same
  shape. `help_engine.HELP_PROMPT` + fix-hint tidy; `scholarship.docs.help.fallback.*` rewritten. No migration, no logic
  change. 730 scholarship pytest + 258 jest + next build clean + i18n parity 2020.
- **Cikgu Gopal — precise message when the IC number is misread but the name matches.** On the student's own identity
  IC, a name‑match with a number‑mismatch is now its own verdict (`ic_nric_misread`) instead of the generic "the IC
  number didn't match your profile." Gopal reassures that the name matched, explains the number is almost certainly a
  camera misread (glare across the digits), and asks for a clean straight‑on re‑upload — with a soft fallback to "check
  the number in your profile" only if a clear photo still differs. When the name *also* fails (likely the wrong card), it
  keeps the generic note. Backend `help_engine` verdict split + guidance/fix‑hint; FE `HELP_VERDICTS`; new fallback copy
  `scholarship.docs.help.fallback.ic_nric_misread` (en/ms/ta). No migration. 730 scholarship pytest + 258 jest + build clean.
- **Verification verdict panel — green facts collapse to a tick, details only for what still needs you.** A fact whose
  badge is green (verified) now shows just `● FACT ✓` with no description, and its evidence/detail block is hidden — green
  means every requirement is met, so the receipts are noise. Amber/red facts are unchanged: they keep their lead line and
  the full detail block (the ✓ evidence + the • unresolved gap), because there the context is the whole story (e.g. "IC ✓,
  STR ✓, but no birth certificate links the mother — request it"). Net effect: a clean row of done tiles, detail only where
  attention is needed. Officer cockpit only; no migration. 258 jest + next build clean.
- **Utility-bill facts in the officer cockpit — Current · Reasonable · Outstanding + an orange "another name" note.**
  A water/electricity bill row now shows three soft hardship signals beside **Address**: **Current** (🟢 the bill is
  within ~3 months of the review date · 🟡 stale · ⚪ no readable date), **Reasonable** (🟢 combined household utility
  per‑capita under RM25/head · 🟡 borderline or high — a soft proxy never shows red · ⚪ can't judge), and **Outstanding**
  (🟢 shown *only* when arrears exceed the current charge — a genuine hardship signal — hidden otherwise). **Reasonable
  combines water + electricity** (water alone is a weak signal); with only one bill it greys out with a "water/electricity
  bill only" note rather than faking a verdict. When the account is in a name that's **neither the student nor any uploaded
  parent IC**, an **orange note** flags it (e.g. "Bill is in another name: …"). All soft — utility bills never gate a
  verdict. Backend `income_engine.utility_check` (+ `utility_reasonable`, billing-period parser); `officerCockpit`
  `documentFacts` extended; new i18n `docsDrawer.fact.reasonable`/`outstanding` + `docsDrawer.utilityNote.*` (en/ms/ta).
  No migration. Officer cockpit only. 723 scholarship pytest + 258 jest + next build clean + i18n parity 2019.
- **Officer Documents panel redesign — coloured per‑fact labels + route‑aware income ordering (TD-085 Sprint 2).** Each
  document row in the cockpit Documents drawer now shows the **labels of the facts that document provides**, coloured by
  its own sub‑verdict (🟢 verified · 🟡 partial · 🔴 not) — Identity IC → Name · IC No; results slip → Name · Subjects ·
  Results; offer letter → Name · IC No · Pathway; STR → Recipient · IC No · Current; salary slip → Name · Amount · Period;
  birth certificate → Child · Mother · Father; etc. The **relationship is movable**: it sits on a father/elder‑sibling IC
  (shared student‑IC patronymic), on the **birth certificate** for a mother, and on the **guardianship letter** for a
  guardian — never on a mother's/guardian's IC. The **income section** is now compulsory‑on‑top → optional‑at‑the‑bottom
  (route + selection aware, sourced from the same `incomeWizard` logic the gate uses), with red **Missing** placeholder
  rows for unmet compulsory documents. The row badge now **rolls up the fact colours**, which fixes the long‑standing
  "earner IC always shows Unread" bug (the earner IC is judged by its income relationship check, not the student‑identity
  verdict it never gets). New `officerCockpit` helpers `documentFacts` + `incomeDocLayout`; the admin detail serializer
  surfaces the income wizard answers (`income_route`/`income_earner`/`income_working_members`); no migration. Officer
  cockpit only. **This completes TD-085** (income gate + cockpit; the document‑first verdict + re‑extraction backfill were
  dropped — the route stays authoritative). 258 jest + next build clean + i18n parity 2013; 697 scholarship pytest.
- **Consent / submission gate v2 — route-aware and strict (TD-085 Sprint 1).** To give consent (and submit), a student
  must now upload exactly what their income route requires, plus a now-compulsory **offer letter**. STR route → the STR
  document + the earner's IC + the relationship doc (mother→birth certificate, guardian→guardianship letter; father via
  patronymic, none). Salary route → for EVERY selected working member: their IC + their **salary slip** (EPF no longer
  substitutes) + the relationship doc. The old "any one of STR / salary slip / EPF" rule is gone. The gate is sourced
  from the wizard's own `income_requirements` (one source of truth, so the consent blockers and the student checklist can
  never disagree); `consent_blockers` gains a `income_doc_blockers` helper + an `offer_letter_missing` /
  `str_missing` / `salary_slip_missing` / `birth_certificate_missing` / `guardianship_letter_missing` / `income_incomplete`
  blocker set (en/ms/ta). **"Never-block" now applies only at the officer/interview verdict, not at submission** (a
  deliberate reversal — a family who can't produce a route document can't submit, but is never auto-rejected later).
  **Grandfathered:** the strict bar applies only to not-yet-submitted apps (keyed on `profile_completed_at`); the 6
  already-submitted applications keep the old looser bar and are resolved at Check 2 / interview — `revert_if_profile_incomplete`
  never rolls them back on the new rules. The per-member salary slip is promoted optional→compulsory in both the backend
  `income_engine` and the frontend `incomeWizard.ts` mirror. No migration (pure logic). 697 scholarship pytest (+10) +
  250 jest + next build clean + i18n parity 1985.

### Fixed
- **STR-route salary slip / EPF now get the same earner-aware check as the salary route** (they were showing the old
  generic "the name doesn't match you — edit your profile" message). STR income proofs are stored UNTAGGED (single
  earner = `income_earner`) where the salary route tags each by member; a route-aware `_cluster_docs` helper hides that
  difference so `income_proof_check` / `income_ic_check` / the cluster coach all verify an STR slip against the untagged
  earner IC — not the student. Backend-only.

### Changed
- **Every document is single-instance now — a re-upload replaces the existing one in the same slot** (user's call,
  2026-06-05; supersedes the S15 "several monthly salary slips / EPF" multi-instance decision). Replace is scoped to
  the `(doc_type, household_member)` pair, so re-uploading Mother's salary slip replaces Mother's, never Father's, and an
  untagged upload never touches the member-tagged income docs. Retired `DocumentListCreateView.MULTI_INSTANCE_DOC_TYPES`.

### Added
- **Income Check-1 — birth certificate + guardianship-letter verification checklists.** The two relationship-proof docs
  were used in the verdict logic but never *surfaced* as a checklist. Now: the **birth certificate** reads the three JPN
  sections (child · father · mother, with the parents' **NRICs**) and shows Child (vs the student) · Mother (vs the
  mother's IC, name+NRIC) · Father (vs the student's patronymic). The **guardianship letter** is now Gemini-extracted
  (guardian name+NRIC · ward · court-order vs authorisation-letter) and shows Guardian (vs the guardian's IC) · Ward (vs
  the student) — so the guardian cluster is complete. Any relationship problem is still voiced once by the earner-IC
  cluster coach (these docs no longer fire the wrong generic "edit your name" nudge). New `bc_check` / `guardianship_check`
  serializer fields + `BcChecklist` / `GuardianshipChecklist`; BC extraction gains the NRIC fields; guardianship gains an
  extraction schema. No migration (computed; schema additive).
- **Income Check-1 — EPF facts refined + utility bills (address check + soft B40 proxy + hardship).** EPF now shows the
  **monthly contribution** (the income figure — drives the 24% salary estimate) separately from the **total accumulated**
  balance and the **year**, so a large lifetime balance is never read as monthly income (the extraction reads "CARUMAN
  SEMASA", and treats "Tiada Transaksi" as no contribution). Utility bills (water/electricity) get their own check: the
  meaningful test is the **home address** (the bill is in a parent's name, so the student-name match is dropped — fixes
  the wrong "edit your profile name" nudge); the **current month's charge** (not the arrears-inclusive total) and any
  **unpaid balance** are read. Combined water+electricity per-capita is surfaced as a **soft B40 proxy** on the Income
  tile (<RM25/capita consistent · >RM40 flags M40/T20) and meaningful **arrears** as a **hardship** signal — both
  officer-facing context, never verdict gates. `income_proof_check` now returns flexible `points`; new `utility_check`
  serializer field + `UtilityChecklist`; new officer codes `utility_percapita_b40` / `utility_percapita_high` /
  `utility_hardship`. No migration (computed; extraction schema additive).
- **Income Check-1 (I4) — salary-route per-capita income gate.** The salary-route Income tile now goes **verified** only
  when the **amount** also clears the B40 line: the earners' pay is summed from the documents (each ticked earner's
  salary-slip **gross**, or — when there's no payslip — an estimate from the EPF monthly contribution, ≈24% of salary)
  → **per-capita** = sum ÷ household size → compared to the cohort's `per_capita_ceiling` (RM1,584, the same line the
  shortlisting engine uses). Below the line *and* the cluster adds up (every earner IC + relationship confirmed) →
  verified (`income_per_capita_ok`); **at/above** the line → `recommend` + `income_above_b40_line` (a human decides at
  interview — never auto-rejected); income unreadable / informal / no household size → `recommend` + interview. EPF
  extraction gains `monthly_contribution`. Officer-facing only (no student to-do). No migration (computed field).
- **Income Check-1 — STR document verification (recipient + currency) + STR-route green = the cluster adds up.** The STR
  document is now read for its **recipient name + IC** and its **currency** (status + year), covering both the MOF letter
  and the MySTR portal screenshot (`vision` STR schema). It joins the **earner's cluster**: the recipient must match the
  STR earner's IC (not the student), and — because STR is awarded annually — a **stale** (older-year) or **rejected** STR
  is flagged (`str_not_current`) as no longer proving B40. The Income tile now goes **verified** only when the whole
  cluster adds up: a current STR whose recipient is the earner + the earner IC + a confirmed relationship (mother→birth
  cert, father→patronymic, guardian→letter); otherwise `recommend` (a human places it) — never blocks. A bare pre-wizard
  STR no longer auto-greens. New `str_check` serializer field + `StrChecklist` (Recipient · IC No · Status/Year · Amount);
  new reason codes `str_not_current` / `str_recipient_mismatch` (full 4-link chain) + the `str_not_current` Gopal coach.
  No migration (computed field; STR extraction is additive).
- **Income Check-1 — per-document IC/proof verification + cluster-aware Cikgu Gopal.** Income documents are now treated
  as a **cluster per person** (Father's IC + Father's salary slip + Father's EPF), unlike the single-document Identity/
  Academic/Pathway facts. **Each income IC** (`parent_ic`) shows the same checklist as the Identity card (IC No · Name ·
  Address) but with a **relationship** verdict — the earner's NRIC is shown for reference, never matched to the student;
  the Name carries a "Linked to your family" / "doesn't match" badge (father/sibling via the shared patronymic, mother
  via birth cert, guardian via letter). **Each salary slip / EPF** is read for the earner's name · **NRIC** (new
  extraction) · amount · period and cross-checked against *that member's* IC — so a father's payslip is verified against
  the father's IC, not the student. **Gopal now speaks once per member cluster** (anchored on the member's IC): it
  reasons across the cluster — relationship, coherence (are the IC + payslip the same person?), and completeness (a proof
  with no IC yet → "add their IC"). The old behaviour (which told the student to edit *their own* name when a parent's
  payslip didn't carry the student's name) is gone — a latent bug where `verdict_for_document` matched an earner's IC
  against the student's profile is fixed by splitting `ic` (identity) from `parent_ic` (relationship/cluster). New help
  codes `income_relationship_mismatch` / `income_proof_person_mismatch` / `income_ic_needed`; serializer fields
  `income_ic_check` + `income_proof_check`; `salary_slip`/`epf` extraction gains `nric`. No migration (computed fields).
- **Income Check-1 — salary (non-STR) route rebuilt for MULTIPLE working household members.** The single-earner salary
  route became a multi-select: *"tick everyone who works"* (father / mother / legal guardian / elder brother / elder
  sister), each with their own IC + (optional) salary slip + EPF. Storage gains a `household_member` tag on
  `ApplicantDocument` so several people's same-type documents coexist (father's payslip never overwrites mother's); the
  single-instance rule is now per `(doc_type, household_member)`. **Relationship proof** stays parent-grade for everyone:
  father/elder brother/elder sister all verify via the *same* student-IC patronymic (siblings carry the same father's
  name — `father_relationship` reused unchanged), mother via birth certificate, guardian via letter. **Verdict** (salary):
  every IC present + every relationship confirmed + ≥1 payslip/EPF → `verified` (the document *data* checks out; the
  income *amount*/B40 test is a later sprint); IC present but no financial doc (informal) or an unprovable relationship
  (e.g. a non-patronymic name) → `recommend` + interview flag — **never blocks**; a missing IC/relationship doc → `gap`.
  Per-member gaps **aggregate** into one ticket carrying a `members` list (the resolution layer keys tickets by code), and
  the income reason-code copy now names the member(s) ("Upload the IC for Father, Elder brother") in en/ms/ta on both the
  officer tile and the student Action Centre. The **forced non-earner-parent EPF** was dropped (EPF only exists for formal
  jobs — near-zero signal, confusing for homemakers). STR route unchanged. Migration `0040` (additive `household_member` +
  `income_working_members`), applied migrate-first.
- **Income verification Check-1 (the fourth and final fact) — a guided document wizard + earner identity & relationship
  proof.** Income was the weakest fact (it only checked that *a* document was present). It is now a clinical check, in
  three sprints (`docs/scholarship/check1-income-plan.md`; migration `0039`, applied migrate-first). **The wizard**
  (`/application` Documents → Household income, replacing the static income cards): Q1 "do you have an STR document?"
  → STR vs salary route · Q2 whose income (father/mother/legal guardian) · Q3 (salary) work status (payslip / informal /
  not working) · Q4 (non-STR) other household earner · plus family-burden steppers (siblings in school / in tertiary).
  The answers drive a **dynamic compulsory/optional document checklist** that reuses the existing card/chip/upload
  pattern. **Proving the earner is family:** father → the father's name in the *student's own IC patronymic* (no extra
  doc); mother → a **Birth Certificate** (a new document type, OCR'd for child/mother/father names); guardian → the
  guardianship letter. **The verdict** (`verdict_engine._verdict_income`, driven off the new pure `income_engine`):
  `verified` (a name-matched STR proves it), `recommend` (salary evidence assembled — a human still places the B40
  per-capita amount call), `review` (a check failed), `gap` (a compulsory doc missing). **Never blocks a genuinely poor
  family:** an informal / no-payslip earner whose income can't be document-proven becomes `recommend` +
  `income_unverified_needs_interview` (the officer confirms via household size, dependents and lifestyle at interview),
  not a rejection. 11 new reason codes wired through the full chain (officer tile + student Action Centre, en/ms/ta).
  Front-end `lib/incomeWizard.ts` mirrors the backend requirement engine exactly so the student's checklist always
  matches the officer verdict. **Deferred (hooks left):** reading the income *amount* for the per-capita test, the
  utility-bill hardship signal, and Cikgu Gopal's income doc-coach copy. Migration `0039` (six additive
  `ScholarshipApplication` fields + the `birth_certificate` doc type), applied migrate-first.
- **Cikgu Gopal now gives pointed, situation-specific results-slip advice instead of generic encouragement.** The coach was
  only ever handed a coarse verdict label (name/subjects/grade mismatch), so when a grade came back merely *uncertain* — the
  common "please check" outcome — `verdict_for_document` fell through to nothing and Gopal either said a generic line or
  stayed silent. Two facts the parser already has are now surfaced: the photo's **tilt angle** (`academic_engine.parse_spm_slip`
  → `skew_angle`; `student_slip_check` → `was_skewed`) and the **uncertain-grade** state. Two new verdict codes route on them:
  `slip_grade_uncertain` (read fine, one grade not fully sure → "glance at your slip and double-check, tidy it on your profile
  if it differs" — never a confident "you're wrong") and `slip_skewed_unclear` (the photo was at an angle *and* that left
  something unclear → "lay it flat, fill the frame, photograph straight from above"; no profile edit). **Anti-nag rule:** the
  retake advice fires only when skew **coincides** with a doubtful read — a rotated photo that nonetheless read cleanly
  (every grade matches) gets **no coach at all**. The **firewall is untouched** — Gopal still receives only a verdict code +
  doc type + first name; no score/profile/reviewer data can reach him. Frontend: the coach now appears on `results === 'uncertain'`,
  the two codes carry pre-written en/ms/ta fallback copy, and `slip_grade_uncertain` (not `slip_skewed_unclear`) gets the
  "edit your profile" link. Backend + frontend, no migration; i18n parity 1850×3.

### Fixed
- **Pathway: a Form-6 / STPM offer no longer false-clashes with the declared pathway.** A student who declared an STPM
  (Form 6) place saw "Offer … differs from the declared pathway — awaiting confirmation" even though the offer was for the
  same school and stream. Cause: the offer's *programme* field is read as the enrolment **type** ("Tingkatan Enam Semester
  1 Tahun 2026"), not the field of study, so the matcher (`pathway_engine.offer_pathway_match`) compared that structure
  wording against the declared field ("Sains Sosial") and saw a false field-clash — overriding the institution, which
  actually matched (same "Pulau Sebang" school). Fix: the enrolment-structure words (`semester`, `tahun`/`year`, `sesi`,
  `intake`/`pengambilan`/`kemasukan`/`tawaran`, and the Malay cardinals `satu`…`sepuluh`) are now treated as **generic**
  (non-distinctive), so a type-only offer programme contributes nothing to clash and the matching school carries it to a
  clean match — no nag. A genuine same-institution-different-field clash (e.g. Diploma Electricity vs Horticulture at UPM)
  is still flagged.
- **Pathway: a readable letter with no name/IC is no longer mislabelled "could not be read — ask for a clearer copy".**
  A general notice/memo (e.g. a UTM "your offer will be released later via SAM" letter) reads perfectly but carries no
  candidate name or IC. The verdict mapped that to `offer_unreadable`, telling the officer to chase a clearer copy that
  wouldn't help. New `offer_no_identity` reason fires when the body read (programme/institution present) but no identity
  is on it: "this letter has no student name or IC — it looks like a general notice, not the personal offer letter; ask
  for the actual offer letter." Truly-blank scans still read `offer_unreadable`. en/ms/ta officer + ticket copy added.

- **Officer Academic verdict no longer falsely says "the results slip could not be read" for a cleanly-read slip.** The
  officer verdict (`verdict_engine._verdict_academic`) decided slip readability partly from `slip.vision_name_match ==
  'not_found'` — but that column is the *supporting-doc / IC* full-text heuristic, not the results-slip name check. A
  results slip is name-checked the proper way (its candidate-name logic, surfaced as the sv-authoritative
  `student_verdict`), and that column is left blank/`not_found` for some name spellings even when the slip read perfectly
  — producing the self-contradictory "could not be read" **and** "entered 8 of 9 subjects" on the same student. Fixed by
  using the slip's own `academic_engine._slip_name_status` (the exact signal the student checklist uses, so officer and
  student now agree) instead of the wrong column. A clean slip with an odd-spelled name verifies; a missing subject still
  surfaces only the missing-subjects nudge. No re-OCR needed — the verdict recomputes per request. Backend only, no migration.

- **SPM results slip now reads correctly when the photo is sideways or tilted (orientation-robust positional parse).** The
  deterministic parser pairs each subject with the grade on its own row by clustering OCR words on their **Y-coordinate** —
  which only held when the slip was **upright**. A phone photo turned ~90° (or shot at a keystone angle) clustered into
  nonsense, the parse was abandoned, and Gemini read it instead — re-introducing the exact grade **transposition** the
  positional parse exists to prevent (this was the recurring "Pavalaharasi / Sharmila read wrong" bug). Fix: capture a
  per-word **baseline angle** (`vision._vision_words`) and, in `academic_engine._group_rows`, estimate the slip's
  dominant text angle and **de-rotate every word centroid** before grouping, so a rotated table becomes horizontal again
  and each subject keeps its own row's grade. **Gated** — a slip within ±25° of upright is left untouched (so a normal
  upright slip is never perturbed by OCR angle-noise, the cause of an earlier regression); only a clearly-rotated slip
  (~±90°) is de-rotated, by its precise median angle (handles the keystone, where the tilt is ~89° not exactly 90°). Row
  tolerance is derived from the inter-row gap so it scales to a 4000px-tall photo. Verified end-to-end against **four
  real student slips** frozen as fixtures (`tests/fixtures/slips/`): two upright (unchanged), one cleanly rotated 90°, one
  rotated-90°-with-keystone in the Type-2 format — all now parse with each subject correctly paired. Where a keystoned
  photo truncates a band's modifier (a bare `Cemerlang` printed beside an `A`), the band-authoritative read (`A-`)
  downstream becomes a soft "please check", never a confident wrong answer. The full-word-geometry capture is now kept
  **only on a fallback** (a slip the parser still can't read), so a future unhandled format is debuggable without bloating
  every successful slip. Backend only, no migration.

### Changed
- **SPM results slip is now read deterministically by positional OCR (Gemini becomes the fallback).** The slip is a
  standardised two-column table whose grade is printed twice — a letter (`A-`) and a Malay word-band (`Cemerlang`).
  The free-form Gemini image read was **row-transposing** the lower rows on watermarked slips (e.g. pairing PERTANIAN
  with PERNIAGAAN's grade) and, because the letter *and* band shift together, the letter↔band cross-check couldn't catch
  it — producing confident-but-wrong "slip reads B" flags that changed on every re-run. New path: keep Google Vision's
  per-word **bounding boxes** (`vision._vision_words`), group words into rows by **Y-coordinate** and columns by X
  (`academic_engine.parse_spm_slip` / `_group_rows`), so each subject pairs with the grade **on its own row** — immune
  to transposition and deterministic across re-runs. The band word is the authoritative grade (every row must carry one,
  which also excludes header/name rows); the letter confirms it; a genuine letter↔band conflict still degrades to
  "check by eye". Gemini (`extract_document_fields`) is used only when the positional parse can't lock onto the table
  (`< 3` subject rows) or the slip isn't SPM. Added `Tidak Hadir → TH` to the band map. Each row's subject is
  **resolved to the canonical SPM subject it contains** (`_match_known_subject`, longest-token-subset) rather than
  matched literally — so a subject **code** (`1103 BAHASA MELAYU`), watermark/OCR noise (`KIMIA Malaysia`, an Arabic
  fragment) or an `Ujian Lisan` oral-test row no longer breaks the match (the latter dedups against the real subject).
  **STPM** (no Malay bands; a ruled grid with grade-points) is a separate follow-up — its slip still routes to Gemini
  for now. Backend only, no migration. _A temporary `_debug_rows` field stores the grouped OCR lines to diagnose a
  residual single-row grade mispair (Sharmila's PERTANIAN); to be removed once solved._

### Fixed
- **Identity name now anchors on the deliberate "as in IC" declaration signature — not the Google handle.** Two
  root-cause fixes after a live review (applicant whose IC, results slip and offer letter all read the correct name,
  yet the verdict showed a fake "truncation" against the junk profile name `Sharmila 1204`):
  - **`profile.name` is now set from `declaration_name` at submit** (`create_application`). The About Me name field is
    pre-filled from the Google sign-in display name (which can be a handle like `Sharmila 1204`) and can ride through
    unchanged; the truthfulness-declaration signature is the deliberate, gated "as in IC" capture, so it becomes the
    canonical profile name from submit onward — and every identity check, email and sponsor profile reads the real
    legal name. Stored verbatim (admin views upper-case via `_full_name`). One-off backfill applied to the single
    pre-fix straggler. No standing code previously kept the two in sync (the earlier reconciliation was a manual sweep
    that missed one row).
  - **MyKad name extractor follows an OCR-mangled parentage marker.** When Vision drops the slash and reads `A/P` as a
    bare trailing `AP` (likewise `AL`/`SO`/`DO`), the extractor now follows to the next line and restores the canonical
    `A/P` (`THEEPICAA AP` → `THEEPICAA A/P SELVAVINAYAGAM`). Token-safe — a glued name like `FAISAL`/`PRATAP`/`VIMAL`
    is never treated as a marker (only a standalone final token counts). Reuses the existing line-break recovery.
  - The verdict's name-truncation copy no longer over-claims "corroborated by the other documents" (the identity
    verdict never actually cross-checks them) — it now credits the NRIC, which is the real anchor.
  - **`/profile/sync/` is now seed-only for the name.** The browser sync pre-fills the name from the Google sign-in
    display name; it may seed a blank profile but never overwrites a name already on file. This closes the one path that
    could otherwise undo the promotion — a student whose session lapses and who re-signs-in through the anonymous auth
    gate would have re-pushed the Google handle. Explicit edits via `PUT /profile/` are unaffected.

### Changed
- **Pathway — confirm ONLY on a real offer-vs-declared clash (no more redundant nag).** Replaces the always-ask
  `pathway_confirm`. A new **lenient matcher** (`pathway_engine.offer_pathway_match` / `_distinctive_tokens` /
  `_declared_pathway`) compares the offer letter's programme + institution against what the student declared at apply
  time (`chosen_programme`, or the pre-U school/track), tolerating naming quirks (*"KM Melaka" ≈ "Kolej Matrikulasi
  Melaka"*) and flagging a **mismatch only when genuinely off** — a different school (SMK Mentakab vs SMK Temerloh), a
  different foundation field (Asasi Pintar vs Asasi Pertanian), or a different diploma at the same campus (Horticulture
  vs Electricity at UPM). `student_offer_check` now returns `{pathway, declared_programme, declared_institution}`.
  **Verdict** (`_verdict_pathway`): the offer agrees (or there's nothing specific to clash with) → **`verified`** (the
  offer settles the pathway — no pointless confirmation); a genuine clash → the `pathway_confirm` query, reframed
  *"Is this where you're going? Your offer is for {programme} at {institution}, which looks different from the study
  choice you entered earlier…"* → the student's **Yes** realigns the record (`confirm_pathway`) and the fact reads
  `verified`. **Check 1** surfaces the clash softly: `OfferLetterChecklist` marks the programme/institution rows red with
  an *"Earlier you'd chosen: …"* note, and **Cikgu Gopal** gives a reassuring nudge (new `offer_pathway_mismatch`
  verdict — *"this is not a problem and never blocks you… we'll ask you to confirm it when you submit"*; never a re-upload
  or edit instruction). **Never a block.** No migration. i18n parity 1848 (en/ms/ta).
- **Document organisation now mirrors the four verification facts (Identity · Academic · Pathway · Income).**
  (1) **Reordered** the verdict so Pathway comes before Income everywhere it renders — scorecard tiles, the Record-verdict
  panel, the AI-suggestion footer, and the officer Documents drawer (`build_verdict`, `audit.FACTS`, the admin page's
  three fact arrays, `officerCockpit` object orders). (2) **The parent/guardian IC moved from Identity to Income** in the
  officer Documents grouping — the income docs (STR / salary slip / EPF) are issued in a parent's name and the parent IC
  is what confirms that earner (display-only; verdict Identity logic still keys on the student's own IC). (3) **The
  student Documents tab** is regrouped from Required/Optional into the five fact sections — **Identity** (compulsory: IC),
  **Academic** (compulsory: results slip), **Pathway** (important: offer letter), **Income** (compulsory: income proof +
  parent IC + utility bills) and **Other** (optional: statement of intent, photo) — each with a status pill. Presentational
  only: no completeness change (the offer letter stays non-blocking; `documents_done` unchanged). No migration. i18n
  parity 1843 (en/ms/ta).

### Added
- **Pathway — AI-raised "final chosen pathway" confirmation (no human officer).** Once a student uploads an offer
  letter whose **Name + IC match** their profile, the system auto-raises a `pathway_confirm` query in the Action Centre
  — *"We can see your offer for {programme} at {institution}. Is this the pathway you'd like assistance for?"* — and the
  student answers **Yes** in place. That writes the offer's programme + institution to `chosen_programme`
  (`source: offer_letter_confirmed`) and stamps `pathway_confirmed_at` (migration `scholarship/0038`, additive), after
  which the **Pathway verdict reads `verified`** (*"Final pathway confirmed by the student: …"*). Deliberately **not a
  blocker**: a student who receives a better offer just uploads that one instead — whatever they confirm becomes the
  final pathway. `_verdict_pathway` now uses `pathway_engine.student_offer_check` (Name + the strong **IC** check) for
  the identity guard; a wrong-person letter → `offer_name_mismatch` (no confirmation offered). The Action Centre renders
  the confirm query with a direct affirmative button (a new in-place resolve, distinct from the navigate-to-section
  `confirm`). +6 backend tests; i18n parity 1830 (en/ms/ta).
- **Check 1 — Pathway (offer letter) facts, differentiated.** The offer letter now gets the same clinical fact-checklist
  the IC and slip have, surfacing the facts the coordinator cares about. Two real identity checks — **Name** and **IC**
  (`candidate_nric` matched against the profile NRIC; the IC is the strong one, since names can coincide but the NRIC
  can't) — plus soft **data points**: **Programme · Institution · Issued-by · Date · Address**. The Gemini `offer_letter`
  extraction was expanded (`+candidate_nric, issuer, offer_date, candidate_address`) with a prompt that understands all
  Malaysian post-SPM offer types (university degree/diploma, polytechnic, matriculation, Form Six) — "issued-by" tells the
  pathway type. New pure `pathway_engine.student_offer_check` is the single source for the FE `OfferLetterChecklist` and
  Cikgu Gopal, so they can't disagree. Programme/institution are surfaced (not hard-checked) — a student may legitimately
  change plans between applying and getting an offer. A minimal safe Gopal verdict (`offer_name_mismatch` = "this may be
  someone else's offer letter, upload your own") replaces the previously-misleading IC-style "edit your profile name"
  advice on a wrong-person letter; richer pathway-aware coaching is a later pass. No migration. +10 backend tests; i18n
  parity 1825 (en/ms/ta).
- **Check 1 — Academic (results slip) follow-up.** Reverted the band-word prompt instruction (one slip extracted an empty
  table under it; the deterministic strip makes it redundant) and split "couldn't read" from "not checked yet" so a slip
  that extracts no subject rows nudges a clearer re-upload. (Folded into the Academic entry below conceptually.)
- **Check 1 — Academic (results slip) hardening (one batch; branch `check1/academic`).** The second of the four facts
  gets clinical upload feedback. **(1) BUG FIX — "Entered 0 of 9 subjects."** Gemini glued the SPM grade-**band** words
  onto each subject (an SPM row prints the grade twice: `MATEMATIK … CEMERLANG TINGGI … A`), so `"MATEMATIK CEMERLANG
  TINGGI"` never matched `"Matematik"` and every subject read as *missing*. `academic_engine._split_band` now strips a
  trailing band phrase (`cemerlang|kepujian|lulus|gagal` + optional `tinggi|tertinggi|atas`) before matching and keeps a
  band→letter map as a fallback for an unread grade; the Gemini `results_slip` prompt also nudges subject-name-only. It's
  a **read-time** fix, so existing prod slips correct themselves with no re-OCR — and the officer verdict
  (`_verdict_academic`) is fixed for free. **(2) Clinical 3-check** — new `student_slip_check` is the single source for
  **Name · Subjects · Results** (+ the **exam year** as a soft data point) consumed by both a new `ResultsSlipChecklist`
  (mirrors the IC `ICChecklist`) and Cikgu Gopal, so they can't disagree. **(3) Specific Gopal advice** — three new
  verdict codes (`slip_name_mismatch` = "this may be someone else's slip, upload your own"; `slip_subjects_missing` =
  "add the subject on your Profile"; `slip_grade_mismatch` = "the slip is the official record — update your Profile to
  match it") with a `/profile` link for the subjects/grade fixes (none for the wrong-file name mismatch). No migration.
  +27 backend tests; i18n parity 1811 (en/ms/ta).
- **Check 1 — Identity/IC OCR hardening (one batch; branch `check1/identity`).** The Identity fact's
  upload-time read now gives every student good feedback. **(1) Name truncation** — a parentage marker
  (A/L · A/P · BIN · BINTI · S/O · D/O) at the END of the MyKad name line means the surname was line-broken;
  it's now appended (*"THERESA ARUL MARY A/P" → "… A/P A.PHILIPS"*). **(2) Address card-label strip** — lines
  that are entirely card chrome ("MyKad", "WARGANEGARA", "ISLAM"…) no longer leak into the surfaced home
  address. **(3) ★ Gemini IC second opinion (cost-gated)** — `run_vision_for_document` keeps the free
  deterministic read, then escalates to a Gemini **image** read ONLY when the read is low-confidence (a core
  field missing, or it disagrees with the typed profile); the merge adopts Gemini's NRIC/name only when it
  matches the profile and the cheap read didn't (address always prefers the cleaner value). Behind
  `IC_GEMINI_FALLBACK_ENABLED` (default ON). This covers marker-less names + blurry-digit NRICs + noisy
  addresses together; common clean uploads stay free. **(4) Cikgu Gopal name-mismatch guidance is now
  bidirectional** — offers BOTH "upload a clearer photo" AND "fix the spelling on your profile" (it no longer
  assumes the document is wrong), and the coach surfaces an "Edit your name in your profile" → `/profile` link.
  No migration. +17 backend tests; i18n parity 1793 (en/ms/ta).
- **Verification Verdict engine + officer scorecard (Sprint 1 of the verification-verdict roadmap).** A new
  deterministic engine (`apps/scholarship/verdict_engine.py`) rolls the scattered post-shortlist signals
  (Vision OCR matchers, doc-assist fields, completeness, the anomaly engine) into ONE four-fact verdict the
  coordinator **audits** instead of assembling: **Identity** (name + NRIC), **Academic** (results slip),
  **Income (B40)**, **Pathway** (offer letter). Each fact carries a status — `verified` (green, the AI asserts) /
  `review` (amber, confirm) / `recommend` (blue, a human places the verdict) / `gap` (red, action needed) — plus
  an evidence list and an unresolved list (`{code, params}`, resolved on the frontend from
  `admin.scholarship.verdict.*`). Pure + deterministic, **no LLM calls**; surfaced on `/admin/scholarship/[id]`
  as a "Verification verdict" card above the Pre-interview flags.
  - **Design rules encoded:** green is *expensive* (under-claim by default); the AI **resolves before it
    escalates** (an OCR name truncation where the IC tokens are a subset of the typed name is settled silently,
    not raised — the NRIC is the hard key); **income green needs a verified STR *document***, not the
    self-declared flag (else it recommends and a human decides); **address is a coherence test** — only a
    state-level divergence escalates, sub-state postcode drift is noise.
  - Backend: `AdminApplicationDetailSerializer.verdict` (mirrors `anomalies`). No migration (reads existing
    signals). 23 new tests in `test_verdict_engine.py` (per-fact statuses, the two design rules, a full
    Theresa-shaped integration check); full scholarship suite green (433). Frontend: `AdminVerdictFact`/
    `AdminVerdictItem` types + the scorecard render (reuses the existing admin card pattern; the polished
    panel + Stitch redesign is Sprint 5). i18n `admin.scholarship.verdict.*` × en/ms/ta (parity 1701; Tamil
    first-draft). Plan: `docs/scholarship/verification-verdict-plan.md`.
- **Grade OCR + academic verification (Sprint 2).** The results-slip extractor now reads the **grade against each
  subject** (`vision.py` `_FIELD_SCHEMAS['results_slip']` → `results: [{subject, grade}]`, plus a grade-specific
  prompt hint), and a new `academic_engine.py` runs two checks the officer used to do by eye: **completeness**
  (every subject on the slip is entered — Theresa: "8 of 10, missing Moral + Tamil Literature") and **accuracy**
  (the typed grades match the slip — the typed and OCR'd grades are two independent readings; agreement is strong
  verification, a disagreement pinpoints the one cell). Comparison is by **normalised subject name** (sidesteps the
  `b_tamil`/`bahasa_tamil` key collision); `_SUBJECT_BM` mirrors `subjects.ts`. The Academic fact now reaches
  **`verified`** when the slip is the student's, complete, and accurate — else `review` with the specific gaps.
  - **Completeness works on already-extracted slips** (legacy `subjects` shape) with no re-OCR; accuracy needs the
    new grade extraction. Grades live in the existing `vision_fields` JSON — **no migration**. Frontend: widened
    `vision_fields.fields` type + a one-line renderer tweak so `{subject, grade}` pairs display cleanly (full doc-box
    redesign stays S5). 12 new tests (`test_academic_engine.py` pure + grade-aware verdict tests); full scholarship
    suite 445 green; `next build` clean. i18n +3 item codes × en/ms/ta (parity 1704). **Billable real-slip OCR smoke
    deferred** to a user-run step (existing docs re-extract on re-upload / admin re-run).
- **Resolution tickets — the IBKR Action Centre backend (Sprint 3).** Each unresolved verdict item becomes a discrete,
  independently-resolvable **`ResolutionItem`** (migration `0036`, table `resolution_items`, RLS deny-by-default) —
  closable by a document, a typed explanation, or a one-tap confirm. New `resolution.py`: `CODE_TO_TICKET` maps the
  ticketable verdict codes → `{fact, kind, doc_type}`; `sync_resolution_items` is **idempotent** (one `source='system'`
  item per `(application, code)`, partial-unique-constrained + race-safe) and **auto-resolves** a ticket the moment its
  gap clears (upload STR → income gap gone → ticket closes), **never re-nagging** an answered confirm. Three verdict
  codes are deliberately **not** ticketed (confirmed with the user): `ic_service_down` (transient — auto-retries,
  escalates to `ic_unreadable` if persistent), `grades_unverified` (a machine "not-read-yet" state), and
  `str_present_unverified` (officer-side confirmation). Officers can raise manual tickets (`add_officer_item` — the
  structured successor to `info_request_note`) and waive/resolve them. Endpoints: student `GET/POST
  scholarship/resolution-items[/<id>/resolve/]`; officer `…/<pk>/resolution-items/` + `…/resolution-items/<id>/<action>/`.
  Sync wired into document upload + delete; the admin detail serializer exposes the live open queue
  (`AdminApplicationDetailSerializer.resolution_items`). **Real-data check:** Theresa auto-generates exactly 2 tickets
  (upload STR + add 2 missing subjects); identity/pathway verified → none; `grades_unverified` correctly excluded.
  9 new tests; full scholarship suite **454** green. **Backend only** — the student Action Centre UI is S4. Migration
  is created on the branch (test DB applies it); **prod migrate-first happens only at deploy** (new-model →
  contenttypes workaround + RLS per TD-058).
- **Student Action Centre — the IBKR queue UI (Sprint 4, frontend).** A warm, self-service "things to finish"
  surface at the **top of `/application`** (above the 5-step tabs) that consumes the S3 resolution endpoints and lets
  a shortlisted student clear each gap **in place**: `doc` → inline upload (reuses the signed-URL upload flow),
  `explanation` → a short typed reply (`POST …/resolve/`), `confirm` → a "Review" button that jumps to the relevant
  tab (the ticket auto-clears server-side once the gap closes). Header "Almost there, {name}" + a progress bar, an
  amber **"To do"** pill per card, a **Cikgu Gopal** coach bubble (graduation-cap mascot), and a green **"All done —
  your application is complete!"** state when the queue empties. Additive + non-blocking. New
  `components/ActionCentre.tsx` + pure `lib/actionCentre.ts` (**16 node-env jest tests**);
  `getResolutionItems`/`resolveResolutionItem` + `ResolutionItem` type in `lib/api.ts`; wired via
  `ScholarshipNextSteps`. Student i18n `scholarship.actionCentre.*` (per-code `item.<code>.{title,desc}` for all 15
  system codes) × en/ms/ta (**parity 1750**, Tamil first-draft). Stitch design approved (spacious V1 cards +
  graduation-cap mascot). `next build` clean; full jest suite 199 green. **No migration, no backend change.**
- **Officer Review Cockpit + verdict audit/override capture (Sprint 5 — the LAST sprint of the verification-verdict
  roadmap).** The admin `/admin/scholarship/[id]` page becomes the two-stage hinge: the coordinator **audits** the
  AI's four-fact verdict, clears leftover caveats, and records their own verdict which can trigger the final sponsor
  profile.
  - **Backend (additive — no new model):** five audit fields on `ScholarshipApplication` (**migration `0037`**):
    `ai_verdict_snapshot` (the four-fact `build_verdict` snapshot captured at decision time), `officer_verdict`
    (`{identity,academic,income,pathway: 'pass'|'fail', overall}`), `verdict_reason`, `verdict_decided_by`,
    `verdict_decided_at`. New reviewer-gated `AdminRecordVerdictView` (`POST …/record-verdict/`) snapshots the AI
    verdict beside the officer's decision and — when `finalise` is set and a draft profile + submitted interview
    exist — runs the existing Phase-D refine to generate the final profile in one action (reuses
    `refine_sponsor_profile`; never re-derives it). New `AdminVerdictMetricsView` (`GET …/verdict-metrics/`) +
    pure `audit.py` (`compute_overrides`/`override_metrics`) compute the **override rate** ("how good is the AI":
    where the human's pass/fail disagreed with the AI's `verified` assertion, per fact). Audit fields exposed
    read-only on `AdminApplicationDetailSerializer`. 17 new tests (`test_verdict_audit.py`); full scholarship
    suite **493** green; migration matches the model (`makemigrations --check` clean).
  - **Frontend (cockpit redesign):** the four-fact verdict rendered as horizontal **status tiles**; a **Caveats to
    resolve** panel (the open `resolution_items`) with officer **Ask** / **Resolve** actions; a redesigned
    **Documents drawer** — grouped under Identity/Academic/Income/Pathway with a file icon, filename, extracted-field
    line, status pill (Verified/Check/Unread) and View link (replaces the old flat list; preserves the doc-assist
    fields + warnings); and a sticky **Record-your-verdict** panel — per-fact pass/fail toggles + reason + **"Save
    verdict & generate final profile"**, a Tools group (pose query / log call / add findings), and an "AI suggested:
    … — you decide" footer. New pure `lib/officerCockpit.ts` (`factTileTone`/`groupDocumentsByFact`/`aiSuggestionFor`/
    `documentPill`, **27 node-env jest tests**); `recordVerdict`/`getVerdictMetrics`/`raiseResolutionItem`/
    `actionResolutionItem` + the audit + `AdminResolutionItem` types in `lib/admin-api.ts`. Admin i18n
    `admin.scholarship.{recordVerdict,caveats,docsDrawer}.*` × en/ms/ta (**parity 1782**, Tamil first-draft).
    Stitch designs approved (cockpit layout A + the standalone documents drawer). `next build` clean; full jest
    suite **226** green. Built by a delegated subagent; build/jest/i18n gates + the diff independently re-verified by
    the orchestrator before commit. **The verdict roadmap (S1–S5) is now complete; the whole branch deploys next
    (migrate-first: `0036` new-model + `0037` additive, per TD-058 + RLS).**

### Fixed
- **Officer cockpit polish + application-pipeline quick wins (verification-verdict 2nd deploy).** (1) The officer
  cockpit (verdict tiles + the sticky **Record your verdict** panel) now renders **directly under the applicant
  header** with the detailed applicant data below it, instead of floating beneath the data — so the officer audits
  the verdict first and the Record panel sits top-right near the name. (2) **Cikgu Gopal** no longer calls the
  programme "HalaTuju Scholarship" — it is the **B40 Assistance Programme**; his tone is toned down (plainer cikgu,
  hard rule **no pet names** like "dear"); and his advice now **sticks** — a storage-injectable cache keyed by a
  per-language verdict signal means a plain page reload re-renders the stored advice with no re-fetch/re-pop, and
  Gopal only re-fires after an actual (re-)upload. (3) The student's **IC validation shows one box per distinct
  issue** (a bad NRIC and a name mismatch are separate boxes, never merged). (4) **Hard audit gate** — an officer
  can no longer verify-&-accept a case until they have **recorded their verdict** (audited the AI's four-fact
  verdict); `verify-accept` returns `400 verdict_not_recorded` otherwise (no override). Backend **494** pytest +
  **231** jest; i18n parity **1782**; `next build` clean. No migration. Plan:
  `docs/scholarship/application-processing-pipeline-plan.md`.
- **Document intake now accepts PDF (not just images) and rejects video/junk — fixes the live TD-080 dead-end.**
  A PDF or video IC used to return Google Vision "Bad image data", which we mislabelled as `ic_service_down`
  ("try again later") — a permanent block at consent (5 applicants stranded). And every PDF *supporting* doc
  (EPF/payslip/offer letter — usually PDFs) silently yielded no OCR text, weakening the income/academic signals.
  - **OCR is now content-type aware** (`vision.extract_text` + `extract_mykad`, via a shared `_vision_document_text`
    seam): a **digital PDF** is read from its text layer (`pypdf` — free, no Vision call); a **scanned PDF** is
    **rasterised, page 1** (`pypdfium2` + `Pillow`) and sent to Vision; images are unchanged. Libs are optional —
    a PDF degrades to "unreadable" if absent. Permissive licences (no AGPL).
  - **Upload format allowlist** (`DocumentListCreateView`): images + PDF only; video/other is rejected
    (`unsupported_format`). Previously there was **no** format check — that's how a `.mp4` IC got through. Frontend
    `accept="image/*,.pdf"` + a client pre-check + an `unsupportedFormat` message (en/ms/ta).
  - **TD-080 error re-map** (`_ic_identity_blockers` + `detect_vision_outage`): a decode/fetch error ("Bad image
    data."/"empty image"/"could not fetch") now → `ic_unreadable` ("re-upload a clear photo/scan"), reserving
    `ic_service_down` for genuine outages.
  - **No migration** (`content_type` already on `ApplicantDocument`). `requirements.txt` += `pypdf`/`pypdfium2`/`Pillow`.
    15 new tests (`test_pdf_intake.py` — real-PDF lib checks + seam-mocked dispatch); scholarship suite 425 green;
    `next build` clean; i18n parity 1663. Plan: `docs/scholarship/document-intake-hardening-plan.md`. **Deferred:**
    a billable real-scanned-IC-PDF Vision smoke (user-run, around deploy).
- **Document-intake follow-ups (surfaced re-running the stuck students' ICs):**
  - **Parent/guardian IC re-run now works.** `AdminRunVisionView` rejected anything but `doc_type='ic'`, so every
    parent-IC "Re-run Vision" 400'd ("Could not re-run Vision"). It now allows `ic` **and** `parent_ic` (both are
    MyKad-structured and OCR'd on upload).
  - **MyKad name extraction fixed — it was grabbing a locality as the name.** `_extract_name` used "longest all-caps
    line," so a locality (e.g. `TAMAN SRI LAYANG`) could out-run the real name → a false name mismatch. It now anchors
    on the **parentage marker** (A/L, A/P, S/O, D/O, BIN, BINTI), which appears in the name and never in an address;
    falls back to the line right after the NRIC (e.g. Chinese names), then to longest. (Harish/Janani cases.)
  - **A name mismatch no longer hard-blocks consent when the NRIC matches.** The NRIC is the hard identity key, so a
    flaky name OCR shouldn't block an NRIC-verified student (`_ic_identity_blockers`); a name mismatch blocks only when
    the NRIC *also* fails (a genuine wrong-IC). The admin still sees the soft name-mismatch chip.
  - Backend only (no migration, no frontend). +7 tests; full backend suite 1468 green.

## [2.26.1] — Remove orphaned sponsor register-interest page + stack (TD-072b) (2026-06-01)

### Removed
- **The pre-feature sponsor "register interest" lead form and its entire backend stack.** Superseded by the
  self-serve sponsor auth + portal (E1c, v2.23.0); it had been orphaned since and held 0 rows in production.
  Full removal (Option B): the `/sponsor/register-interest` page, `submitSponsorInterest` API helper, the
  `sponsorInterest.*` i18n block in all three locales (en/ms/ta), `SponsorInterestView` +
  `AdminSponsorInterestView` + their two routes, `SponsorInterestSerializer`, the `SponsorInterest` model
  (table `sponsor_interests`), and the obsolete `test_sponsor_interest.py`.
  - **Kept** `emails.send_sponsor_interest_admin_email` — now shared by the live `SponsorRegisterView`.
  - **Migration `0035_remove_sponsor_interest`** (DeleteModel) — destructive, so applied **deploy-first**:
    code pushed first, then `DROP TABLE sponsor_interests` via Supabase MCP (table empty, safe).
  - i18n parity holds at 1662 keys × 3 locales; 183 jest; scholarship 410. Closes **TD-072(b)**.
- **Dropped the dead legacy `student_profiles` table (TD-025).** The Streamlit-era `public.student_profiles` (30 rows,
  19 cols — `name`/`email`/`phone`/`grades`/`pin_hash`/…) was orphaned: the live `StudentProfile` model owns
  `api_student_profiles` (618 rows), and the `api_` prefix existed *only* to avoid colliding with this dead table —
  a footgun that caused a v2.21.0 near-miss (a raw `ALTER` silently hit the wrong table). Not a Django-managed table,
  so dropped via Supabase MCP with **no migration/deploy**. Pre-drop: verified zero incoming FKs, zero live code
  references, zero view/trigger/RLS dependencies; backed up all 30 rows to
  `halatuju_api/docs/backups/student_profiles_legacy_backup_2026-06-01.json`. A mistaken bare `ALTER student_profiles`
  now errors loudly instead of silently succeeding. Closes **TD-025**.
- **Purged the historical orphan document blobs (TD-062, fully closed).** Ran the `cleanup_orphan_blobs` sweep against
  prod for the first time. To avoid the wrong-DB footgun, the known-paths set was pulled from the prod DB via Supabase
  MCP (not a local connection) and diffed against a Storage-API bucket listing. Found **6 orphans, all under app `3/`**
  (Elanjelian test account — 5×`ic` + 1×`parent_ic`, leftover from pre-fix `Remove` clicks that dropped the DB row but
  not the blob); the 49 live documents all matched. Deleted the 6 after sign-off; re-verify: 49 bucket objects, 0
  orphans. Going-forward delete path was already clean. Closes **TD-062**.

## [2.26.0] — Phase E Sprint E3a: sponsor wallet + match/consent (backend, no real money) (2026-06-01)

- **The sponsorship match — a sponsor funds an anonymous student, the student/guardian accepts.** Built on dummy data,
  behind the pool flag; **no real money is touched** — donations are mocked (no toyyibPay), and disbursement + tranches
  are later, gated slices. Money is modelled as a **ledger**, never a custody/refund flow.
  - **Wallet (donation) model:** a sponsor **donates** into myNADI (final — never a bank refund); their spendable
    **balance = total donations − allocations that still hold** (`Donation` + `Sponsorship`; `sponsorship.sponsor_balance`).
    A lapsed/cancelled allocation simply stops holding, so the amount returns to the balance to redirect — exactly the
    behaviour the user described, with no money leaving myNADI.
  - **Match flow (1:1, full-or-nothing for now; many-sponsor plumbing underneath):** an admin sets the
    `ScholarshipApplication.award_amount`; a sponsor with enough balance **funds in full** → an `offered` `Sponsorship`
    (award letter point) → the student (or **guardian** for under-18s, reusing the share-consent guardian gate) **accepts**
    within a deadline → `active`, app → new **`sponsored`** status, and the student **leaves the pool**; decline/lapse →
    the amount returns to the sponsor's balance. A DB partial-unique constraint enforces one holding sponsor per student.
  - **Anonymity holds BOTH ways (and is tested):** the sponsor's view of their allocation leaks no student
    name/NRIC/email/phone (allowlist card); the student's award view has **no sponsor field at all**. Admin oversight
    (back office) sees both sides.
  - **Endpoints:** sponsor `wallet` · `wallet/donate` (MOCK) · `pool/<id>/fund` · `sponsorships` · `cancel`
    (flag + approved-sponsor gated); student `scholarship/award/` GET + accept/decline (guardian-gated); admin
    `applications/<id>/award-amount/` + `admin/sponsorships/` oversight. **Migration `0034`** (additive `award_amount`
    + new `sponsor_donations` + `sponsorships` tables + RLS, applied migrate-first via Supabase MCP, prod-verified).
  - +17 tests (`test_sponsorship.py`); 1452 pytest + 183 jest. **Deferred (TD-075):** real toyyibPay donation-in +
    disbursement-out + the tranche schedule (RM ×N with progress-gated release/withhold) + the lapse cron + partial /
    multi-sponsor funding. See `docs/retrospective-v2.26-sponsorship-e3a.md`.

## [2.25.1] — Anon-profile pre-publish identifier scan (TD-074b) (2026-06-01)

- **The anonymous sponsor blurb's anonymity is now structural, not just model-trust + human-review.** The blurb is
  generated from non-identifying inputs but is fed the student's free-text narrative, which could echo a name/school/
  place. New `pool.scan_anon_for_identifiers(text, profile)` scans the generated blurb for the student's **own**
  identifying tokens — name + school distinctive tokens (generic words like SMK/Sekolah/School and connectors
  bin/binti/a-l are stoplisted to avoid false positives), city, NRIC, phone, email — and `AdminPublishAnonProfileView`
  now **refuses to publish** (`400 anon_identifier_leak` + the offending `fields`) when any are found; the profile
  stays unpublished and the admin must regenerate first. The scan errs toward blocking. Three layers now guard the
  soft surface (prompt forbids → admin reviews → system blocks publish on leak); the allowlist card remains the hard
  boundary. Closes one of the two pre-go-live gates for the pool flag (the other is the lawyer review). +7 tests;
  1435 pytest. Backend only, no migration.

## [2.25.0] — Phase E Sprint E2b: anonymised pool frontend (browse UI + admin anon controls) (2026-05-31)

- **The pool frontend — completing Phase E2 end-to-end, still behind the OFF flag (dark deploy).** While
  `SPONSOR_POOL_ENABLED` is off the pool API 404s, so an approved sponsor keeps seeing today's "browsing coming soon"
  shell; the real UI appears only when the flag is flipped (post-lawyer). Built mirroring existing card/list patterns.
  - **Sponsor browse:** the `/sponsor` approved state fetches the pool — on success renders an **anonymised cards
    grid** (alias · state · field · academic band · funding categories); on 404/error degrades to the coming-soon
    shell. New **`/sponsor/pool/[id]`** detail page: the non-identifying summary + the generated **anonymous blurb**
    (react-markdown) + a clear "identities are protected" note.
  - **Admin controls** on `/admin/scholarship/[id]`: a new "Anonymous profile (sponsor pool)" card (mirrors the
    Final-profile panel) — **Generate (AI)** → preview `anon_markdown` → **Publish / Unpublish** + a "published to
    pool" badge. Reviewer-gated (backend enforces).
  - API clients `getSponsorPool`/`getSponsorPoolDetail` (api.ts) + `generateAnonProfile`/`publishAnonProfile`
    (admin-api.ts; `anon_*` added to `AdminSponsorProfile`). i18n `sponsorPool.*` + `admin.scholarship.anonProfile.*`
    (parity 1675; Tamil first-draft). No migration. 1428 pytest + 183 jest; `next build` clean. Not click-tested
    (flag-gated; needs the flag on + dummy data + sponsor/admin sessions). Lawyer review gates flipping the flag on.

## [2.24.0] — Phase E Sprint E2a: anonymised sponsor discovery pool (backend, flag-gated) (2026-05-31)

- **The PDPA-critical heart of the sponsor marketplace — built behind a master flag, on dummy data, NOT live.**
  An approved sponsor can browse an anonymised pool of students; a sponsor **never** sees a name, NRIC, address,
  phone, email, or school. **`SPONSOR_POOL_ENABLED` defaults OFF** — every browse endpoint 404s until the lawyer
  signs off; this release ships the machinery with the door shut.
  - **Eligibility (consent = opt-in):** a student is in the pool only when their **anonymous profile is published**
    *and* an **active `share_with_sponsors` consent** exists (`pool.is_pool_eligible` / `eligible_pool_queryset`).
    Each pooled student gets a stable, non-sequential alias (`pool_ref`, e.g. `S-A3F9C1`) + a coarse academic band.
  - **Generated (not scrubbed) anonymous profile:** `profile_engine.generate_anonymous_profile` uses a **separate
    prompt fed only non-identifying inputs** — no name/school/referees — instructed to say "the student" and omit any
    names/places. An admin **generates → reviews → publishes** it (the human backstop); regenerating un-publishes.
  - **Allowlist serializers are the hard safety boundary:** `SponsorPoolCardSerializer` (alias · state · field ·
    academic band · funding categories · months) + `SponsorPoolDetailSerializer` (+ the anon blurb) are plain
    `Serializer`s with **explicit derived fields and zero model passthrough**, so a new model field can never leak.
    Dedicated tests plant a distinctive name/NRIC/address/phone/email/school and assert **none** appears in any
    sponsor payload.
  - **Endpoints:** `GET /api/v1/sponsor/pool/` + `/pool/<id>/` (flag-gated **and** approved-sponsor-only — pending
    sponsor → 403); admin reviewer-gated `…/anon-profile/generate/` + `…/anon-profile/publish/`. **Migration `0033`**
    (additive `anon_*` columns on `sponsor_profiles`, applied migrate-first via Supabase MCP, prod-verified).
  - No frontend yet (E2b). 1428 pytest (+17, `test_sponsor_pool.py`) + 183 jest. The lawyer review gates flipping the
    flag on, not the build. See `docs/retrospective-v2.24-sponsor-pool-e2a.md`.

## [2.23.2] — Logout isolation + student modal no longer overlays admin/sponsor (2026-05-31)

- **Follow-up to v2.23.1's login-isolation fix — now the LOGOUT side is isolated too.** Logging out of the **student**
  app was logging you out of the admin/sponsor consoles. Two causes, both fixed:
  - `clearAll()` (run on student logout) deleted **every** `halatuju_*` localStorage key — including
    `halatuju_admin_session` and `halatuju_sponsor_session`. It now **preserves** those two (and their PKCE verifiers).
  - All three `signOut()` calls used Supabase's default **`global`** scope, which revokes *every* session for the
    identity server-side (the three clients share one Google identity). All three now use **`scope: 'local'`**, so
    each logout ends only its own session. Net: student / admin / sponsor logouts no longer affect each other.
- **The student auth-gate modal ("Create Your Free Student Account") no longer overlays the admin/sponsor consoles.**
  It's rendered globally in `Providers`, so it could appear over `/admin` + `/sponsor`; it now route-guards itself
  (`usePathname`) and renders nothing on `/admin/*` and `/sponsor/*` (the visible half of TD-073). No migration; no i18n.
  1411 pytest + 183 jest; `next build` clean.

## [2.23.1] — Auth session-isolation fix (PKCE) + sponsor/partner UX polish (2026-05-31)

- **Security/correctness fix — cross-scope session leak closed (PKCE).** Logging into the Partner (admin) or Sponsor
  console with Google **also silently created a Student session in the same browser**, and logging out of admin didn't
  clear it — so clicking "Dashboard" afterwards showed you logged in. **Root cause:** Supabase-js defaults to the
  **implicit** OAuth flow, which returns the session in the URL *hash* (`#access_token=…`) — readable with no secret —
  and the student `AuthProvider` is mounted **globally** (incl. on `/admin/auth/callback` + `/sponsor/auth/callback`)
  with `detectSessionInUrl` on, so it grabbed the admin/sponsor Google session into the student storage key. **Fix:**
  all three Supabase clients (student `getSupabase`, `getAdminSupabase`, `getSponsorSupabase`) now use
  `flowType: 'pkce'` — the OAuth result comes back as a `?code=` that can only be exchanged with the code-verifier
  stored under the *initiating* client's storage key, so a non-initiating client (the global student client on an
  admin/sponsor callback) physically cannot claim the session. Not a privilege escalation (one Google account = one
  Supabase identity, gated per-scope by role), but a real isolation bug on shared/public computers. **Note:** users
  who already have a leaked student session must log out / clear storage once; the bleed cannot recur after this.
- **Sponsor form + student modal polish (live feedback):**
  - Student auth-gate modal title → **"Create Your Free Student Account"** (was "…Free Account").
  - Phone fields now read **"Mobile number"** with the correct **`12-345 6789`** placeholder (the leading 0 is dropped
    after the `+60` prefix); new `formatMyMobile`/`isValidMyMobile` helpers (node-unit-tested) format as you type and
    **validate** the number, with inline error messages for **email** and **mobile** on the sponsor register form.
    Sponsor phone is stored as `+60 12-345 6789`.
  - Required-field `*` markers are now **red** on the sponsor register + complete-details forms.
- **Partner login rename + footer cleanup:** `/admin/login` now reads **"Partner Login"** with subtitle **"For partner
  organisations and invited individuals"** (was "Admin Login / Partner organisation portal") — so an invited volunteer
  interviewer, not only an organisation, reads themselves into it; the top badge reads "Partner". The redundant
  **"Admin" link in the site footer was removed** (the partner portal is still reachable via the header's Log in ▾ →
  Partner). i18n en/ms/ta (parity 1652; Tamil first-draft). No migration. 1411 pytest + 183 jest; `next build` clean.

## [2.23.0] — Phase E Sprint E1c: sponsor self-serve auth (email/password + Google) (2026-05-31)

- **Sponsors now have a real self-serve account, not just a Google-only thin form.** Acting on live feedback after E1:
  - **Dedicated login page** at `/sponsor/login` (styled like `/admin/login`) — email/password + Google + forgot-password.
    The header's **Sponsor** menu (desktop + mobile) and the Sign-Up chooser now route here / to `/sponsor/register`
    (previously the old `/sponsor/register-interest` lead form, now unlinked).
  - **Full registration** at `/sponsor/register` with the requested fields: **Full name (as in NRIC/Passport), Email,
    Password** (live rule checks: ≥8 chars · upper+lower · 1 number), **Re-enter password**, **Phone** (Malaysian +60
    default), **Source** ("How did you find us?"), and **PDPA consent**. Google is offered too — a Google sponsor lands
    on a **"complete your details"** step (phone/source/consent) since OAuth only yields name+email.
  - **Isolated sponsor auth stack** (mirrors the admin pattern, supersedes E1's `KEY_SPONSOR_SIGNIN` student-client
    hack): new `sponsor-supabase.ts` (own `storageKey: 'halatuju_sponsor_session'`, email/password + Google + reset),
    `SponsorAuthProvider`, `/sponsor/auth/callback`. The sponsor session never touches the student NRIC/anonymous flow.
  - **Backend:** `Sponsor` gains `phone`, `source`, `consent_at`, `consent_version` (**migration `scholarship/0032`**,
    additive, applied migrate-first via Supabase MCP). The register endpoint now requires name+phone+source+consent and
    also **completes** an incomplete (Google/legacy) row; `/sponsor/me` reports `profile_complete`; admin vetting shows
    phone+source. Tests: sponsor suite 12 → 15.
  - **Landing-page login buttons now match the dashboard** — extracted the `Log in ▾ {Student/Sponsor/Partner} | Sign Up`
    cluster into a shared `components/AuthButtons.tsx` used by both `AppHeader` and the landing nav (the rest of the
    landing page is unchanged). Pure `lib/sponsorAuth.ts` (`checkPassword`/`SPONSOR_SOURCES`) is node-env unit-tested.
  - **Deferred (TD-071):** Cloudflare Turnstile on signup (shown in the mockup) — email confirmation + admin vetting gate
    fakes for now. **MY-only phone** for now (TD-072). 1411 pytest + 178 jest; i18n parity 1650 (Tamil first-draft);
    `next build` clean. **Not click-tested** (OAuth + admin flows — TD-070). See `docs/retrospective-v2.23-sponsor-auth.md`.

## [2.22.0] — Phase E Sprint E1: sponsor accounts + admin vetting (no student data) (2026-05-31)

- **First slice of the safeguarded sponsor marketplace (`docs/scholarship/phase-e-sponsor-roadmap.md`).** Anyone can self-register as a sponsor, an admin vets them, and an approved sponsor lands in a portal shell. **Zero student data is exposed anywhere in this slice** — browsing the (anonymised) student pool arrives in E2, which stays gated on the lawyer review before any real student is shown.
  - **Backend (E1a, committed `99c7937`):** new `Sponsor` model (`supabase_user_id`-keyed, status `pending`/`approved`/`rejected`/`suspended`; **migration `scholarship/0031`**, table `sponsors`, applied migrate-first via Supabase MCP with **RLS deny-by-default**). `SponsorMixin` mirrors `PartnerAdminMixin` (resolve sponsor by Supabase UID; `require_approved_sponsor` gate for E2+). Sponsor self-service: `POST /api/v1/sponsor/register/` (idempotent; rejects anonymous guests; emails the admin) + `GET /api/v1/sponsor/me/` (own account or `{registered:false}`). Admin vetting: `GET /api/v1/admin/sponsors/[?status]` + `POST /api/v1/admin/sponsors/<id>/review/ {approve|reject|suspend}` (reviewer-gated, stamps `reviewed_at`/`reviewed_by`). `SponsorSerializer` is an **allowlist** (id/name/email/organisation/status/is_approved/created_at — all read-only). NRIC-gate middleware whitelists `/api/v1/sponsor/` (sponsors have no NRIC). +12 tests (`test_sponsor.py`).
  - **Frontend (E1b):** `/sponsor` portal — six states off `getSponsorMe()`: loading · signed-out (Google sign-in) · register form (name/organisation/note) · pending · approved (a "browsing coming soon" E2 shell) · inactive (rejected/suspended). `/admin/sponsors` vetting table (status filter) with per-row **Approve / Reject / Suspend** + a "Sponsors" admin nav link.
  - **Sponsor sign-in bypasses the student NRIC modal.** A sponsor does a **direct Google sign-in** flagged by a one-shot `KEY_SPONSOR_SIGNIN` (sessionStorage) that `/auth/callback` reads to route back to `/sponsor` — it never sets `KEY_PENDING_AUTH_ACTION`, so the student auth-gate / NRIC-claim flow is never triggered for a sponsor. No change to the delicate `AuthGateModal`.
  - **No migration in E1b** (frontend only). i18n `sponsorPortal.*` + `admin.sponsors.*` across en/ms/ta (parity **1598**; **Tamil first-draft**, queued for refine). Tests: **1408 backend** pytest (+12 from E1a) + **172 jest** (+1); `next build` clean, both new routes compiled, no `rules-of-hooks` errors.
  - **Not yet click-tested interactively** — the sponsor Google-OAuth sign-in and the admin approve/reject can't run headless; needs a live smoke before E2 faces real sponsors (TD-070).

## [2.21.0] — Elective subjects persist + cap raised 2 → 7 (2026-05-31)

- **SPM electives now survive a logout/login, and a student may enter up to 7 of them** (was 2). Two related fixes shipped together.
  - **Bug fixed: electives silently lost on logout/login.** Electives had no durable identity — *which* grade keys were electives lived only in browser localStorage (`KEY_ELEKTIF`), was never synced, and was never re-hydrated on login. On reload the grades form kept only `core ∪ aliran ∪ elektif` grades, so the electives were dropped — and a re-save propagated the loss to the DB. Fix: new `StudentProfile.elective_subjects` JSONField (**migration `0052`**, additive) — the durable record of which subjects are electives, mirroring `stream_subjects` (TD-063). Synced in `/profile/sync/`, returned by the profile GET, and **re-hydrated on login** (`auth-context` now restores `KEY_ELEKTIF` from `elective_subjects` *and* `KEY_ALIRAN` from `stream_subjects` — fixing the latent aliran case too).
  - **Feature: elective cap 2 → 7.** Via a new `MAX_SPM_ELECTIVES` constant (single source). SPM has no official subject cap and high achievers sit many (11-A cases); the form now allows up to 7 electives. The **merit engine is unchanged** — Sec3 still scores only the *best 2* electives (`remaining.sort()[:2]`); more electives just enlarge the pool, so the golden master is untouched. Raising the cap also *improves* accuracy: high achievers can now enter their true best electives, and students no longer become wrongly ineligible when a course's required elective couldn't fit in 2 slots.
  - **Migrate-first care (TD-025):** `StudentProfile.Meta.db_table = 'api_student_profiles'` (not the Django default) — the prod `ALTER` targets that table; a column first added to the legacy `student_profiles` table by mistake was caught pre-deploy and dropped. **No historical backfill:** 485/491 existing profiles have empty `stream_subjects`, so a grades-derived backfill would mislabel stream subjects as electives — the fix prevents future loss and deletes nothing.
  - **Out of scope (TD-069):** the STPM flow's SPM-prerequisite electives use a separate subsystem (`spm_prereq_grades` + `halatuju_spm_elektif`) and stay capped at 2 — a follow-up.
  - +7 backend tests (merit best-2 under 5/7 electives, sync round-trip, default empty); backend 1396, jest 171, `next build` clean.

## [2.20.0] — "Cikgu Gopal" document-help coach on the Documents tab (2026-05-31)

- **A warm, encouraging helper now appears when a student's document upload comes back with a soft mismatch.** On the /application **Documents** tab, beneath the existing amber/grey chip (IC name/NRIC mismatch, supporting-doc name/address/wrong-doc/unreadable), a soft-blue **"Cikgu Gopal"** note explains *why* the document needs what it needs and gently nudges the student to re-upload — in their own language (en/ms/ta). It is **proactive** (fires only on a real mismatch, never under a green chip) and **never a chat box**.
  - **Coach, never ghostwriter.** The model is instructed to explain and encourage but to refuse to write the student's application answers/essays, and it has no access to (and must never reveal) scores or reviewer notes. Enforced by guardrail tests on the built prompt.
  - **Structurally firewalled from admin data.** The engine (`help_engine.generate_document_help`) receives **only** a doc-type + the already-decided verdict code + the student's first name — there is no parameter through which a `SponsorProfile`, `InterviewSession`, score, or anomaly could reach it. Asserted by a signature test, not prompt-trust.
  - **Only phrases, never decides.** The verdict is computed upstream by the existing deterministic matchers / Vision OCR (`vision.doc_student_verdict`, the IC nric/name matchers); the coach just puts a kind voice on it (consistent with the "Gemini extracts, matchers decide" decision).
  - **Soft, never blocks; degrades gracefully.** New `GET /api/v1/scholarship/documents/<pk>/help/` (own-doc scoped) reuses the shared `profile_engine._call_gemini_text` Gemini seam on the free tier, with an hourly per-application cap. When the AI is unconfigured/throttled/errored, the frontend shows pre-written i18n **fallback copy** keyed by the verdict — the student is never left with a cold, silent chip.
  - **No migration** — the coach stores nothing; it reads existing verdict columns. New `help_engine.py` + `DocumentHelpView` + `DocumentHelpCoach.tsx` + pure `lib/documentHelp.ts` (`shouldShowCoach`/`fallbackKeyFor`). Tests: **+18 backend** (engine + endpoint + guardrail/firewall, all Gemini mocked) → 1391 pytest; **+8 jest** (pure logic, node-env) → 171 jest; `next build` clean. i18n en/ms/ta `scholarship.docs.help.coachLabel` + `fallback.*` (parity 1559; **Tamil first-draft**, queued for refine). Stitch screen `daf30389` (HalaTuju B40 Assistance) approved before build.

## [2.19.0] — Four rejection buckets with differentiated decline emails (2026-05-31)

- **Rejections are now categorised, and each bucket gets its own decline email** (suggestive of the reason, never blunt — a fully generic note is more frustrating). New `ScholarshipApplication.rejection_category` (+ `rejected_at`/`rejected_by`; **migration `0029`**, additive, migrate-first):
  - **merit** — engine, academic floor not met → email hints "especially competitive on academic results".
  - **need** — engine, financial-need test not met → email hints "directed to students in the greatest financial need; prioritised on that basis".
  - **ineligible** — engine, hard gate (no consent / not pursuing tertiary this year / IPTS-only) → the existing generic warm decline.
  - **interview** — admin action, "reviewed but not selected", available from **shortlisted onward** (poor documentation is grounds — no formal interview needed) → an extra-thankful email ("thank you for submitting your documents… with the limited funding this round we could only support those who most met **both need (primarily) and merit**").
  - **contractual** — admin action, failed post-award steps, available on **accepted** only → generic decline (the admin-typed reason is deferred — TD-068).
  - Buckets merit/need/ineligible are set automatically: the engine already recorded *why* it rejected, so `evaluate()` now returns a `category`, `score_application` persists it at submit, and the scheduled reveal picks the email via `emails.send_decline_email(category=…)`. The two admin buckets go through a new reviewer-gated `AdminRejectView` (`POST …/reject/ {category}`) → `services.admin_reject()`, which validates the status (interview from shortlisted/profile_complete/interviewing/interviewed; contractual from accepted only), stamps who/when, and sends the bucket email immediately.
- **Admin UI:** a **"Decline (after review)"** button beside Verify-&-accept (shortlisted onward) and a **"Decline (contractual)"** button on accepted students (both with a confirm), a red **rejection-bucket badge** next to the status, and the Review & actions panel is now hidden **only** for pre-shortlist rejections (merit/need/ineligible) — interview/contractual rejections keep the documents + interview record visible for audit. New trilingual templates (en/ms/ta; Tamil first-draft) + `admin.scholarship.reject.*` (parity 1551). +22 tests (emails asserted via `mail.outbox`; no real mail in CI), backend 1373.

## [2.18.0] — Phase D: Gemini v2 profile refine with interview findings (2026-05-31)

- **Phase D — second Gemini pass refines the sponsor profile with the interview.** On the admin sponsor-profile card, a reviewer can click **"Refine with interview findings (AI)"** → Gemini takes the existing draft profile + the **submitted** `InterviewSession` (each finding's verdict + the interviewer's own rationale, the 1–5 rubric scores, and the overall note) → a refined **final profile (v2)**, shown in its own panel with an AI badge + finalised timestamp. Same guardrail as the draft (*use only what's given; don't invent*); where the interview confirmed/clarified something it's folded in, where it raised a new concern it's reflected honestly. Completes the post-shortlist roadmap's Phase D and the "Profile generation" bucket. **Admin-facing for now** — the sponsor consumer is gated on Phase E (no portal yet). New `SponsorProfile.final_markdown` / `final_model_used` / `finalised_at` (**migration `0028`**, additive, applied migrate-first). New `refine_sponsor_profile()` + `REFINE_PROMPT`; the raw model call was extracted into a shared `_call_gemini_text` seam that **both** the draft and refine functions now use (the draft path was refactored onto it with no behaviour change — tests mock the one seam). `AdminFinaliseProfileView` is **reviewer-gated**: 400 `no_draft` if no draft, 400 `no_interview` if no submitted interview, 503 on engine error; the serializer exposes the 3 new fields read-only — **no Gemini in any GET**. The FE Refine button stays disabled until a submitted interview exists. +13 tests (all mock Gemini), backend 1351. i18n en/ms/ta `admin.scholarship.finalProfile.*` (parity 1540; Tamil first-draft). Cost: ~$0.001 per click, on demand only.

## [2.17.0] — Gemini doc-assist + interview gap-spotter, consent-gating, supporting-doc OCR (2026-05-31)

- **Interview gap-spotter (admin-on-demand Gemini, Phase B).** On the Pre-interview-flags card, a reviewer can click **"Suggest interview gaps (AI)"** → one Gemini call reads the applicant's *typed narrative* (aspirations / plans / fears / daily life / family context + funding/pathway/income context) → 3–6 suggested interview questions, each `{code, question, why}`, stored on the application and rendered beside the deterministic anomaly flags. The gaps are **capturable as interview findings** (a combined findings list merges anomalies + gaps, each keyed by `code`, writing into the same `findings` dict — no backend change to interview capture). Unlike anomalies (i18n-resolved `{code, params}`), a gap **carries its own dynamic text** (Gemini-written, never i18n'd) — only `code` is stable so a verdict can attach. New `interview_gaps` JSONField + `interview_gaps_run_at` (**migration `0027`**, additive, applied migrate-first). New `gap_engine.py` (reuses `profile_engine` language/context helpers + the shared `vision._call_gemini_json` seam; normalises/slugifies/dedupes codes, clamps ≤6, drops empties, never fabricates). `AdminSuggestGapsView` is **reviewer-gated**; the serializer exposes the stored gaps as a **plain read-only** field — **no Gemini in any GET** (`get_anomalies` untouched). +8 tests (all mock Gemini), backend 309. i18n en/ms/ta `admin.scholarship.gaps.*` (parity 1533; Tamil first-draft). Cost: ~$0.001 per click, on demand only.

- **Document-assist: Gemini reads supporting docs on upload + gives the student feedback.** When a student uploads a weak-OCR supporting doc (salary slip / EPF / utility bill / results slip / offer letter), Gemini now **extracts the fields** (name, employer, income, address, amount, subjects…) from the OCR text, and the existing **deterministic matchers decide** a soft verdict (so it can't be a Gemini hallucination): the **student** sees a specific nudge — *"the name on this doesn't match you or your parent/guardian"*, *"the address on this bill doesn't match your home"*, *"this doesn't look like a salary slip"* — and **self-corrects at upload** instead of an admin↔student round-trip; the **admin** sees the extracted values on the applicant detail. Automatic, **soft / never-blocking**. New `vision_fields` JSONField (**migration `0026`**, additive). **Guardrails:** 8 MB/file size cap, 40-doc/application cap, and an hourly per-application **AI throttle** that skips only the billable Gemini call (upload + free checks still run → *"we'll review this manually"*) — never locks a student out. Cost knob `DOC_ASSIST_ONLY_WHEN_UNCERTAIN`. Reuses one OCR pass; structured JSON output; +16 tests (all mock Gemini), backend 301. `apiRequest` now carries the backend error `code` so guardrail messages localise.
- **Step-4 live-refresh after a document/consent change.** Uploading or deleting a document (or giving consent) now refreshes the page's application status + completeness immediately (new `getScholarshipApplication` + an `onChange` callback from the Documents/Consent components), so e.g. deleting a compulsory doc reflects the `profile_complete → shortlisted` rollback without a reload. Only `app` is refreshed, not the form — in-progress story/funding edits are preserved.
- **Honest funnel: un-confirm a profile edited back to incomplete.** If a `profile_complete` application is edited below complete (the student deletes a compulsory document, or clears a required story field), it now rolls back to `shortlisted` and clears `profile_completed_at` — so the status never claims "complete" on an incomplete profile (which previously left the admin accept-gate blocking a "complete"-looking application). New `revert_if_profile_incomplete()` called on document delete + details PATCH; only touches `profile_complete` (interviewing/interviewed/accepted are the admin's). +4 tests. No migration.
- **MyKad name OCR — skip card header/label lines.** `vision._extract_name` (which feeds the IC name used by the now-live consent identity gate) picked the *longest* all-caps line, so a card label like "WARGANEGARA MALAYSIA" could be grabbed instead of the name — risking a false `ic_name_mismatch` block. Added a header-phrase blocklist (KAD/PENGENALAN/MYKAD/MALAYSIA/WARGANEGARA/LELAKI/PEREMPUAN/ISLAM): a line made up *entirely* of those tokens is skipped, while a name that merely *contains* one (e.g. "NUR MALAYSIA BINTI ALI") is kept. +4 tests. No migration.
- **Guardianship letter is now optional, not a hard block.** Under-18s with a non-parent guardian (grandparent / legal guardian / sibling / relative) no longer must upload a guardianship letter to consent — they *may* upload one, but it's optional. Removed the `guardianship_letter_required` 400 in `ConsentView`, dropped the letter from `guardian_docs_done` (now always True), and removed the FE block + warning. parent_ic stays compulsory for everyone.
- **Tech-support box: email is now a `mailto:` link.**
- **Consent step layout.** The outstanding-items checklist moved *below* the Give-consent button (was on top), so the consent text + action button lead. The **(temporary, testing-only)** tech-support box moved into the left step menu so it's reachable on every step (mobile fallback below the content, since the menu is hidden < lg). Marked `TEMP` in code for easy removal after testing.
- **/apply state list — federal territories now carry the "W.P." prefix** ("W.P. Kuala Lumpur" / "W.P. Putrajaya" / "W.P. Labuan"), matching the /profile + /onboarding lists which already used it (the /apply list was the inconsistent one). Backend `_normalize_state` strips "W.P." so anomaly-engine state matching is unaffected. Normalised the 1 existing short-form profile row to match.

- **Internal cron endpoint + `ADMIN_NOTIFY_EMAIL` fix.** Added `POST /api/v1/internal/cron/<job>/` (shared-secret `X-Cron-Secret`, constant-time compare, whitelisted jobs only) so Cloud Scheduler can run `alert_vision_outage` (daily) and `send_pending_decision_emails` (~15 min) inside the running api service — no separate Cloud Run Job replicating plain-env secrets. **Also fixed a latent bug:** `ADMIN_NOTIFY_EMAIL` was set as a Cloud Run env var but never read into Django settings, so every admin-notify email (sponsor interest, profile-complete, outage alert) silently no-op'd; now read in `base.py`. New `CRON_SECRET` setting. +7 tests (277 backend). No migration.

- **Soft OCR identity checks on supporting documents.** On upload, results slip / STR / salary slip / EPF / offer letter / utility bills now get a Google-Vision **full-text** read (generic, not MyKad-structured) and a tolerant **presence** check: does the student's *or* a parent/guardian's name appear? Utility bills also check whether the **home address** appears. Verdicts (`found` / `not_found` / `unreadable`) are **soft — never block** — and surfaced both to the **student** (a chip under each upload) and the **interviewer** (name/addr badges on the admin doc list). New `vision_name_match` / `vision_address_match` fields (**migration `scholarship/0025`** — apply migrate-first). New `extract_text` + `name_present` / `address_present` matchers (reuse the existing token canonicaliser). +7 backend tests. i18n en/ms/ta (parity 1518). Cost: +1 Vision call per uploaded supporting doc.

- **`/application` Step-4 polish (batch).**
  - **Story:** "What is your daily life like?" and "What worries you most / what support would help?" are now **compulsory** (`*` + added to the story completeness gate). Home address still pre-fills from the profile when set.
  - **Funding:** the student's **decided study** (from /apply) now shows read-only between the info box and the programme-length question; programme-length label is now "How long is your programme? **(estimated, in years)**".
  - **Consent:** a **tech-support info box** ("Email tamiliam@gmail.com or call 012-337 5709…") now sits below the consent step so a stuck student has a human to reach.
  - **Documents:** removed "(for under-18s)" from the intro (parent IC is required for everyone) and "(optional)" from the photo doc. (Income proof remains: any one of STR / salary slip / EPF satisfies it.)
  - i18n en/ms/ta (parity 1514); story-gate test updates across consent/details/phase-c/admin suites (264 backend, jest 163). No migration.

- **Consent is now a properly-gated final step (Step 4 / `/application`).** Previously an adult could give consent with nothing else done. Consent now requires the whole profile to be complete first, and the student's uploaded IC to be machine-readable and match their name + NRIC — and the Consent step **lists every outstanding item at once** so it can be fixed in one pass (the give-consent button stays disabled until the list is empty; the server enforces the same list).
  - New `consent_blockers(application)` (services.py) returns all unmet preconditions as codes: `quiz_incomplete`, `story_incomplete`, `address_incomplete`, `funding_incomplete`, `ic_missing`, `results_slip_missing`, `parent_ic_missing`, `income_proof_missing`, plus identity checks on the student's own IC — `ic_nric_mismatch`, `ic_name_mismatch`, `ic_unreadable` (poor image → re-upload) and `ic_service_down` (Vision errored → try later). NRIC must match exactly; a *partial* name (subset — same person, shorter/longer form) is allowed since the NRIC is the hard key.
  - `ConsentView` GET returns `blockers`; POST hard-blocks with `{error: 'consent_not_ready', blockers: [...]}`. Existing minor guardian-gate (parent IC name/NRIC match) unchanged. Reuses the existing Vision OCR fields (read once at upload, cached in the DB — no repeat OCR calls).
  - Frontend `ScholarshipConsent` renders the blocker checklist and disables the consent toggle/button until ready. New i18n labels (en/ms/ta, parity 1512).
  - No migration. Backend: scholarship suite passing (8 new consent tests). jest 163; `next build` clean.
- **Vision-OCR outage alert.** A read-only check (`detect_vision_outage`, no Vision API calls) + `alert_vision_outage` management command: if every IC/parent-IC OCR attempt in the last 24h errored with none succeeding (genuine service errors, not blurry images), it emails `settings.ADMIN_NOTIFY_EMAIL` (tamiliam@gmail.com) — `send_vision_outage_alert_email`. Idempotent-by-cadence: schedule daily so it reminds once a day while down. 8 new tests. **Scheduler wiring is a deploy-time ops step** (Cloud Scheduler → Cloud Run Job, alongside the still-pending decision-emails job). No migration.

## [2.16.8] — Apply form: rename Support step to "Support I Need" (2026-05-30)

- **Apply form — renamed the Support step.** "Support I'd Like From Us" → **Support I Need** (ms "Bantuan Yang Saya Perlukan"; ta "எனக்குத் தேவையான உதவி"). Shorter and first-person; drops the "us" so there's no pronoun-referent question at all. i18n-only, parity 1498.

## [2.16.7] — Apply form: household-size cap + income formatting (2026-05-30)

- **Apply form (My Family) — household-size cap + income formatting.** The household-size field now rejects a value above **20** on submit (new `householdSizeMax` validation + error message, jumps to the My Family tab; the ≥1 rule is unchanged) and gains a `max={20}` hint. The combined monthly income field now displays as **`3,000.00`** (thousands separators + two decimals): it became a text input that shows raw digits while focused and the formatted value on blur, with only the raw digits stored for submission. New testable `formatMoney2dp` helper. i18n parity 1498 × en/ms/ta; jest 163.

## [2.16.6] — Admin applicant-detail polish (masonry, income/email, label cleanup) (2026-05-30)

- **Admin applicant detail — income formatting + email link.** Household income now renders as `RM 2,400` (space after RM + thousands separators) instead of `RM2400`. The contact email is now a blue `mailto:` link so it reads as an email at a glance.
- **Admin applicant detail — relabelled the Support help fields.** "Help: university" → **University application**, "Help: scholarship" → **Scholarship application** (en/ms/ta). Labels render uppercase via the existing field styling. i18n-only.
- **Admin applicant detail — removed the "Consent to contact" field.** Consent is a hard requirement to submit an application, so it is always "Yes" and carries no signal for the admin. Dropped the field from the Support card and removed the now-orphaned `admin.scholarship.consentToContact` i18n key from en/ms/ta (parity 1497). The submission-side consent logic (apply-form toggle, validation, payload) is untouched.
- **Admin applicant detail — cards float (masonry) instead of a fixed grid.** The four summary cards were a row-major 2×2 grid, so Family & Finances was pinned to the second row beneath the tall Academic card, leaving a gap under the shorter About card. Restructured into two independent columns (left: About → Family & Finances; right: Academic → Support) so each column packs its cards top-down and Family floats up directly under About. Self-corrects whichever column is taller. Frontend-only, no migration. (Minor: on mobile the single-column order becomes About → Family → Academic → Support.)

## [2.16.5] — Apply-form first-person voice + admin "Student's note" merge (2026-05-30)

Two polish items continuing the 2.16.x admin/apply pass.

- **First-person voice on /apply** — the form mixed voices ("About Me", "My Family", but "Your Plans", "Your SPM / STPM Results", "Support You'd Like From Us"). Unified every section title + ownership label to the student's own voice: **My Plans**, **My SPM / STPM Results**, **Support I'd Like From Us**, "Number of people in **my** household", "Scholarships **I** have applied for or hold". Direct questions still address the student as "you" (the natural way a form asks) and the organisation stays "us" — so "you = student / us = HalaTuju" holds with no pronoun collision. Chose **"Support I'd Like From Us"** over the literal "From You" precisely to avoid "you" meaning two parties (student in the questions, org in the title) on one screen.
- **Context-aware results title** — the Results step now names the exam the student actually sat: **"My SPM Results"** for SPM leavers, **"My STPM Results"** for STPM students, instead of the generic "My SPM / STPM Results". New `resultsSpm` / `resultsStpm` keys + a `sectionKey()` helper wired into all three render sites (sidebar nav, progress subtitle, card heading).
- **Admin "Student's note"** — on the applicant detail page, the two free-text memos ("Anything you'd like to add?" from Plans + "Anything else you'd like us to know?" from Support) now sit in **one** box, each question labelled, instead of two separate cards (one of them mislabelled "Personal appeal"). The Plans block (chosen programme/pathway, top choices, considered pathways) is now nested into the Academic card under a divider rather than a standalone full-width card — tighter, fewer boxes.
- Additive only — **no migration**. i18n parity **1498 × en/ms/ta** (Tamil first-draft, refine pending); jest **160**; `tsc` clean on both touched pages; `next build` clean.

## [2.16.4] — Admin: full name, login email, and a merit-calc bug fix (2026-05-30)

Three fixes from reviewing an applicant whose card showed a username, no email, and a too-low merit:

- **Full name** — the admin title + list now use the **declaration signature** (the full legal name typed at submit, e.g. "SHARMILA A/P SANGGAR") in preference to `profile.name`, which is often the Google display name/handle ("Sharmila 1204"). New `_full_name()` helper used by both admin serializers.
- **Email** — the Contact card now shows the applicant's **login/comms email** (`notify_email`, captured at submit from their Google account) when the optional `contact_email` is blank. (The applicant *did* log in with an email; it just wasn't being surfaced.) `notify_email` added to the admin serializer.
- **Merit-score bug** — `get_merit_score` scored grades directly from `profile.grades`, which stores History under the key `hist`, while the engine's core expects `history`. So **History was read as a fail (G)** and merit was understated (e.g. 62.6 → **68.9** once History is counted). Fixed by applying the same `hist`→`history` rename the eligibility flow uses. Affects every applicant's displayed merit.
- Additive only — no migration. Backend test covers all three; golden masters unchanged; jest 155; `next build` clean.

## [2.16.3] — Admin: link chosen programme to its HalaTuju course page (2026-05-30)

On the admin applicant detail, the chosen programme + each top-3 course choice are now **clickable links** to the public HalaTuju course page (opens in a new tab), so an admin can see the full course detail — institution, requirements, fees — when the course name alone isn't enough. Routes by qualification: SPM → `/course/<course_id>`, STPM → `/stpm/<course_id>` (the `course_id` is already on `chosen_programme` / `top_choices`). Frontend-only; `next build` clean.

## [2.16.2] — Admin applicant profile refinements (2026-05-30)

Refines the complete-profile admin view (2.16.1) per review — reordered, de-cluttered, pathway-context-aware.

- **Box order** now Contact · Academic · Plans · Family & finances · Support (then Story/Funding when filled). Title shows the student's full name (`profile.name`, e.g. "KRISHA VYSNAVI A/P MUTHUKKUMAAR") — confirmed already correct.
- **Contact:** removed the duplicate name (the title shows it) and "Referred by"; order is NRIC · Phone (now `formatPhone`-formatted) · Email · Address · Call language.
- **Academic:** replaced "SPM A" + "CoQ score" with a single **Merit score** — the course-guide ranking number (new `merit_score` serializer field: SPM = computed academic+CoQ merit via the engine; STPM = PNGK). Removed the "income: per-capita …" shortlist-reason line. Still SPM/STPM-aware (MUET + STPM grades for STPM).
- **Plans** (renamed from "My Plans"): now **pathway-context-aware** — institution pathways (matric/STPM) show Pre-U track + institution; programme pathways (asasi, university, …) show the chosen programme and hide the N/A Pre-U track. Removed "Intends tertiary" + "Decided?" (intermediate steps) and the empty "Other scholarships". **UPU status** now shows a readable label (e.g. `public_other` → "Public institution (not via UPU)"). `pathways_considered` / uncertainty rows show only when present.
- **Investigation (the "still-deciding note on a decided student"):** the note is the uncertain-branch free-text, but `buildApplicationPayload` submits `uncertainty_note` **regardless of branch** (scholarship.ts), so a `sure`/decided applicant can still carry it — it's effectively a general note, mislabeled. Fix: relabel to **"Student's note"** and show it independent of branch. (A follow-up could clear `uncertainty_note` on the /apply form when the student is `sure`.)
- **Support:** removed the declaration signature.
- Additive only — no migration. Backend test + golden masters unchanged; jest 155; `next build` clean; i18n parity 1495 × en/ms/ta.

## [2.16.1] — Complete applicant profile on the admin detail page (2026-05-30)

The admin applicant detail page showed only a thin slice of what the student entered at /apply (school, qualification, SPM A, income, STR, intended_pathway). Investigation confirmed **no data was lost** — everything is stored; it just wasn't displayed. This surfaces all of it as a complete, grouped profile.

- **`AdminApplicationDetailSerializer` extended** with the profile/application fields it wasn't exposing: contact (`contact_phone`, `contact_email`, `preferred_state`, `postal_code`, `city`, `preferred_call_language`, `referral_source`, `guardians`), academic detail (`muet_band`, `coq_score`, `grades`, `stpm_grades`, `spm_prereq_grades`), "Your story" narrative (`first_in_family`, `parents_occupation`, `siblings_studying_count`, `family_context`, `daily_life`), and `consent_to_contact` / `declaration_name` / `declared_at`. (`declaration_name` was already in the FE type but never sent — now populated.) The My Plans / My Support fields were already exposed but untyped on the FE; now typed.
- **Admin detail page rebuilt** from two thin cards into grouped sections: **Academic · Contact & identity · Family & finances · My Plans · My Support · Your story · Funding**. The "Your story" card renders only when the student has filled it (post-shortlist).
- **SPM/STPM-aware** (per request): the Academic section shows SPM A + SPM grades for SPM applicants, and STPM PNGK + MUET + STPM grades (+ SPM prerequisites) for STPM applicants — no more empty STPM fields on an SPM profile or vice versa.
- Additive only — **no migration, no data change**. Backend test asserts the new fields are present; scholarship suite + golden masters unchanged; jest 155; `next build` clean; i18n parity 1489 × en/ms/ta (Tamil first-draft).

## [2.16.0] — Branded entry + sponsor-interest capture (2026-05-30)

Replaces the no-op `/login` + single student-only auth modal with a branded entry surface for HalaTuju's user types — **without** regressing the open, browse-first course guide.

- **Header**: a **"Log in"** dropdown (Student → existing Google + deferred-NRIC modal · Sponsor → register-interest · Partner → existing `/admin/login`) + a **"Sign Up"** button → a new `/get-started` chooser (Sign up as student / Register as a sponsor + "Already have an account? Log in"). Reuses `AuthGateModal` for all student auth; no new student auth path.
- **Browse-first preserved (deliberate)**: the new entries are options, not gates. Anonymous quiz/eligibility/course-search stay open; NRIC stays a deferred soft-claim at save/apply. The NRIC gate's behaviour is unchanged — only `/api/v1/sponsor-interest/` was added to its whitelist.
- **Sponsor = "register interest"** (no self-serve account yet — the real sponsor portal is a future Phase E). New public `POST /api/v1/sponsor-interest/` (`AllowAny`) + `SponsorInterest` model (`sponsor_interests` table, RLS-on/service-role-only like its siblings) stores the lead and emails the admin (`ADMIN_NOTIFY_EMAIL`). A `/sponsor/register-interest` page captures name/email/organisation/message. Admins can list leads via `GET /api/v1/admin/sponsor-interest/`.
- **Admin/Partner stays invite-only** (already the case) — the entry just links to `/admin/login`. **Mentor** and **non-Google student login** are explicitly out of scope.
- Tests: `+6` (`test_sponsor_interest.py`: public submit creates row + emails; missing name/email → 400; gate doesn't block the public path; admin list requires admin). Golden masters + NRIC-gate suites unchanged; jest 155; `next build` clean; i18n parity 1442 × en/ms/ta (Tamil first-draft).

## [2.15.0] — Phase C: post-shortlist handoff + interview layer (2026-05-30)

Builds the admin side of the post-shortlist funnel (`docs/scholarship/post-shortlist-vision.md` Phase C) and — critically — hardens the **submit → next-step handoff** that exploration found unsound just as the first real batch of students reached Step 4.

**New status funnel:** `shortlisted → profile_complete → interviewing → interviewed → accepted` (plus `rejected`). `assigned_to` is an FK, not a status.

- **Explicit "Confirm & submit" (handoff fix).** Step 4 had no "I'm done" action — completion was a silent computed-on-read state the admin couldn't see. New `POST …/applications/<id>/confirm/` (`confirm_profile` service) flips `shortlisted → profile_complete`, stamps `profile_completed_at`, and emails the admin (`ADMIN_NOTIFY_EMAIL`, skipped if unset). The student sees a Confirm button once all parts are done. **Completion is not a freeze** — `POST_SHORTLIST_EDITABLE` keeps Step 4 (incl. document upload via `_current_application`) open through the funnel so the student can add more if asked.
- **Hard accept-gate.** `AdminVerifyAcceptView` now refuses to accept an application whose live `application_completeness` isn't complete (`400 incomplete_profile` with the breakdown) — no override. The admin detail page disables Accept and lists the missing parts.
- **Request more documentation.** `POST …/request-info/` stores a note + emails the student (trilingual); the note shows as a banner on their Step 4. No status change.
- **Admin roles.** `PartnerAdmin.role` ∈ {super, reviewer, viewer} (kept alongside `is_super_admin`, expand-contract; `is_super` property bridges them). `viewer` is read-only; write endpoints (accept, assign, interview, referee, generate/publish profile, request-info) require reviewer/super. `AdminRoleView` returns `role`.
- **Assignment.** `ScholarshipApplication.assigned_to` FK + `?assigned=me|none|<id>` list filter + an assignment dropdown (`assignable-admins` endpoint) + an "Assigned to me" filter and Assigned column on the list.
- **InterviewSession + capture UI.** New `interview_sessions` table (findings keyed to the anomaly `{code}` contract → `{verdict ∈ resolved|still_unclear|new_concern, rationale ≤140}`, plus a 1–5 rubric + overall note). The admin detail "Pre-interview flags" card gains a capture form; Save-draft (→ `interviewing`) and Submit (→ `interviewed`, `submit_interview` service). Verdict enum + rationale length validated server-side.
- **Migrations** `courses/0051` (role) + `scholarship/0023` (assigned_to, profile_completed_at, status/verdict choices, info-request fields, InterviewSession) — additive, applied migrate-first via Supabase MCP; the new `interview_sessions` table gets RLS + an advisors pass.
- Tests: **1270 backend** (+21 `test_phase_c.py`: confirm, hard-gate, role gating, assignment, interview draft/submit + validation, request-info), golden masters unchanged (SPM 5319 / STPM 2026); jest 155; `next build` clean; i18n parity 1417 × en/ms/ta (Tamil first-draft).

## [2.14.0] — TD-061 + TD-062: drop dead columns, orphan-blob cleanup (2026-05-30)

**TD-062 — orphan Storage blob cleanup.** New `storage.list_objects(prefix)` helper + `manage.py cleanup_orphan_blobs` command: walks the `b40-documents` bucket's `{app}/{doc_type}/{uuid}` layout, diffs leaf paths against `ApplicantDocument.storage_path`, reports orphans (dry-run default; `--apply` deletes via the existing `delete_objects`). Sweeps the historical blobs leaked by pre-S15 "Remove" clicks. 3 tests (mocked Storage). Running `--apply` on prod is a separate manual step (needs the service-role key locally).

**TD-061 — drop 4 dead columns under expand-contract.** Removed `StudentProfile.family_income` / `siblings` / `phone` and `ScholarshipApplication.siblings_studying` — all superseded (by `household_income` / `household_size` / `contact_phone` / `siblings_studying_count` respectively) in S14/S15 but never fully retired.

- **Latent bug fixed in passing:** the `/profile` page reads & writes `household_income`/`household_size`, but the GET response and `ProfileUpdateSerializer` still carried the *legacy* `family_income`/`siblings` and **not** the canonical ones — so a student editing household income/size on `/profile` saw blanks and had their edit silently dropped (only `/apply` could write them). Repointing the endpoint to the canonical fields fixes that.
- **Repointed everywhere the dead fields were still wired:** `/profile` GET + `ProfileUpdateSerializer`; both admin student serializers; the admin CSV export (headers "Household Income"/"Household Size", values from the canonical columns + `contact_phone`); the AI sponsor-profile prompt (`siblings_studying` → count-only, no boolean fallback); the scholarship details serializer + allowed-fields. Front-end: `StudentProfile`/`SyncProfileData`/admin types, the admin student list + detail pages, `useProfileCompleteness`, and `applicationToDetailsForm` (count-only).
- **Expand-contract ordering (deploy-first / DROP-after):** this release ships the code with the model fields **removed** (Django ignores the still-present DB columns); the `DROP COLUMN`s (migrations `courses/0050` + `scholarship/0022`) are applied via Supabase MCP **after** the new revision is live on 100% traffic. Pre-drop `SELECT COUNT(*)` safety hold re-confirmed.
- Tests: full backend **1249 pass**; jest 155; `next build` clean.

## [2.13.0] — TD-063: explicit stream subjects (back-end trusts the student's pick) (2026-05-30)

Resolves TD-063 (FE/BE stream-pool duplication drift risk) by making the back-end **trust the student's own stream/aliran selection** instead of re-guessing the stream from its own copy of the pools.

- **Root cause of the debt:** the merit engine receives a *flat* grades dict with no stream label, so it guessed the stream by counting which pool held the most subjects — which required `engine.py` to keep its own copy of `subjects.ts`'s pools. The two copies could drift (the S18 bug class: a dropdown subject missing from the back-end pool silently scored at the 10% elective weight instead of 30% stream weight).
- **Fix:** `prepare_merit_inputs(grades, stream_subjects=None)` now takes the subjects the student explicitly studied in their stream. When present, **Sec2 (30% stream weight) = best 2 of those** — the pools are not consulted at all, so a subject missing from the back-end pool can no longer be mis-scored. When absent (golden-master fixtures, profiles saved before this change), it **falls back to the legacy count-heuristic**, so existing/historical flat-grade data scores identically.
- **Persisted:** new `StudentProfile.stream_subjects` JSON field (migration `courses/0049`, additive, applied migrate-first via Supabase MCP). The front-end sends the student's `aliranSubjects` everywhere merit is computed — live merit on the grades page, eligibility on the dashboard + search, the stateless merit calculator — and persists them on profile sync + login. Returned on `GET /profile/` for cross-device rehydration.
- **Pools are now fallback-only.** The `SCIENCE_POOL`/`ARTS_POOL`/`TECHNICAL_POOL` copies in `engine.py` remain solely to classify old/unlabelled data; for any student with an explicit selection they are bypassed, so the drift risk no longer reaches a labelled student. Linking comment + paired count tests kept for the fallback path.
- **Rollout is safe:** existing logged-in students who haven't re-saved have an empty `stream_subjects` → fallback → **unchanged score**; they pick up the explicit path the next time they save grades.
- **Verification:** golden master **unchanged at 5319** (proves the no-label path is byte-identical); a differential audit (now captured as 6 unit tests in `test_merit_pools.py`) confirmed the explicit path matches the heuristic for every single-stream student and diverges only for genuine cross-stream students the heuristic was mis-classifying — where the explicit score is the correct one. Courses pytest 983 pass, scholarship 215, jest 156, `next build` clean.

## [2.12.1] — S24: Funding tab UX polish (radios, * markers, tips) (2026-05-29)

- **Programme length is now a radio group, not a dropdown — and labels are year-only** (no more "(Matriculation / Foundation)" / "(Diploma)" / "(Degree)" annotations). The same year-count maps to multiple programme levels (1y = matric OR foundation; 3y = diploma OR most degrees; 5y = PISMP OR 5-year degree like medicine/dentistry), so the level annotations were misleading. Added a 5-year option (was capped at 4 — PISMP and medical degrees fell outside the range).
- **Programme length is now compulsory.** `funding_done` rule extended on both sides: `categories non-empty AND programme_months IS NOT NULL`. Marked with `*` via the shared `FieldLabel` component. Without a length the admin can't size the assistance.
- **Categories label now carries `*`** for visual parity with the length question. The "at least one tick" rule already existed in `funding_done`; the marker just surfaces it.
- **"Anything else" textarea polished:** dropped the "(optional)" suffix (convention across the form is no "(optional)" — required fields wear `*`, everything else is implicitly optional). Added placeholder ghost text ("If this assistance doesn't come through, I'll take a part-time job and apply again next year.") + a collapsible "Need ideas?" tips panel with 3 bullets matching the Story tab pattern. Bullets folded in the user-suggested example: "How you would manage if this assistance doesn't come through."
- **i18n parity** 1379 × en/ms/ta (+ `length60` + `notePlaceholder` + `noteTipsTitle` + `noteTip1/2/3` — 7 new keys; `length12/24/36/48` text shortened; Tamil first-draft for the new keys queued).
- **Tests:** backend `+2` (`test_funding_done_true_when_categories_and_months_set` rename + `test_funding_done_false_when_programme_months_null`); existing tests/`_make_complete` helper extended with `programme_months=36`. Scholarship `test_details.py` 39/39 pass. Frontend jest 156/156 pass; `next build` clean.

## [2.12.0] — S23: income proof now required (2026-05-29)

- **Proof of household income is now a required document.** Previously the income-proof card (STR / salary slip / EPF) sat in the Optional section; an applicant could mark Documents as complete without uploading any income evidence. Any one of `{str, salary_slip, epf}` satisfies the gate — STR families are encouraged in the card explainer to ALSO upload a salary slip and/or EPF statement for every working household member, but one upload is enough to pass completeness.
- **Card explainer rewritten for B40 directness:** *"If your family is an STR recipient, please upload a screenshot of your STR portal showing your parent's name and NRIC. We strongly encourage you to also upload the latest salary slip and/or EPF statement for every working member of the household."* The previous "Any one is fine…" wording understated how much admin uses the extra documents to cross-check the household income figure typed at /apply.
- **`documents_done` rule (backend `services.application_completeness` + frontend `documentsComplete`)** extended: `ic + results_slip + parent_ic + (str ∨ salary_slip ∨ epf)`. The IncomeProofCard moved from the Optional section to the Required section on the Documents tab. `requiredNote` copy dropped "two" (now four cards in Required).
- **Tests:** backend `+4` (`test_documents_done_false_when_income_proof_missing` + three positive cases per income-proof type) — scholarship test_details suite 38/38 pass. Frontend jest `+4` (one negative + three positive variants + multi-upload case) — 156/156 pass. `_make_complete` helper extended to include an STR doc so the existing `test_complete_when_all_present` still asserts a 7-part green.
- **No migration.** Choices were already on `ApplicantDocument.DOC_TYPES` since S4; only the completeness rule changed. **No backfill.** Live applications already shortlisted (just Elanjelian on prod) get the new requirement at next page load — they re-open the Documents tab and upload one income proof.

## [2.11.1] — Name-mismatch chip directs to /profile (2026-05-29)

- **Vision OCR name-soft chip on the Documents tab now tells the student where to fix it.** When Vision reads the name on the IC slightly differently from the typed name, the most likely cause is a typo at /apply, not a problem with the IC. New copy: *"Your NRIC matches but the name on your IC reads slightly differently. The name on your IC is the official one — please update your profile to match it exactly."* + a *"Edit your name in your profile"* link below the chip pointing to `/profile`. Applies only to the `name-soft` variant (NRIC mismatch left unchanged; NRIC is locked once admin-verified anyway). i18n parity 1370 × en/ms/ta (+1 new `name-soft-action` key; Tamil first-draft queued). Frontend-only; tests 154/154 pass; web-only deploy.

## [2.10.1] — Stream dropdowns sorted alphabetically (2026-05-29)

- **Stream-subject dropdowns now list options alphabetically by display name** (locale-aware), matching the elective dropdown. Applies to both the SPM grades page (`onboarding/grades`) and the STPM SPM-prerequisite page (`onboarding/stpm-grades`). With the Arts pool now at 38 subjects (S18), a sorted list is much easier to scan. Pre-filled default stream subjects are unaffected — they still read the canonical pool order. Frontend-only; no test or backend change.

## [2.11.0] — S19: minor consent flow hardening + UX iteration round (2026-05-29)

Composite sprint after S18 ship. Six commits, one headline (minor consent v2) plus four
copy/UX iterations the user drove through live, plus a follow-up policy change on
`parent_ic` requirement. All shipped to prod incrementally.

- **Minor consent v2** (`7a9e8cb`). Pre-S19 the minor branch trusted typed values
  unconditionally; this iteration closes the gap. Added: parent NRIC field (masked
  `XXXXXX-XX-XXXX`, stored in new `Consent.guardian_nric` column via migration
  `scholarship/0021`); structured 7-option relationship dropdown (father, mother,
  legal_guardian, grandparent, brother, sister, relative — "older_sibling" split into
  brother+sister; "other_relative" shortened to relative; no "Other" per user); consent
  text body interpolates `{student_name}`, `{student_nric}`, and pronouns derived from
  the student's NRIC last digit (`gender_from_nric` helper); **hard-gate** name + NRIC
  match against `parent_ic` Vision OCR (was a soft anomaly flag in S17 — now blocks
  consent POST with 400 `parent_ic_nric_mismatch` / `parent_ic_name_mismatch`); FE
  pre-checks live and disables the toggle on mismatch; OCR-disclosure paragraph removed
  from consent body (stays in Documents step where OCR actually happens). `CONSENT_VERSION`
  bumped `2026-draft-2` → `2026-draft-3` (0 pre-existing consents on prod, forward-only).
- **Layout iteration** (`abdfab5`). User feedback after seeing S19 in the browser: simpler
  parent-voice body in B40 language (two short paragraphs); moved the subtitle into a
  student-directed blue info-box ("As you are under 18, please ask your parent or guardian
  to read the following section…"); removed the redundant guardianNotice line; moved the
  `needParentIc` warning UP into that slot, conditional on `!hasParentIc` (hide when
  uploaded). DRAFT label removed from both adult and minor branches (still a working
  model, but the DRAFT banner no longer fits).
- **InfoBox + bold consent body** (`cf9b1d4`). New `components/InfoBox.tsx` locks the
  box-colour convention across `/application`: green=success, blue=info, amber=warning,
  red=block; fixed `rounded-lg p-3 text-sm` + `text-{color}-800` body. Applied to consent
  warnings + funding intro + save-error block. Adult subtitle dropped (consent body is
  self-explanatory). Consent body renders `**bold**` markers (markdown style) as
  `<strong>` — used for student name, NRIC, and the programme name. Tiny `renderRich`
  helper, 5 lines.
- **Box-ify all tab intros** (`d6c0505`). Every `/application` step now opens with one
  instruction-led blue InfoBox where applicable (Story langNote, Funding intro merged
  from two stacked paragraphs, Documents step4Body rewritten as instruction). step6Body
  intro on Consent tab removed (redundant). minorInfoNotice trimmed (dropped "As you are
  under 18 years of age," prefix — the consent body itself states the under-18 fact).
- **parent_ic universal compulsory** (`35d61b3`). Per user direction: even adult applicants
  need to upload parent's IC, because the admin cross-checks supporting docs like STR or
  EPF (typically issued in a parent's name) against the parent's IC. `documents_done` now
  requires `{ic, results_slip, parent_ic}` universally; `guardian_docs_done` simplified
  (parent_ic moved out; minor branch only checks the conditional `guardianship_letter`).
  Help text rewritten universal × en/ms/ta. Forward-looking, not retroactive — 12 currently
  submitted apps are all pre-decision-reveal so they see the "received" status card not
  the Documents tab; only Elanjelian (test) is at /application today.

**Tests** — backend **1236 / 1236 pass** (+12 from 1224 at S17 close: 4 TestGuardianDocsDone
restructure, 4 new TestConsentApi for NRIC-mismatch/name-mismatch/missing-nric/hyphen-strip
+ 3 minor relationship test updates + 1 new TestGuardianDocsDone case for parent_ic moved
out). Frontend **jest 154 / 154** (documentsComplete suite rewritten in-place to drop the
isMinor flag tests).
**Migration applied via Supabase MCP** (TD-058 workaround): `scholarship/0021` — additive
`ADD COLUMN guardian_nric` + choices-only `AlterField` for new GUARDIAN_RELATIONSHIPS list.
**i18n** parity 1369 × en/ms/ta. Tamil first-draft mirrors queued (queue now 10 batches).
**Deploys**: 6 (one per commit). All small; total under-budget.

## [2.10.0] — S18: SPM stream subject coverage — full Arts & Technical lists (2026-05-29)

A user reported that the SPM apply-form stream dropdowns offered far fewer subjects than the official SPM list. Root cause: the Arts pool listed only 9 subjects and Technical only 8, while `SUBJECT_NAMES` already had labels for ~26 of the missing Arts subjects — they were simply never added to the selectable pool. Worse, the backend merit engine kept its **own** hardcoded copy of these pools, so any subject in the dropdown but absent from the backend pool would silently score on the 10% elective weight instead of the 30% stream weight. This sprint brings both into line with the official source (Islamic-stream subjects excluded per the product's mainstream scope) and keeps frontend and backend pools in lockstep.

### Changed
- **Subject model (`subjects.ts`): single `category` → `streams` list.** A subject can now belong to more than one stream pool (e.g. the sciences appear under both Science and Technical, matching the official SPM elective grouping) while remaining electable. Derived exports (`SPM_CORE_SUBJECTS`, `SPM_STREAM_POOLS`, `SPM_ALL_ELECTIVE_SUBJECTS`, `SPM_PREREQ_STREAM_POOLS`) keep their names and shapes — **no consuming page changed.**
- **Arts stream pool: 9 → 38 subjects.** Adds the full non-Islamic official list — languages (Arabic, Iban, Kadazandusun, Punjabi, Semai), literatures (English, Chinese, Tamil, Communicative Malay), performing & visual arts (Dance, Choreography, Acting, Scenography, Music subjects, 2D/3D Fine Art, Graphic/Industrial/Craft Design, Creative Multimedia, Script Writing, Performing Arts Production, Art History & Management), and Bible Knowledge.
- **Technical stream pool: 8 → 16 subjects.** Now matches the official Science-Technology-Vocational grouping: the four engineering studies, Engineering Drawing, Technical Graphics, Computer Science, Inventions, plus Asas Kelestarian, Pertanian, Sains Rumah Tangga, Sains Sukan, Sains Tambahan, and the sciences (Bio/Fizik/Kimia/Add Maths). `Multimedia` moved out of Technical to elective-only (it maps to the Arts group in the source).
- **Backend merit pools (`engine.py`) expanded to mirror the frontend** and lifted to module-level constants (`SCIENCE_POOL`, `ARTS_POOL`, `TECHNICAL_POOL`) so the 30% stream weight (Sec2) recognises every selectable stream subject. A code comment ties the two definitions together.

### Added
- Two new subject keys with labels: `bahasa_punjabi` (Punjabi Language) and `bible_knowledge` (Bible Knowledge).
- `subjects.test.ts` (12 tests): pool composition counts, Islamic-exclusion, sciences-in-both-pools, the "selected-as-stream-subject disappears-from-electives" dedup invariant, and label coverage for every selectable subject.
- `test_merit_pools.py` (7 tests): pool membership mirrors the frontend, and arts/technical stream subjects land in Sec2 (30%) not Sec3 (10%).

### Notes
- **No migration, no data backfill** — subject keys are not persisted as enums; grades are stored by key. Existing saved grades are unaffected.
- Golden master unchanged (SPM 5319): the new keys aren't held by the baseline students, and the science/technical pool overlap resolves the stream tie to Science by ordering, so pure-science merit is identical. Verified, not assumed.

## [2.9.0] — S17: minor consent flow — re-voiced text, parent IC + guardianship letter, structured relationship (2026-05-29)

The pre-S17 minor branch was a half-measure: it captured guardian name + free-text relationship + flipped the toggle label, but the consent body still read "I consent…" (student voice) and we trusted the typed guardian name with no identity verification. Lawyer review needs a defensible end-to-end flow. This sprint delivers that working model — single push, one migration, ready for legal sign-off.

- **Re-voiced consent text for minors.** New `scholarship.consent.textMinor` i18n block — full parent-voice paragraph: *"I am the parent or legal guardian of the named applicant, who is under 18 years of age. On their behalf, I consent to… I confirm that I have legal authority to give this consent for the applicant."* Replaces the prior toggle-label-only minor cue.
- **Structured `guardian_relationship` dropdown** (6 codes, no free-text): `father`, `mother`, `legal_guardian` (court-appointed), `grandparent`, `older_sibling`, `other_relative`. "Other" intentionally excluded per user direction — if no fit, the right path is a court-appointed `legal_guardian` with a letter. Backend rejects any value not in the structured list (`ConsentCreateSerializer.validate_guardian_relationship` → 400).
- **Parent/guardian IC upload required for minors.** New doc type `parent_ic` on `ApplicantDocument.DOC_TYPES`. Auto-Vision-OCR'd on upload (reuses the S13 pipeline). Compulsory in the Documents tab when applicant is a minor; backend blocks consent POST with 400 `parent_ic_required` if missing.
- **Guardianship letter required for non-parent guardians.** New doc type `guardianship_letter`. Pragmatic acceptance (per user direction): a court-issued guardianship order OR a parent's written authorisation letter — both count. Backend blocks consent POST with 400 `guardianship_letter_required` when `needs_guardianship_letter(relationship)` is true and the doc isn't uploaded. Shown in the Optional section of the Documents tab when minor (the relationship is picked only at consent time).
- **Completeness rule now 7-part.** `application_completeness` gains `guardian_docs_done`: trivially true for adults; for minors requires `parent_ic` uploaded, AND if the latest active consent's relationship is non-parent also `guardianship_letter`. `complete = quiz + story + funding + docs + consent + address + guardian_docs`.
- **2 new anomaly rules** (S16 Phase A engine):
  - `parent_ic_name_mismatch` — Vision-OCR name on `parent_ic` differs from the typed guardian name on the consent (token-set via the existing `name_match`).
  - `parent_ic_underage` — Vision-OCR NRIC on `parent_ic` indicates age < 18. The "guardian" is themselves a minor — hard signal for the admin.
- **CONSENT_VERSION bumped** `2026-draft-1` → `2026-draft-2`. Existing active `2026-draft-1` consents become outdated; student/guardian re-attests with the new flow on next visit. Honest re-consent for a substantive identity change. **Prod check at sprint close: zero existing consent rows** (the live programme is still dormant), so the bump is purely forward-looking — no real applicants need to re-attest.
- **Migration `scholarship/0020`** — choices-only (no DDL); applied as a direct `django_migrations` insert via Supabase MCP per the TD-058 workaround. `Consent.guardian_relationship` keeps its `CharField(100)` storage; choices enforced at the serializer + admin level. Pre-S17 free-text consent rows (none on prod) would stay readable.
- **Admin verify-&-accept card** gains a "Parent/guardian IC (Vision OCR)" row when present — surfaces extracted NRIC + name + address + Re-run link. No automated verdict on this card; the new anomaly rules surface the verdicts in the Pre-interview flags card above.
- **i18n** parity 1356 × en/ms/ta (+20 keys: consent textMinor + 6 relationship labels + relationshipPlaceholder + needParentIc/Letter + 2 doc-type labels + 2 doc-help + 1 admin parentIcTitle + 2 anomaly pairs). Tamil first-draft mirrors queued — **batch is now 9 deep**.
- **Tests** — backend **1224 / 1224 pass** (+13 new: 4 TestGuardianDocsDone; 4 TestConsentApi for parent_ic_required + guardianship_letter_required + non-parent-with-letter OK + invalid-relationship rejected; 3 minor-relationship test updates; 4 anomaly tests for the two new rules). Frontend **jest 112 / 112** (+2: documentsComplete minor signature; DOC_TYPES length bump 11 → 13).
- **1 deploy**; under budget.

## [2.8.0] — S16 Phase A: deterministic anomaly engine for pre-interview flags (2026-05-29)

First slice of the post-shortlist vision (`docs/scholarship/post-shortlist-vision.md`). Single focused sprint.

- **Engine** (`apps/scholarship/anomaly_engine.py`). Pure module: 10 `_detect_*` functions registered in a `_DETECTORS` tuple, plus one `detect_anomalies(application) → list[dict]` aggregator returning JSON-ready `{code, params}` dicts. Each rule null-safe over missing profile / docs / funding_need. No LLM calls, no model writes — all deterministic. The 10 rules (per the user-calibrated taxonomy):
  - `vision_nric_mismatch`, `vision_name_mismatch` — built on S13's OCR verdicts.
  - `address_state_mismatch` — Vision-OCR'd state ≠ `profile.preferred_state`, with W.P. prefix normalisation.
  - `jkm_high_income` — `receives_jkm=true` AND `household_income > RM3000`; question reframed to acknowledge disability/caregiving (JKM is family-applied, not student-applied — the user corrected my first framing).
  - `household_size_one`, `first_in_family_with_siblings_studying` (question preempts the school-vs-university distinction).
  - `funding_other_without_note`, `declaration_name_mismatch` (token-set via `vision.name_match`).
  - `str_claimed_no_doc` — `receives_str=true` AND no `doc_type='str'` upload. New rule per user suggestion.
  - `device_in_funding` — laptop won't fit in the RM 3,000 cap alone. New rule per user suggestion.
- **Three suggestions deferred to Phase B** (need Gemini multimodal): utility-bill amount vs household size; SOI content-derived questions; "wrong" supporting doc detection. Honest scope.
- **Admin UI** (`admin/scholarship/[id]/page.tsx`). New "Pre-interview flags" card above verify-&-accept; amber-tinted list, one entry per flag, each renders the observed fact + the suggested question via i18n with the engine's `params` interpolated. Empty-state: *"No automated flags. Use your judgement during the interview."* — the engine is honest about silence. Flag count chip in the card header.
- **Backend wiring**: `AdminApplicationDetailSerializer` adds `anomalies = SerializerMethodField`, called per GET (no cache; the function is cheap and pure). Read-only.
- **Frontend type**: new `AdminAnomaly { code, params }` interface in `admin-api.ts`; `AdminScholarshipDetail.anomalies: AdminAnomaly[]`.
- **i18n**: 26 new keys per locale (5 UI scaffolding + 10 facts + 10 questions + 1 askLabel). Parity 1336 × en/ms/ta. Tamil first-draft mirrors queued for batch refine — **queue is now 8 batches / ~85+ strings**.
- **Tests**: 23 new in `test_anomaly_engine.py` (one positive + one negative per rule + integration shape tests for empty input, dict shape, ordering stability). 193/193 scholarship pytest. Next build EXIT=0.
- **Live preview for app #3** (Elanjelian, shortlisted): expected 2 flags on first load — `address_state_mismatch` (IC: KEDAH vs profile: Putrajaya) + `str_claimed_no_doc` (`receives_str=true`, no STR doc uploaded). First real-data validation of the engine.
- **No migration**. No backfill needed.

## [2.7.0] — S15: Story tab polish + Vision MyKad address + single-instance docs (2026-05-29)

Composite sprint after S14 ship. Four discrete pieces, all deployed; see retrospective for the journey.

- **Story tab polish on /application** (`53afbad`). Live-testing feedback converted to four UX/UX-data items:
  - **Tick boxes → slide toggles** on `firstInFamily` + the Consent agreement, matching /apply's `Toggle` (STR/JKM). `FieldLabel` extracted from /apply to `src/components/FieldLabel.tsx` so /application reuses the same `*` convention.
  - **Siblings: boolean → numeric.** "One or more of my siblings are also studying" replaced by "How many of your siblings are also studying?" — useful proxy for family education burden. Backend: migration `scholarship/0019` adds `siblings_studying_count: PositiveSmallIntegerField(null=True, blank=True)`; legacy `siblings_studying` boolean kept for back-compat (joins TD-061 contract). `profile_engine._build_prompt` prefers the count over the boolean.
  - **Placeholder ghost text + collapsible "Need ideas?" tips** on all 6 open textareas (parentsOccupation, familyContext, aspirations, plans, dailyLife, fears). Native `<details>` panels with 3 short bullets each. Tone deliberately first-person + slightly imperfect — student should think *"I can write better than that"*.
  - **Asterisk convention.** Required Story-tab fields (aspirations, plans, street, postal, city) gain `*` via `FieldLabel required`; optional fields drop the "(Optional)" suffix. Matches /apply.
- **Vision OCR for MyKad address surface** (`69cb1d0`, `0fb08a3`, `4baae5f`). Building on S13's MyKad name+NRIC OCR: now also extract the home address from the IC photo. Migration `scholarship/0018` adds `vision_address: CharField(max_length=500)`; new `_extract_address` helper in `vision.py` uses a postcode-anchor heuristic to walk up the OCR text, drops the NRIC + name lines, strips "Alamat" labels, and now also picks up the state line below the postcode + the taman/kampung line above. Soft signal only — no matcher, no verdict; admin verify-&-accept card surfaces the extracted address alongside the student-entered `profile.address` for eyeball cross-check at interview time. The heuristic-tuning journey took 3 deploys against the real MyKad — first miss (state below postcode), second miss (TAMAN SEMANGAT dropped as "looks like a name"), final pass captures all 4 lines.
- **Single-instance doc-type replace on re-upload** (`2ee7d5d`). Previously, a student could upload multiple IC photos and the system kept all of them — leaving the admin to guess which was authoritative. Now: `DocumentListCreateView.POST` sweeps any existing rows of the same single-instance doc type (DB + Supabase Storage blob) before creating the new one. The three income-proof types (STR / salary_slip / EPF) intentionally stay multi-instance for monthly slip stacking. Explicit `DELETE` also sweeps the Storage blob (was leaking blobs on every Remove click). UI label flips from "Add more" → "Replace" for single-instance types. TD-062 logged for the orphan Storage blobs that pre-fix Remove clicks left behind (sweep when convenient).
- **Post-shortlist vision doc** (`87404e1`). Direction-setting `docs/scholarship/post-shortlist-vision.md` — four user types (student done; admin needs role categories; sponsor + mentor to do), funnel through interview/sponsorship/in-programme, three-engine gap model (deterministic rules + Vision OCR + Gemini), two-stage profile (draft → interview findings → final), standardisation north star. Recommended Phase A = deterministic anomaly engine as the first slice.

**Tests** — backend 1188 (+19: 5 vision address extraction, 3 docs single-instance, 6 details siblings count, 2 profile_engine count fallback, +3 from related); frontend jest 110 (+4: siblings count round-trip + prefill behaviour).
**i18n** parity 1310 × en/ms/ta (+34 keys; Tamil first-draft mirrors queued for batch refine — pending queue is now 7 batches).
**Migrations applied via Supabase MCP** (migrate-first per TD-058 workaround): `scholarship/0018_applicantdocument_vision_address`, `scholarship/0019_scholarshipapplication_siblings_studying_count`. Both additive, 0 rows touched.
**Deploys**: 5 over the sprint (3 Vision address tuning + 1 single-instance docs + 1 S15 polish). The 3 Vision deploys were a heuristic-tuning loop against real-data feedback — captured as a lesson (test fixtures alone can't validate OCR heuristics; user-driven verification is essential).

## [2.6.0] — S14: /profile schema consolidation + required address on /application (2026-05-29)

Backend + frontend (no migration; data backfilled via Supabase MCP under the expand-contract pattern). Closes
four /profile gaps surfaced during live user-testing: redundant income/siblings/phone fields that didn't sync with
/apply, plus the missing physical address capture for shortlisted applicants.

- **/profile family card.** Replaced the `family_income` range dropdown with an open RM input bound to
  `household_income` (same column /apply already writes) and re-labelled "Number of Siblings" → "Household size"
  on `household_size` (also shared with /apply). One source of truth for income + household composition.
- **/profile Contact & Location.** Dropped the dead `phone` input (the visible Contact Phone in Contact Details
  is the synced one). No behaviour change for users; the deprecated input is just gone.
- **Contact Email auto-default.** `ProfileView.get` now falls back to the auth-user email when
  `profile.contact_email` is blank, and reports it as verified (Google/Supabase already verified that mailbox).
  Read-time fallback only — the DB row stays empty; a user-set contact email still wins and uses its real
  verification flag.
- **/application Story tab — new "Where you live" card.** Street + postcode + city inputs under the Family card.
  State stays read-only ("from your application" — sourced from `profile.preferred_state`). One Save button
  writes everything; `save_application_details` persists the address sub-fields to the profile (alongside the
  narrative on the application). Pre-fills from `profile.address`/`postal_code`/`city` on next read.
- **Completeness rule now 6-part.** `application_completeness` gains `address_done` (street + postcode + city
  all non-blank); `complete = quiz + story + funding + docs + consent + address`. Story tab tick requires both
  the narrative AND the address. Existing shortlisted applicants must add their address to reach "complete".
- **Conflict policy doc'd** on `buildApplicationPayload`: last-write-wins on shared profile fields.
- **TD-061 logged** (drop the three dead columns next session under expand-contract).
- **Backfills run on prod via Supabase MCP** (before push): `household_income` populated from `family_income`
  range midpoints (41 rows), `household_size = siblings + 2` (42 rows), phone-promotion no-op (all 6 dead-phone
  rows already had `contact_phone`), contact_email auto-default is read-time so no DB write needed.
- **i18n** parity 1276 keys × en/ms/ta — Tamil first-drafts for the new keys (`profile.householdIncome*`,
  `householdSize*`, `scholarship.nextSteps.story.cardAddress.*`) **pending user refine**.
- **Tests** — backend +3 (address_done, address PATCH writes to profile, contact_email auto-default ×2);
  frontend +4 (buildDetailsPayload address, applicationToDetailsForm address pre-fill + defaults).
  151/151 scholarship pytest + 106/106 jest, build green (EXIT=0).

## [2.5.0] — S13: Vision OCR for MyKad — soft signal at upload + verify-&-accept (2026-05-28)

Backend + frontend + admin (additive migration `scholarship 0016`, migrate-first via Supabase MCP). When a student
uploads their **IC**, Google Cloud Vision is auto-triggered server-side; the student sees an instant chip below the
file row ("looks good" / "name slightly different" / "NRIC doesn't match" / "couldn't read"), and the admin sees the
same signal as a row inside the verify-&-accept card. **Vision is a soft hint only — never a hard block.** The admin
verify-&-accept (S11a) remains the real identity gate. Resolves the post-launch fast-follow flagged at S12 split.
- **Backend (`apps/scholarship/vision.py` + `views`):** new `vision.py` with pure matchers (`nric_match`,
  `name_match` returns match/partial/mismatch) + a graceful-degradation entry point (`run_vision_for_document`)
  that fetches the image from Supabase Storage, calls Cloud Vision `document_text_detection`, extracts NRIC + name,
  and writes 4 new `ApplicantDocument` fields (`vision_nric`, `vision_name`, `vision_run_at`, `vision_error`). The
  IC `record-document` POST auto-triggers it; a new admin endpoint `POST .../documents/<id>/re-run-vision/` lets the
  coordinator retry. **All Vision calls are mocked in tests** (8 pure-matcher tests + 3 IC auto-trigger tests + 4
  admin re-run tests); **no paid calls** during build. The serializer also exposes server-computed
  `vision_nric_verdict` / `vision_name_verdict` so the frontend doesn't reimplement the matchers (S5c-lesson).
- **Migration `scholarship 0016`** — additive 4 columns; applied migrate-first via Supabase MCP (per the TD-058
  workaround) before the push.
- **Frontend (student):** the IC card helper now reads *"…we'll check it automatically to help you spot typos —
  your photo isn't kept at Google."* A `VisionChip` renders below the IC file row in one of four variants (green
  ✓ match · amber ⚠ name-soft · amber ⚠ NRIC-bad · neutral ⓘ unreadable), driven by the server verdicts.
- **Frontend (admin):** a new "Vision OCR (soft signal)" row inside the verify-&-accept card — two coloured pills,
  the raw extracted NRIC + name, a `Re-run Vision` link, and the declaration name shown for cross-check. Stitch was
  skipped on the admin side (S5b precedent — internal admin UI doesn't go through Stitch).
- **Consent text bump** — appended one sentence honestly disclosing automated OCR processing on uploaded documents
  (still PDPA-aligned: data already collected; transient processing). Inline privacy hint in the IC card too.
- **API key path deferred to post-deploy.** The Cloud Vision API isn't enabled yet — the new code degrades to
  `vision_error="AI service not configured"` and the student sees the neutral "couldn't read" chip. **One real
  end-to-end check is admin-triggered (billable) and waits for the user's explicit greenlight.**
- Gates: backend **1162 pytest** (+21), `next build` **EXIT=0** (explicit exit-code check, TD-059 lesson), i18n
  parity **1257** ×3. Tamil first-draft pending user refine (consistent with S4/S5a).

## [2.4.7] — TD-059 cleanup: drop dead `FundingNeed` amount columns (2026-05-28)

Backend + frontend cleanup, **destructive migration** (`scholarship 0015`). The S3 funding reframe (v2.4.2) left
9 line-item amount columns on `FundingNeed` orphaned (no readers, no writers, no UI). This drops them.
- **Backend:** `FundingNeed` loses `tuition_gap`, `laptop`, `hostel`, `transport`, `books`, `monthly_allowance`,
  `allowance_months`, `other`, `other_desc` and the `total` property (and the `__str__` line that used it).
  `FundingNeedSerializer.fields` shrinks to `categories`/`funding_note`/`programme_months` only. Stale model + payload
  tests dropped or rewritten to use `categories`.
- **Frontend:** `FundingNeed` interface, `DetailsFormState` (8 form fields removed) and the `fundingTotal` helper +
  its jest tests; payload/form mappings in `applicationToDetailsForm`/`buildDetailsPayload` shrunk to the 3 kept
  fields. `/admin/scholarship/[id]` no longer shows `RM${funding_need.total}` — shows the **ticked categories** list.
- **Migration ordering — expand-contract (deploy-first, drop-after).** For a destructive change, dropping columns
  before the deploy would 500 the currently-live `FundingNeedSerializer`. So: code shipped first (Django ignores
  extra DB columns), then `DROP COLUMN ×9` applied on prod via Supabase MCP + `django_migrations` row recorded
  (per the TD-058 workaround). 0 prod rows in `funding_needs` confirmed before the drop.
- Build clean; backend 1141 pytest; jest 123; i18n unchanged (parity 1246). **Resolves TD-059.**

## [2.4.6] — AI sponsor-profile generator rebuilt + Tamil/BM-aware (Step-4 redesign, S5c) (2026-05-28)

Backend + admin frontend, **no migration**. **Resolves TD-060.** `profile_engine.py` was building its Gemini prompt from
fields the profile-canonical refactor removed (`qualification`/`spm_a_count`/`household_income`/`stpm_pngk`) plus
legacy/dead ones — it would have 500'd if an admin clicked "Generate". Rebuilt against the current data model **and**
made language-aware.
- **`_build_prompt` rewritten** to read profile-canonical academic/financial data (`profile.exam_type`,
  `count_spm_a_grades(profile.grades)`, `profile.stpm_cgpa`, `household_income/size`, `receives_str/jkm`), the "Your
  story" narrative (`aspirations`, `plans`, `first_in_family`, `parents_occupation`, `siblings_studying`,
  `family_context`, `daily_life`), the pathway (`field_of_study` + `pathways_considered`), and the simplified funding
  (`categories` + `funding_note` + `programme_months` — **not** the dead `total`/TD-059) + referees.
- **Language-aware:** the prompt tells the model the student's own words may be in **Malay, English, or Tamil**
  (understand all three) and to write the profile in a **target language**. `generate_sponsor_profile(application,
  language=None)` defaults output to the applicant's locale (en→English, ms→Malay); the admin can override via a small
  **EN / BM** selector on `/admin/scholarship/[id]`. (Tamil *output* deferred to Phase 2 — sponsors read EN/BM — but
  it's now a one-line prompt-parameter change.)
- **Tests:** new `test_profile_engine.py` (8) exercises the pure prompt builder — current fields present, multilingual
  + target-language instructions present, no dead `total`, language resolution, and the **TD-060 regression** (no
  `AttributeError` on a current-model application). Gemini stays mocked; **no live/paid calls** were made.
- Build clean; backend 1143 pytest; i18n parity 1246. **Note:** a true end-to-end generation check is an
  admin-triggered live (billable) Gemini call — run it when ready; the programme is still dormant.

## [2.4.5] — Admin records the referee at verify-&-accept (Step-4 redesign, S5b) (2026-05-28)

Backend + admin frontend, **no migration** (the `Referee` model already exists). The Step-4 redesign moved the referee
out of the student flow; this lets the **coordinator record it at the verify-&-accept stage**, which previously had no UI.
- **Backend:** new PartnerAdmin-scoped endpoints — `GET/POST /api/v1/admin/scholarship/applications/<pk>/referees/`
  (list/add) and `DELETE …/referees/<ref_id>/` (remove, scoped to the application). Reuses `RefereeSerializer`. Tests
  for add/list/delete, name-required, wrong-application 404, and admin-only access.
- **Admin frontend:** the Referee section on `/admin/scholarship/[id]` is now interactive — lists referees with a
  remove action and an add form (name, role, relationship, phone, email). New `addReferee`/`deleteReferee` admin-API
  helpers. i18n ×3 (parity 1245).
- Build clean; backend 1135 pytest. **Finding logged as TD-060:** the AI sponsor-profile generator (`profile_engine.py`)
  references fields the profile-canonical refactor removed (`qualification`/`spm_a_count`/`household_income`/`stpm_pngk`)
  plus legacy/dead ones — it would error if invoked. Its rebuild + Tamil/BM-awareness is **S5c** (next).

## [2.4.4] — Completeness finalise + "What happens next" (Step-4 redesign, S5a) (2026-05-28)

Backend + frontend, **no migration**. Closes the completeness loop and gives the student a reassuring finish.
- **Backend:** `application_completeness` gains **`consent_done`** (an active `Consent` row exists) and **`complete`
  now = quiz + story + funding + compulsory-docs + consent** (the full 5-part rollup; supersedes S4's interim
  "complete excludes docs/consent"). The read serializer now exposes **`notify_email`** (read-only — the address
  decision/comms emails are actually sent to). Tests updated to the new contract + `consent_done` cases.
- **Frontend:** `ScholarshipNextSteps` now wires the **real Documents + Consent step ticks** (S4 added
  `documents_done` to the backend but the UI still hardcoded them to false). Once all five steps are done, the intro
  banner switches to a green **"You're all set!"** state and a new **"What happens next"** panel appears — a 3-step
  plain-language timeline (we review → we may call you in your preferred language → decision by email) plus a note
  stating the exact email updates go to. i18n ×3 (parity 1235; Tamil copy first-draft pending user refine).
- Progress bar, "Step X of 5", per-step ticks and the desktop 2-column rail were already delivered in S1 — this
  sprint only wired the remaining signals and added the finish panel. Build clean; backend 1128 pytest.
- **Deferred to S5b:** admin referee-at-verify-&-accept + Tamil-aware AI sponsor-profile. **TD-059** (drop dead
  `FundingNeed` amount columns) still queued.

## [2.4.3] — Documents — compulsory vs optional, with explainers (Step-4 redesign, S4) (2026-05-28)

Backend + frontend (migrate-first: `scholarship 0014`, choices-only — no DDL, row recorded on prod before deploy).
Reworks the Documents tab so the **two compulsory documents are clearly separated from the optional ones**, each with
a one-line "what to upload / why" explainer, so B40 students aren't discouraged by an onerous-looking list.
- **Required** (amber pill): Identity card (IC) + SPM/STPM results slip — *"We need these two to process your application."*
- **Optional** (muted pill): a single **"Proof of household income"** card accepting **any one of** STR letter /
  salary slip / EPF statement (multi-file — several earners welcome); plus latest water bill, latest electricity bill
  (kept as a prosperity proxy), statement of intent, offer letter, photo. `reference_letter` dropped from the student
  UI (referee moved to the admin verify-&-accept stage; kept in model choices for back-compat).
- Backend: 4 new `ApplicantDocument` doc types (`salary_slip`, `water_bill`, `electricity_bill`, `offer_letter`) —
  additive choices-only migration `0014`. `application_completeness` gains **`documents_done`** = IC **and** results
  slip both present. `complete` is **deliberately unchanged** (still quiz + story + funding) — the documents/consent
  gate lands in S5's completeness finalise. Serializers derive their choice list from the model, so the new types
  validate automatically.
- Frontend: `ScholarshipDocuments` reworked into Required/Optional sections + a combined income-proof card (STR /
  salary slip / EPF selector, each file stored under its own type); `scholarship.ts` doc-type groups +
  `documentsComplete()` helper (+jest); i18n ×3 (parity 1227) — Tamil copy is a first draft pending the user's review.
- Build clean; backend 112 pytest; UI matches the Stitch-approved prototype.

## [2.4.2] — "How you'd use the support" — reframed funding (Step-4 redesign, S3) (2026-05-27)

Backend + frontend (migrate-first: `scholarship 0013`). Reframes the funding tab away from itemised RM amounts.
Since assistance is **capped at RM3,000 (a contribution)**, asking a total or "how you'd cover the balance" only
manufactured a discouraging gap — so both are gone. The tab now: states **"Our assistance is up to RM3,000 — the
actual amount may be lower…"**; asks **programme length**; offers a **tick-only** checklist of what the support would
help with (living, transport, accommodation, books, device, tuition *with "often covered" helper*, something-else);
and an **optional open box** ("how you're planning to fund your studies, or how you'd manage if this doesn't come
through"). No totals, no per-category amounts.
- Backend: `FundingNeed` gains `categories` (JSON), `funding_note` (text), `programme_months` (int) — additive
  migration `0013`, migrate-first (0 existing rows); serializer + details-PATCH + tests. **Funding-complete** now =
  at least one category ticked (was total > 0).
- Frontend: funding tab rewritten (tick categories + length + open box); `DetailsFormState`/payload mapping; i18n ×3
  (parity 1209). Legacy amount fields kept as dead columns (unused).
- Build clean; backend 106 / jest 93; UI screenshot-verified.

## [2.4.1] — "Your story" guided section (Step-4 redesign, S2) (2026-05-27)

Backend + frontend (migrate-first: `scholarship 0012`, applied to prod before deploy). Replaces the "story" tab's
4 generic textareas with a **guided two-card section** — *About your family* + *About you* — that together form the
basis of the student's statement of intent. Trimmed to high-signal, mostly-optional prompts (per the signal-vs-burden
review): family = first-in-family tick, parents'/guardians' occupation, "siblings also studying" (optional), and an
optional family-situation box; you = aspirations + plan (the keepers) + optional daily-life/responsibilities +
optional "what worries you / what support would help". A visible note invites answers in **BM / English / Tamil**,
and points to the Statement-of-Intent upload for "more to say". No profile data is re-asked (sibling count, income,
etc. stay on the canonical profile).
- Backend: 5 additive narrative fields on `ScholarshipApplication` (`first_in_family`, `parents_occupation`,
  `siblings_studying`, `family_context`, `daily_life`; migration `0012`); details-PATCH + read serializers + tests.
  **Story-complete** now = `aspirations` + `plans` filled (was aspirations + justification); everything else optional.
- Frontend: the guided form in the Story tab; `DetailsFormState` + payload mapping; i18n ×3 (parity 1190).
- Build clean; backend 101 / jest 88; UI screenshot-verified (mobile + desktop). No total/photo/funding change here
  (those are S3/S4).

## [2.4.0] — Application follow-up → 5-tab shell (Step-4 redesign, S1) (2026-05-27)

Frontend-only (web deploy). First sprint of the `/scholarship/application` (post-shortlist "complete your profile")
redesign — see `docs/scholarship/application-redesign-plan.md`. The shortlisted view changes from one long scroll to
a **5-tab sectioned shell** mirroring `/apply`: desktop left step-rail + active section card, mobile bottom tab bar,
a progress bar + "Step N of 5" indicator. Tabs: **Quiz · Your story · Funding · Documents · Consent** — the Referee
step is **dropped from the student flow** (it moves to the coordinator's verify-&-accept stage in a later sprint).
Section *content* is ported in **unchanged** this sprint (the single details form is split across the Story + Funding
tabs but still PATCHes the same payload via one shared form state — a Save button on each tab persists everything);
Your story / Funding / Documents get their actual rework in S2–S4. New pure helpers `NEXT_STEP_ORDER` +
`defaultNextTab` (opens on the first incomplete step) with 9 unit tests. Build clean; jest 86; i18n parity 1177.
No backend/model change.

## [2.3.1] — Shortlist email links straight to "complete your profile" (2026-05-27)

Backend-only (api deploy). Live testing showed the shortlist **invitation email** said *"we'll be in touch shortly
with what to do next"* with **no link** — leaving the student stuck at Step 4 with nowhere to go. The email now
includes a direct **call-to-action link** to `{FRONTEND_URL}/scholarship/application` (the complete-your-profile
page), with the documents note (IC, results slip, proof of household income) matching the "How it works" Step 4, in
all three locales. The link is built in `emails._send` from `settings.FRONTEND_URL` (so the ack/decline bodies are
unaffected). Separately, `FRONTEND_URL` now defaults to the **branded `https://halatuju.xyz`** (was the raw Cloud Run
URL) and the live Cloud Run env var was updated to match — so both the shortlist link **and** the existing
verify-email link are now branded. +1 test (shortlist body contains the link). The +48h decline email is unchanged
(no link by design — it's a warm "not this round").

## [2.3.0] — Truthfulness declaration + typed-name signature before submit (2026-05-27)

Backend + frontend (migrate-first: scholarship `0011`, applied to prod before deploy). Adds a final
attestation step to the B40 apply form, on the "Support" tab just above Submit:
- **Declaration** (plain language, no legalese): "I declare that everything I've shared in this application
  is true and complete… I understand the team may ask me for documents to confirm it, and that giving false or
  misleading information can lead to my application being rejected — or any assistance being withdrawn later."
- **Typed-name signature** (required): the student types their full name (as in their IC) to sign. Its value is
  the deliberate act of assent + an audit record — **not** identity verification, since we only hold the name they
  typed in About Me to compare against, never the official JPN record. So the match is a **soft nudge**: if the
  signature doesn't loosely match (case/space-insensitive) the About Me name, we show a gentle warning but never
  block submission.
- **Audit trail:** new `declaration_name` (the signed name) + `declared_at` (server timestamp, stamped at submit)
  on `ScholarshipApplication`. Accepted by the create serializer, exposed by the read serializer. `declared_at` is
  only set when a signature is present (no signature → null).

Backend: model + migration `0011` (additive) + `_APP_FIELDS` + `create_application` stamp; 97 scholarship tests
(2 new). Frontend: `declarationName` in the form state/payload, required in `applyFormError`, soft
`declarationNameMismatch` helper; declaration block on the Support tab (3 locales); 79 lib tests (4 new); i18n
parity 1171. Build clean; declaration block + soft nudge verified locally (Playwright).

## [2.2.7] — Apply-flow polish: NRIC prefill, clearer "no results" prompt, real ending page (2026-05-27)

Frontend-only (one `halatuju-web` deploy). Three issues from live new-user testing:
- **NRIC now pre-fills the apply form.** The NRIC the student gives at the sign-up gate was saved to the
  profile but showed up blank on the apply form. Root cause: the form's profile-prefill locked itself on the
  *first* profile snapshot, which for a brand-new user has no NRIC yet (it's claimed at the gate moments later).
  The prefill now waits until the profile actually carries its NRIC before seeding, so the field arrives
  pre-filled (and still editable, since it's unverified). Verified in prod DB that the NRIC was being persisted —
  this was purely a frontend timing bug.
- **Clearer prompt when results are missing.** A student who reaches "Your Plans" without exam results saw a
  vague "add them in the previous step". Rewritten to name the step explicitly and urge action: "We can't show
  your pathways yet — we don't have your exam results. Please go to the 'Your SPM / STPM Results' step and add
  your results first…" (`plan.noPathways`, ×3 locales, step named per-language).
- **The post-submission page is no longer a dead end.** `/scholarship/application` rendered a bare card with no
  site chrome. It now uses the standard `AppHeader` + `AppFooter` (full nav + footer), states **which email** we'll
  write to ("We'll send any updates… to {email}. Please check that inbox, including spam."), and offers "Browse
  courses while you wait" + "Back to home" CTAs. Email falls back to the Google sign-in address when no separate
  contact email is set. Applies to the received / accepted / none states alike.

Verified locally (Playwright) that the application page renders with header, card, email note, CTAs, and footer.
Build clean; i18n parity 1164; 75 lib tests pass.

## [2.2.6] — Stop Chrome address-autofill hijacking the course / institution comboboxes (2026-05-27)

Frontend-only (one `halatuju-web` deploy). Reported on the live STPM top-3 picker: Chrome's saved-address
autofill (postcodes / localities) popped up **over** the course list, covering it. Both `ProgrammePicker`
and `InstitutionPicker` already set `autoComplete="off"`, but Chrome **ignores `off`** for fields it
heuristically classifies as address/contact. Switched both to `autoComplete="new-password"` — Chrome won't
autofill saved addresses into a new-password field, and since the inputs are `type="text"` no password UI
fires. Added `data-1p-ignore` + `data-lpignore="true"` so the new-password hint doesn't attract 1Password /
LastPass icons. Affects every course picker (decided + top-3 branches) and the matric-college / Form-6-school
pickers. Build clean.

## [2.2.5] — STPM "still deciding" top-3 degree picker + PISMP in SPM leaning pills (2026-05-27)

Frontend-only (one `halatuju-web` deploy, no api change):
- **STPM students who are "still deciding" now rank their top 3 degrees.** Previously the uncertain branch offered
  STPM students only the SPM-style pathway pills, which don't fit them — an STPM student weighs *specific degrees*,
  not pathways. They now get **3 ranked boxes (1st / 2nd / 3rd)**, each a type-to-search picker over the degrees their
  STPM results qualify them for (same `ProgrammePicker` as the decided branch). Selections dedupe across boxes and
  store as `top_choices` (rank + course + institution); empty slots are dropped and ranks re-sequenced on submit.
  Every box generates decision/profile signal — consistent with "no control without signal".
- **SPM leaning pills now show all 9 pathways, including PISMP.** The pills previously listed only *eligible*
  pathways, which silently dropped PISMP (Teaching / IPG). Leanings are exploratory, not a commitment, so the full
  menu (`PATHWAY_ORDER`) is shown — a student can lean towards a pathway even before qualifying.

Verified locally (Playwright): all 9 pills incl. PISMP render; the 3 STPM boxes select, dedupe, and persist
`top_choices` with institution + null gaps. Build clean; i18n parity 1161; 75 lib tests pass (+1 for null-slot filtering).

## [2.2.4] — STPM eligibility fix (0 for all STPM students) + scholarship list + decided-branch note (2026-05-27)

- **STPM eligibility bug (critical):** the apply form's degree picker showed "no eligible courses" for **every** STPM
  student. Root cause: the STPM eligibility view (`/stpm/eligibility/check/`) passed **raw** profile demographics
  (`male`/`malaysian`) to the engine, which compares against the Malay forms (`Lelaki`/`Warganegara`). All 1112 STPM
  courses require Malaysian citizenship, so `malaysian` ≠ `Warganegara` excluded every course → 0. (The SPM path
  normalises in its serializer; the STPM view didn't.) Fix: shared `normalize_gender`/`normalize_nationality` helpers
  (extracted from the SPM serializer, now used by both) applied in the STPM view. Verified live: a real STPM student
  goes from 0 → **601** eligible degrees. +1 regression test; 47 STPM/serializer/golden-master tests pass. (api)
- **Other-scholarships list updated** to JPA, Khazanah, PETRONAS, Bank Negara Malaysia, Program Dermasiswa B40,
  Maybank, Maxis, Sime Darby, Others (replaces MARA / Yayasan / Bank-corporate). (web, ×3 locales)
- **"Anything you'd like to add?"** free-text now shows for the **Decided** branch too (not just "still deciding"),
  so a decided student who can't find their exact course in the filtered list can tell us. (web)

Build clean; i18n parity 1159; 74 FE + 47 STPM backend tests pass.

## [2.2.3] — `coq` round-trip fix + STPM names canonicalised + "Public University" copy (2026-05-27)

Three frontend fixes, one `halatuju-web` deploy (no api change):
- **`coq` now round-trips to the edit form.** 2.2.2 persisted `coq` to the DB, but the auth context's
  profile-cache effect *overwrote* `KEY_PROFILE` on every refresh — dropping the camelCase `coqScore` and never
  mapping the backend's snake_case `coq_score` back. So the grades/edit form re-read `0`. The cache now **merges**
  (instead of overwriting) and maps `coq_score → coqScore`, so a stored co-curricular score shows on re-edit.
- **STPM centre names canonicalised to the MOE secondary list (by code).** All 584 STPM centres matched a secondary
  school by code (clean subset, zero gaps), but every name had drifted from the canonical MOE record (Title-Case copy
  with casing/bracket/apostrophe inconsistencies + truncations, e.g. `Datin Onn → DATIN ONN JAFFAR`, `Munsyi → MUNSHI`).
  Names now come from the canonical secondary list, so the STPM stream→school picker shows **identical** names to the
  About Me School field (ALL-CAPS, as About Me already displays).
- **"Public university degree" → "Public university"** in the Plans pathway dropdown (en/ms/ta).

Build clean; i18n parity 1156; 74 lib tests pass. Forward-only for `coq` (existing profiles fill in on next sync).

## [2.2.2] — Persist `coq_score` to the profile (co-curricular score now stored, not just local) (2026-05-27)

Follow-up to 2.2.1, fixing the *root* gap rather than just tolerating it. `coq_score` was collected at onboarding
but only kept in `localStorage` and **never synced**, so it was `null` for 100% of DB profiles (2.2.1 just defaulted
the null). The profile-sync payload now includes `coq_score` (both the onboarding sync and the auth-gate sync read it
from the saved profile); the backend already persisted it via `ProfileUpdateSerializer`. +1 sync regression test
(`test_sync_persists_coq_score`). A localStorage↔sync parity audit confirmed `coq` was the *only* un-synced field.
**Forward-only** — existing profiles persist `coq` on their next onboarding/sync (no backfill; nothing server-side
reads `coq`, so no decision impact). Merit stays a computed-on-the-fly derivative (correctly **not** stored).
Frontend (`halatuju-web`) + a backend test.

## [2.2.1] — Hotfix: eligibility 400 on null `coq_score` blanked the Plans pathway dropdown (2026-05-27)

Hotfix for the 2.2.0 Plans redesign. The apply page posts the **full** student profile to `/eligibility/check/`;
`coq_score` is `null` for **100% of prod profiles (601/601)**, and `EligibilityRequestSerializer` rejected null
`coq_score` with HTTP 400 — so the call failed and the Plans-step pathway dropdown showed the empty *"once your
results are in…"* state for **every SPM applicant** (476 with grades), even though their results were fine.
Fix: `EligibilityRequestSerializer.to_internal_value` now **strips nulls** so optional fields fall back to their
declared defaults (`coq_score`→5.0, `colorblind`→False, …) instead of erroring — one place, covers the whole class.
Backend-only, no migration. +1 regression test (full profile with null optionals → 200 + pathways); 100 courses +
serializer tests pass. **Root cause was missed in 2.2.0 because previews used mocked `pathway_stats` and the
post-deploy check sent a minimal payload, never the real full-profile call.** Deployed to `halatuju-api`.

## [2.2.0] — B40 apply-form "Your Plans" redesign — DEPLOYED TO PROD (2026-05-27)

Context-aware, progressive-disclosure rebuild of the apply-form Plans step (P1–P5), built on
`feature/plans-redesign` and shipped in one coordinated deploy. **Merged `acdb2a4` → `main`; both Cloud Run
services deployed (`halatuju-api-00156`, `halatuju-web-00205`, builds SUCCESS); live + verified on halatuju.xyz**
(served bundle carries the new strings; `/eligibility/check/` + `/fields/` 200). Migration `0010` (7 optional
fields) was applied **migrate-first** to prod and verified (7/7 columns on `scholarship_applications`, correct
`jsonb`/`text`/`varchar` types) before the push — additive, zero-downtime. 97 frontend + 1105 backend tests green.
The step now opens with one question (Decided / Still deciding) and reveals only eligible options; every control
generates a decision or profile signal. (The wider B40 programme remains **not promoted** — separate launch task:
wire Cloud Scheduler → `send_pending_decision_emails`.) Per-sprint detail below.

### P1 — storage foundation (backend, 2026-05-26)
- **7 new optional fields** on `ScholarshipApplication` (migration `0010_plans_redesign_fields`):
  `pathway_certainty`, `chosen_pathway`, `pre_u_track`, `pre_u_institution`, `chosen_programme` (json),
  `uncertainty_reasons` (json), `uncertainty_note`. All blank/default → backward-compatible.
- Wired through the intake (`ApplicationCreateSerializer`), read (`ApplicationReadSerializer`), and admin
  serializers, plus `services._APP_FIELDS` + `build_intake_snapshot` (persisted + frozen in the audit snapshot).
- **Engine unchanged**: shortlisting still gates on `intends_tertiary_2026` + `upu_status=='ipts'`; the new
  fields don't touch the decision or the `courses` eligibility engine (reused read-only by later sprints).
- Tests: +2 (sure + uncertain branch round-trip, snapshot, read serializer). Scholarship suite **95 passed**;
  migration applies cleanly on SQLite.

### P2 — Plans-step shell + eligible-pathway dropdown (frontend, 2026-05-26)
- The "Your Plans" step now opens with **one question — "Do you know which pathway you'll take?"** →
  *Yes, I've decided* / *I'm still deciding*. Nothing else shows until it's answered (progressive disclosure).
- **Decided (SPM leavers)** reveals a single-select **eligible-only pathway dropdown** — each option shows
  its eligible-programme count (e.g. *"Polytechnic — 85 eligible"*), fed live by the eligibility engine
  (`/eligibility/check/` → `pathway_stats` → `eligiblePathways()` in fixed order). New `<PathwaySelect>` component.
  STPM students see a degree-branch stub; *Still deciding* shows an exploration stub (both built in P5).
- **State + validation**: `ApplyFormState` gains `pathwayCertainty` + `chosenPathway`; payload adds
  `pathway_certainty` + `chosen_pathway` (P1 fields). `applyFormError` is now exam-type-aware — the pathway
  question is required (but *"still deciding"* is always a valid answer), and a decided SPM leaver must pick a
  pathway; STPM students are exempted (degree picker lands in P5). `upu_status` is **derived** from the chosen
  public pathway (no separate UPU question); `intends_tertiary_2026` stays true by default.
- **Replaced** the multi-select pathway chips, the UPU radio, and the "I intend to continue" checkbox + their
  i18n keys (×3 locales). Field-of-study + top-3 course pickers stay gated under "decided" pending P3 (which
  collapses them into one pathway-filtered course dropdown); "other scholarships" kept as an independent signal.
- Tests: +6 (eligible-pathways helper from P2a + certainty/chosen-pathway validation + payload mapping).
  Frontend suite **76 passed**; `next build` clean; i18n parity 1126 keys. Branch only — not deployed.

### P3 — Decided-course picker for programme pathways (frontend, 2026-05-26)
- When a student picks a **programme pathway** (Foundation / Public university / Polytechnic / Community
  college / Teaching-PISMP / ILJTM / ILKBS), the "decided" branch now reveals a **single-select, type-to-search
  course combobox** showing **only the courses that pathway makes them eligible for** (A–Z, with institution
  counts). New `<ProgrammePicker>` component (School-field UX, but constrained to the eligible list — no free text).
- Courses come from the **same `/eligibility/check/` call** P2 already makes — the page now also keeps
  `eligible_courses` and filters by `pathway_type` (`programmesForPathway()` helper). No new endpoint/fetch.
- **Matriculation & STPM** pathways show a short institution stub (their stream→school / track→college flow is P4).
- Picking a course stores `chosen_programme` (the P1 JSON field) and **derives `field_of_study`** from the
  course — no separate field question. `applyFormError` now requires the course on a decided programme pathway
  (matric/STPM exempt — P4; STPM students exempt — P5).
- **Removed** (delete-as-you-replace): the field-of-study `<select>` + the top-3 saved-courses picker that P2
  parked under "decided", their data fetches (`getSavedCourses` / `fetchFieldTaxonomy`), and 8 now-dead i18n keys
  (×3 locales). The one course dropdown replaces both.
- Tests: +8 (`programmesForPathway` filter/sort, `isProgrammePathway`, course requirement + matric/STPM exemptions,
  `chosen_programme` mapping). Frontend suite **84 passed**; `next build` clean (`/scholarship/apply` 36.1 kB);
  i18n parity 1125 keys. Branch only — not deployed.

### P4 — Institution pathways: Matriculation track→college + STPM stream→school (frontend, 2026-05-26)
- The two non-programme pathways now have their decided sub-flows (replacing the P3 institution stub):
  - **Matriculation** → **track** chips (only the tracks the student qualifies for, from `/calculate/pathways/`
    via `eligibleMatricTracks()`) → **college** picker (`MATRIC_COLLEGES` filtered to that track by `collegesForTrack()`).
  - **STPM / Form 6** → **stream** chips (Sains / Sains Sosial / *Not sure*) → **school** picker (the 584 Form 6
    centres in `stpm-schools.json`, filtered to that stream by `stpmSchoolsForStream()`).
- New generic `<InstitutionPicker>` (type-to-search name combobox, capped list + "keep typing" hint) — reused for
  both the college list and the 584-school list. Matric track eligibility comes from an extra `/calculate/pathways/`
  call fired alongside the existing eligibility call (SPM leavers only).
- Storage: track/stream → `pre_u_track`, college/school → `pre_u_institution` (P1 fields). `applyFormError` requires
  both on a decided matric/STPM pathway (STPM students still exempt — their degree picker is P5). `field_of_study`
  is intentionally left empty for pre-U pathways (no degree chosen yet; the track/stream is the signal).
- Tests: +9 (`isInstitutionPathway`, `eligibleMatricTracks`, `collegesForTrack`, `stpmSchoolsForStream`, the
  track/stream + institution validation, payload mapping). Frontend suite **93 passed**; `next build` clean
  (`/scholarship/apply` 37.2 kB); i18n parity 1144 keys. Branch only — not deployed.

### P5 — STPM-student degree picker + Uncertain branch (frontend, 2026-05-26)
- **Post-STPM students** (`exam_type === 'stpm'`) now get a real **degree picker** instead of the stub — their
  decided branch skips the SPM pathway step and reuses `<ProgrammePicker>` over the degrees from
  `/stpm/eligibility/check/` (mapped + sorted A–Z by `stpmDegreesToCourses()`, university shown as the institution).
  Stores `chosen_programme` + derives field. New validation: a decided STPM student must pick a degree.
- **"Still deciding" branch** is now built out (was a stub): optional **leaning chips** (eligible pathways →
  `pathways_considered`, SPM leavers only), **"Where are you right now?" reason chips** (→ `uncertainty_reasons`:
  exploring / waiting for results / want advice / family / finance), and a free-text line (→ `uncertainty_note`).
  All optional — "uncertain" never blocks the application.
- **Mentoring stays coordinator-set** (per the model's design): the reasons are captured + surfaced on the admin
  detail, and the coordinator flags `mentoring_candidate` from them (not auto-set at intake).
- Tests: +6 (`stpmDegreesToCourses`, `UNCERTAINTY_REASONS`, STPM degree requirement, uncertain-never-blocks,
  reasons/note payload). Frontend suite **97 passed**; `next build` clean (`/scholarship/apply` 37.5 kB); i18n
  parity 1156 keys. **Branch complete — ready for the gated ship (migrate-first → merge → deploy).**

## [2.1.5] — Apply-form: My Family ordering + required household size (2026-05-25)

### Changed
- **Field order in My Family** — "Number of people in your household" now comes *before* "Combined monthly household
  income", so the student counts the household first and then totals that group's income (the old order asked them to
  "add up the income of everyone you counted" before they'd counted anyone).
- **Tips work in concert** — the household tip now ends "Next, you'll total this group's monthly income"; the income
  tip now reads "everyone you counted **above**". (en/ms/ta)

### Added
- **Household size is now required** (`min 1`) — it's needed for the per-capita income calculation. New `householdSize`
  validation + error message (en/ms/ta), surfaced on the My Family step. (+1 test)

## [2.1.4] — Apply-form: one tooltip, phone mask, per-step validation (2026-05-25)

### Fixed
- **Duplicate tooltip** — the `i` bubble dropped its native `title` attribute, which had been showing a second, drab
  browser tooltip on hover. Hover (desktop) and click/tap (mobile) now open the same custom popover.

### Added
- **Phone auto-mask** — phone and parent-phone fields format to `0XX-XXX XXXX` as digits are typed (`formatPhone`),
  matching the NRIC mask; pre-filled profile values are masked on load too.
- **Validation on Continue** — each step is validated when the student clicks Continue (not only at final submit):
  advancing is blocked while the current/earlier step has an error, which is surfaced there. Phone is now
  format-validated (9–11 digits, leading 0); parent phone is optional but validated when present (`parentPhone` error).

### Tests
- +8 unit tests (`formatPhone`, `isValidPhone`, phone/parent-phone validation). i18n parity **1121 → 1122** keys.

### Follow-ups (same day)
- **Landline-aware phone mask** — `formatPhone` now detects the Malaysian area-code length by prefix (mobile 01X and
  Sabah/Sarawak 08X = 3 digits; 03/04/05/06/07/09 = 2) and groups accordingly: `03-1234 5678`, `04-123 4567`,
  `088-123 456`, `012-345 6789`. (+1 test)
- **Consent control is now a toggle** — the consent on the Support step matches the STR/JKM toggle switches in My
  Family (label left, switch right) instead of a lone checkbox. `Toggle` extracted to `components/Toggle.tsx`.

## [2.1.3] — Apply-form: friendlier help bubble (2026-05-25)

### Changed
- The field help `i` bubble is restyled on-brand and extracted to `components/InfoTip.tsx`: a primary-tinted `i` with a
  ring, and a white rounded popover card with a soft primary border, shadow, caret and a lightbulb icon — replacing the
  flat grey `i` + hard dark-grey tooltip. Adds an optional `defaultOpen` prop. Applies to every apply-form field tooltip.

## [2.1.2] — Apply-form: home link, IC mask, searchable school field (2026-05-25)

Three usability fixes on `/scholarship/apply` (raised from the live form). All `halatuju-web`; deployed via push
to `main` (`9aa5d9e`).

### Added
- **Searchable School field** — the free-text School input is now a search-as-you-type field over all **2,480
  Malaysian secondary schools** (`PERINGKAT = Menengah`: SMK, SBP, SMKA, KV, KT6, SM SABK, etc.), each shown with its
  state, sourced from the MOE directory `SenaraiSekolahWeb_April2026.xlsx` (kept in `/docs` for provenance). Includes a
  **"can't find your school? just type it"** free-text fallback so a missing/misspelled school never blocks an
  applicant. New `src/data/secondary-schools.{json,ts}` (+ `searchSchools` helper) and `components/SchoolSelect.tsx`.
  The field still stores the school **name** (no backend/schema change).
- **Home link on desktop** — the apply form's desktop step-rail now has a Home link back to `/scholarship` (the mobile
  bottom bar already had one; desktop had no way back).

### Changed
- **IC number auto-masks** to `XXXXXX-XX-XXXX` as digits are typed (`formatNric`). Previously a student could type 12
  bare digits that silently failed the `NRIC_RE` check on submit; the mask produces exactly the format the validator
  and the claim endpoint require.

### Follow-ups (same day)
- School field tip now reads "where you sat for SPM **or STPM**" (was SPM only); the search placeholder shows a
  sample name — "Start typing, e.g. SMK Vivekananda" (a real entry) — so the SMK abbreviation/format is clear. (en/ms/ta)

### Tests
- +6 unit tests (`formatNric`, `searchSchools`, school-data integrity). i18n parity **1118 → 1121** keys
  (`schoolSearchPlaceholder` / `schoolNotListed` / `schoolNoMatch`, en/ms/ta). Production build clean
  (`/scholarship/apply` 8 kB → 37.6 kB from the route-split school list).

## [2.1.1] — Post-deploy: /scholarship copy + layout fixes (2026-05-25)

Small production follow-ups after the B40 redesign went live. All `halatuju-web` only; deployed to halatuju.xyz via
push to `main` (3 commits: `6706837`, `9d7224d`, plus the earlier OG/hero fixes).

### Changed
- **"Can I apply?" section restructured** — a single shared heading now spans two columns: the requirements
  checklist (left) and the "Please note" callout kept as-is (right). Heading reworded to first-person **"Can I apply?"**
  to match the copy doc (en/ms/ta).
- **Landing copy aligned with `docs/halatuju_scholarship_landing_copy.md`** across **en/ms/ta** — the page had still
  been running the older pre-doc wording. Reworked hero sub, lead paragraphs (dropped the "our community / self-help"
  framing), value cards; **Please note 5 → 7 bullets** (added Limited places, Trust w/ light verification, Under 18);
  **Can I apply 5 → 6 requirements** (added 20-min interview + quarterly-progress lines, DOSM citation, "Solid academic
  record"); How-it-works timing ("same day", "within 48 hours", MyNadi named, "up to two months"); FAQ replaced with
  the approved 9-question set.

### Added
- **"Want to support a student?"** donor section — **Get in touch** → `mailto:info@halatuju.xyz?subject=Sponsor enquiry`;
  "Funds are administered by MyNadi Foundation" with a link to yayasanmynadi.org. **Section 44(6) tax line omitted**
  until MyNadi's status is confirmed.
- **"About this programme"** section — partners credited; the partner whose registered name contains "Indian" is shown
  as the **acronym "CUMIG" only**, to keep the word off the public page (MyNadi 44(6) non-discrimination).

### Verified
- i18n parity 1118 keys across en/ms/ta (0 warnings); production build clean.

## [2.1.0] — B40 Redesign · Sprint 12b: DEPLOYED to production (2026-05-25)

The B40 redesign (S7–S12a) is **live in production**. `feature/b40-redesign` merged to `main` (release merge
`55c2c36`); both Cloud Run services rebuilt + deployed; health checks 200.

### Deployment
- **Migrations applied to prod first** (zero-downtime, additive): courses `0048` + scholarship `0007`, `0008`, `0009`.
  Confirmed via `showmigrations` + an information_schema column check. **Note:** the Cloud Run deploy triggers do
  **not** run migrations (build → push → deploy only), so migrations were applied manually *before* pushing `main`,
  keeping the existing live site healthy throughout.
- **Cohort `b40-2026`** verified live and **thresholds corrected to the settled S8 values**: a pre-existing row from
  Phase 1 still had the advertised cut-offs (`min_spm_a_count=5`, `min_stpm_pngk=3.0`); set to the engine's lenient
  `4` / `2.9` (B+ count 5, per-capita 1584, 2h/48h delays were already correct). Added an idempotent
  `seed_b40_2026_cohort` management command (+ 3 tests) for reproducible cohort creation.
- Post-deploy security advisors: 0 errors (scholarship tables' "RLS enabled, no policy" are the intended
  deny-by-default design; all WARNs pre-existing).

### Deferred (must do before promoting)
- **Cloud Scheduler → `send_pending_decision_emails`** — not wired (no applicants while the site is unpromoted).
  Required before the programme is promoted, or shortlist/decline reveal emails won't fire.
- **Vision OCR** → post-launch S13 (new Google Vision key + cost sign-off).

### Tests
- Backend **1100 → 1103** (cohort seed command). Migrations verified on prod. No frontend change.

## [Unreleased] — B40 Redesign · Sprint 12a: apply-form desktop responsiveness (2026-05-24)

The desktop layout for the apply form (the item deferred from S9). Frontend only; on `feature/b40-redesign`, not deployed.

### Changed
- `/scholarship/apply` is now responsive on desktop: on `lg` it becomes a **two-column layout** — a left vertical
  **step-nav rail** (the five sections, active highlighted, completed ticked) beside the active section card +
  Back/Continue — using the horizontal space the mobile single column left empty. The mobile **bottom tab bar is
  now `lg:hidden`** (the rail replaces it on desktop), and the container widens (`max-w-2xl` → `lg:max-w-4xl`).
- Mobile is unchanged (single column, progress, section card, bottom tab bar). The change is contained to the
  page's layout shell — section content and the mobile flow are untouched.

### Notes
- The `/scholarship/application` cards (received/accepted) already read fine centred at `max-w-2xl` — left as-is.
  `ScholarshipNextSteps` (post-shortlist follow-up) wasn't touched; can get a desktop pass later if needed.

### Tests
- `next build` clean. Frontend jest unchanged (49 — layout only). Backend unchanged (1100). No i18n change, no migration.

## [Unreleased] — B40 Redesign · Sprint 11b: applicant application states + login banner (2026-05-24)

The applicant-facing half of S11. Frontend only; on `feature/b40-redesign`, not deployed.

### Added
- `/scholarship/application` gains the **accepted** state — a distinct "confirmed" card (congratulations + "our team
  will be in touch about your award"), separate from the neutral received card. Full status map now: submitted →
  received · shortlisted → follow-up · **accepted → confirmed** · rejected/withdrawn → neutral.
- **`ScholarshipBanner`** — a self-contained dashboard banner that fetches the caller's application and renders only
  when it's **shortlisted** ("complete your application") or **accepted** ("confirmed"), linking to
  `/scholarship/application`; renders nothing otherwise (margin lives on the banner so there's no empty gap). EN/MS/TA i18n.

### Tests
- Frontend jest unchanged (49 — display + one fetch, no new pure logic). Backend unchanged (1100). `next build`
  clean; i18n 1107-key parity.

## [Unreleased] — B40 Redesign · Sprint 11a: admin verify-&-accept + NRIC lock + mentoring (2026-05-24)

The human verification gate for MyNadi admins. Backend + admin frontend; on `feature/b40-redesign`, not deployed.
(Applicant application-page states + login banner split to S11b.)

### Added
- **`AdminVerifyAcceptView`** (`POST /admin/scholarship/applications/<id>/verify-accept/`): admin confirms a
  checklist (NRIC / name / results / document) against the uploaded MyKad → sets `profile.nric_verified` (**locks**
  the NRIC), stamps `verified_at` / `verified_by` / `verify_checklist`, and advances the application
  **shortlisted → accepted**. Only a shortlisted application can be accepted.
- New **`accepted`** application status (passed the auto-screen = shortlisted; human-verified & confirmed = accepted).
- Mentoring-candidate toggle via **PATCH** on the admin detail endpoint.
- Admin detail page (`/admin/scholarship/[id]`): a **Verify-&-accept checklist card** (Accept enabled only when all
  four are ticked; shows the locked/accepted + verified-by state) + a mentoring-candidate toggle. EN/MS/TA i18n.
- `verified_at` / `verified_by` / `verify_checklist` audit fields; serializer exposes `nric` (full, for comparison),
  `nric_verified`, the audit fields, `mentoring_candidate`, and the S10 plans/support intake. Migration `0009`.

### Fixed
- **TD-054 resolved**: NRIC uniqueness is now enforced at the single verify-&-accept point — if another profile
  already has that NRIC *verified*, the endpoint returns `409 nric_conflict` for the admin to resolve (the soft-NRIC
  "clash surfaces at verification" design), instead of the old claim transfer-path PK collision.

### Tests
- Backend **1095 → 1100** (verify-accept happy path, TD-054 conflict, only-shortlisted guard, mentoring toggle,
  non-admin 403). Migration `0009` + golden masters intact. Frontend jest unchanged (49).

## [Unreleased] — B40 Redesign · Sprint 10: apply form ② — My Plans + Support + "received" (2026-05-24)

The second half of the apply form. Frontend only (every field was already accepted by `ApplicationCreateSerializer`
since S7); on `feature/b40-redesign`, not deployed.

### Added
- **My Plans**: "intend to continue tertiary study" gate checkbox; **pathways considering** multi-select chips;
  **UPU / destination** radio (with an inline amber note when "private (IPTS)" is picked — IPTS-only is out of
  scope and the S8 engine declines it); **field of study** dropdown (from the field taxonomy); **top-3 course
  choices** picked from the student's **saved courses** (ranked by tap order, max 3, friendly empty-state);
  **other scholarships** multi-select chips + free text → funding-overlap signal.
- **My Support**: help-with-university + help-with-scholarship radios (optional, Yes/No/Not sure), "anything else"
  free text, required consent.
- `scholarship.ts`: plans/support form state + payload mapping (`top_choices` ranked by order) + constants
  (`UPU_OPTIONS`, `HELP_OPTIONS`, `OTHER_SCHOLARSHIP_OPTIONS`, `TopChoice`); apply page fetches saved courses
  (exam-type aware) + field taxonomy on mount. EN/MS/TA i18n.

### Changed
- The apply form's single `intended_pathway` select is replaced by the `pathways_considered` multi-select; the
  `notes` free-text is replaced by `anything_else`. `intends_tertiary_2026` kept (engine hard gate) as a checkbox.

### Notes
- The post-submit **"Application received"** screen already works (S8's silent-score keeps status `submitted`, so the
  application page shows the neutral "received — we'll be in touch" card; the follow-up only appears once shortlisted).
  No auto-advance.

### Tests
- Frontend jest **49** (top_choices builder + plans/support payload; replaces the dropped notes test). Backend unchanged (1095).

## [Unreleased] — B40 Redesign · Sprint 9b: My Results edit → onboarding round-trip (2026-05-24)

Wires the apply form's My Results "edit/add results" into the full onboarding flow and brings the student back
without losing in-progress edits. Frontend only; on `feature/b40-redesign`, not deployed.

### Changed
- **My Results "edit / add results"** now routes through the **full onboarding** (`/onboarding/exam-type` → grades
  → … → "a few more details") instead of `/profile` or `/quiz`, so the profile ends up complete for course
  recommendations too.
- The **final onboarding step** is context-aware: entered from the apply form, its button reads **"Save & return
  to application"** and routes back to `/scholarship/apply` (otherwise unchanged → dashboard).

### Added
- **Stash & restore** of in-progress About-Me/My-Family edits across the onboarding detour (sessionStorage): the
  form only commits on submit, so edits are stashed before leaving and restored on return (landing on the Results
  tab). Helpers `stashApplyForm` / `popApplyStash` / `hasApplyReturn` / `clearApplyReturn` (storage-injectable,
  SSR-safe); orphan return-marker cleared on a normal apply visit.
- i18n `onboarding.saveReturnToApplication`; Results CTA copy updated (edit/add → onboarding).

### Tests
- Frontend jest **44 → 49** (stash/restore round-trip, marker set/clear, SSR no-op). Backend unchanged (1095).

## [Unreleased] — B40 Redesign · Sprint 9: apply form ① — About Me + My Family (2026-05-24)

Apply-form rebuild, first half. Inline-editable **About Me** + **My Family**, commit-on-submit. Frontend +
small backend write-back; on `feature/b40-redesign`, not deployed. Mobile-first (desktop layout is S12).

### Changed
- **About Me** (was read-only "About You") is now **inline-editable**, pre-filled from the profile: full name,
  school, **NRIC** (editable until verified, read-only + "Verified" badge once locked), referring organisation,
  home state, phone. **Contact email is locked** (already verified). The old "Edit → /profile" bounce is gone.
- **Commit-on-submit** — edits live in form state; on a successful submit the About Me + My Family fields sync to
  the canonical profile (`sync_profile_fields`), and the **NRIC commits via the validated claim path** (never the
  application payload). A failed submit persists nothing.
- Section headings are first-person (**About Me**, **My Family**); tab labels stay short (About / Family / …).
- Validation now enforces the required About-Me fields (name, school, NRIC format, referring org, home state,
  phone) + household income, and **jumps the user to the offending tab**; the error banner moved out of the
  Support tab so it shows on whichever tab the error is on.

### Added
- **My Family**: parent/guardian **name + phone** (stored in `profile.guardians`) and **preferred call language**
  (en/ms/ta/mixed → `profile.preferred_call_language`); `i` tooltips on income, household, STR, JKM.
- Required `*` + `i` info-bubble tooltips across About Me + My Family (`InfoTip` + `FieldLabel` components).
- Referring-organisation **fixed dropdown** (9 legacy options) → stored as `referral_source`, resolved to the
  `referred_by_org` FK server-side when a matching active `PartnerOrganisation` exists.
- `scholarship.ts`: new form fields + `nricChanged`, `REFERRING_ORG_OPTIONS`, `CALL_LANGUAGE_OPTIONS`,
  `MALAYSIAN_STATES`; `ApplicationCreateSerializer` accepts the new write-only profile fields; profile GET returns
  `referral_source` + `guardians`. EN/MS/TA i18n (labels, tooltips, headings, validation).

### Tests
- Backend **1093 → 1095** (About-Me/Family write-back + referring-org FK resolution). Frontend jest **37 → 44**.

## [Unreleased] — B40 Redesign · Sprint 8: decision engine + silent-score + delayed reveal (2026-05-24)

The deterministic decision engine (final policy calls settled). Backend only; on `feature/b40-redesign`, not deployed.

### Changed
- **`shortlisting.py` rewritten** to the settled rule (no score/weights/hardship): hard gates (consent · intends
  public study · not IPTS-only) → academic floor (SPM ≥4 at A- AND ≥5 at B+ / STPM PNGK ≥2.9) → income (STR →
  pass, bucket A; else per-capita income < `per_capita_ceiling` RM1,584 → pass, bucket B). `evaluate()` returns
  `verdict` (shortlisted/rejected) + bucket + reason.
- **Submit no longer decides instantly** — it scores **silently** (`score_application`): stores verdict +
  `decision_due_at`, status stays `submitted`, only the acknowledgement email is sent.
- **Delayed reveal** via `send_pending_decision_emails` (now release-due-decisions): flips status + sends the
  email at `decision_due_at` — **+2h** shortlist (invitation), **+48h** decline (warm).
- **Decline email** rewritten warm (EN/MS/TA): "not successful this round, all the best, you're welcome at our
  higher-education seminars — we'll send invites."

### Added
- Cohort: `per_capita_ceiling` (1584), `min_spm_bplus_count` (5), `success_delay_hours` (2), `decline_delay_hours`
  (48); defaults `min_spm_a_count` 5→4, `min_stpm_pngk` 3.0→2.9.
- Application: `verdict`, `decision_due_at`, `decision_released_at`. Migration scholarship `0008`.

### Tests
- Backend **1093 pass** (golden masters intact). Rewrote engine tests (per-capita + academic-floor + IPTS + STR),
  scheduler tests (release-due / idempotent / dry-run), submit tests (silent score), cohort-defaults; added a
  per-verdict-delay scoring test.

## [Unreleased] — B40 Redesign · Sprint 7: backend foundation (soft-NRIC + intake fields) (2026-05-23)

Foundation for the decision-engine redesign + apply-form rebuild (6-sprint roadmap in
`docs/scholarship/b40-decision-redesign-plan.md`). Backend only; on `feature/b40-redesign`, not deployed.

### Added
- **`StudentProfile.nric_verified`** (Bool), **`coq_score`** (Float — co-curricular score now persisted,
  was transient), **`preferred_call_language`**. Profile GET returns all three.
- **`ScholarshipApplication`** new intake fields (all optional): `field_of_study`, `pathways_considered`,
  `top_choices`, `upu_status` (incl. an IPTS option), `other_scholarships` (+ free text), `help_university`,
  `help_scholarship`, `anything_else`, `mentoring_candidate`. Carried through the create serializer,
  `_APP_FIELDS`, the audit `intake_snapshot`, and the read serializer.
- Migrations: courses `0048`, scholarship `0007`.

### Changed
- **Soft-NRIC (supersedes "IC immutable"):** uniqueness now enforced **only when verified**
  (`unique_verified_nric` replaces `unique_nric_when_set`); NRIC is **read-only on PUT/sync** (claim path
  only); the claim endpoint **blocks a change once verified** (403 `nric_locked`). See `docs/decisions.md`.

### Tests
- Backend **1091 pass** (was 1086; +4 soft-NRIC, +1 intake round-trip), golden masters intact (SPM 5319,
  STPM 2026). Updated `test_profile_fields` (PUT no longer sets NRIC; uniqueness only when verified).

## [Unreleased] — B40 Assistance Programme · Phase 1.5c public landing + follow-up route (2026-05-22)

Added the public marketing landing and gave the post-submission follow-up its own page.

### Added
- **`/scholarship/` landing** (public, no sign-in) — Stitch-designed, community self-help framing:
  hero + AI imagery, overview + value cards, a "Please note (pilot)" callout, a "Can you apply?"
  checklist (Indian-descent pilot, B40 < RM5,860, 5 A's / PNGK 3.0, public post-secondary), an
  8-step "How it works" timeline, a 10-item FAQ accordion, and a closing CTA. Renders with
  `AppHeader`/`AppFooter` like other content pages.
- **`/scholarship/application`** — the post-submission home: shortlisted students complete their
  follow-up (`ScholarshipNextSteps`) here; everyone else sees a neutral "received" status; visitors
  with no application are sent to apply. The apply page now redirects returning applicants here and
  routes here after submit (no more inline status branch).
- **AI imagery** (Gemini, via Stitch) saved as real assets: `public/scholarship/hero.jpg`,
  `community.jpg`. Hero is `priority`; the CTA image lazy-loads.
- **i18n**: `scholarship.landing.*` + `scholarship.application.*` in EN/MS/TA (1002 keys, parity
  verified). Gate button copy and all landing copy use the approved British-English wording.

### Tests / verification
- Jest **37 pass**; `next build` green (`/scholarship`, `/scholarship/application`, `/scholarship/apply`
  all compile). Live render check on `next dev` confirmed the landing renders (hero image, value cards,
  pilot callout, requirements, timeline, FAQ, CTA, footer). Not deployed.

## [Unreleased] — B40 Assistance Programme · Phase 1.5b apply-form frontend rebuild (2026-05-22)

Rebuilt the student apply flow to the profile-canonical API and the Stitch-approved design
(landing soft sign-in gate + tabbed 5-section form).

### Added / Changed
- **Soft sign-in gate** — anonymous visitors read the eligibility criteria freely and apply via a
  one-tap "Continue with Google" (the same button registers new students), with a "we'll use your
  profile so you never retype" reassurance. Replaces the old plain sign-in prompt.
- **Tabbed 5-section apply form** (Form A) — About You · Your Family · Your SPM/STPM Results ·
  Your Plans · Support, with a step progress bar + sticky bottom tab bar.
  - Sections 1 & 3 are **read-only, pre-filled from the profile** with "From your HalaTuju profile"
    badges and Edit links; results show A-count / A+ / STPM CGPA, or a "finish your quiz" prompt when
    the profile has no academic data yet.
  - Section 2 (Family) **writes financial fields back to the profile** (income, household size, STR/JKM
    toggles) with a "this also updates your HalaTuju profile" caption.
  - Academic data is **never posted** — the backend reads it from the profile.
- **`scholarship.ts`** — `ApplyFormState` slimmed to the financial + application fields;
  `profileToApplyDefaults` pre-fills financial from the profile; new `profileAcademicSummary` helper;
  `buildApplicationPayload`/`applyFormError` drop the academic fields.
- **API types** — `StudentProfile` gains the financial fields; student `ScholarshipApplication` uses
  `exam_type` (was `qualification`) and exposes `intake_snapshot`. (Admin types/serializer unchanged.)
- **i18n** — new `scholarship.apply.*` keys (gate, tabs, sections, read-only field labels, write-back
  note, results summary, empty states) in EN/MS/TA; 925 keys, parity verified.

### Tests
- `scholarship.test.ts` updated to the new shape (20 pass); full Jest **37 pass**; `next build` green
  (`/scholarship/apply` compiles). Not deployed.

## [Unreleased] — B40 Assistance Programme · Phase 1.5a source-of-truth refactor (2026-05-22)

Made the HalaTuju profile the single source of truth for applicant data, plus de-Gmailed email.

### Changed
- **Profile is canonical.** Moved academic (read from existing `grades`/`exam_type`/`stpm_cgpa`) and
  financial data to `courses.StudentProfile`: added `household_income`, `household_size`,
  `receives_str`, `receives_jkm`, `guardians` (migration `courses 0047`).
- **`ScholarshipApplication` slimmed** (migration `scholarship 0006`) — removed the duplicated
  `qualification`/`spm_a_count`/`stpm_pngk`/`household_income`/`household_size`/`receives_str`/
  `receives_jkm`; added `intake_snapshot` (immutable record of what was declared at submit time).
- **Shortlisting reads the profile live** — `shortlisting.evaluate()` scores academic + income from
  `application.profile`; intent + consent stay per-application. `count_spm_a_grades` now lives in
  `shortlisting.py`.
- **Apply flow writes back** — `services.sync_profile_fields` syncs the form's financial fields to the
  profile (non-None only, never blanks an existing value); `build_intake_snapshot` freezes the audit copy.
- **Serializers** — create accepts the financial write-back fields (write-only); read + admin serializers
  derive academic/financial from the profile and expose `intake_snapshot`.
- **Email de-Gmailed** — `production.py` email is now fully env-driven (Brevo SMTP relay default);
  no personal address in code. Deploy sets `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` + verifies the sender domain.

### Tests
- Full backend suite **1086 pass**. Updated `test_shortlisting`/`test_api`/`test_models`/
  `test_admin_scholarship` for the profile-canonical shape; removed the obsolete
  "explicit a-count override" test; added write-back + snapshot coverage.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 6b (2026-05-22) — Phase 1 build complete

MyNadi admin console UI (frontend) — completes Sprint 6 and the Phase 1 build.

### Added
- **`/admin/scholarship`** — applications list with status + bucket filters.
- **`/admin/scholarship/[id]`** — full applicant detail (intake, funding, documents, referees,
  consent) + AI sponsor-profile panel: Generate → edit Markdown → Save → Publish, with status badge.
- Admin API client (`getScholarshipApplications`, `getScholarshipApplication`,
  `generateSponsorProfile`, `saveSponsorProfile`, `publishSponsorProfile`); "B40 Applications" nav link.
- i18n: `admin.scholarship.*` in EN/MS/TA (894 keys, parity verified).

### Tests
- Frontend suite **37 pass**; check-i18n PASS; `next build` — both admin pages compile.

### Phase 1 status
- **All 6 sprints complete.** Backend 1086 tests, frontend 37, golden masters intact, on
  `feature/b40-assistance` (not deployed). Remaining: the single Phase-1 deploy (carry-forwards) and
  Phase 0 legal/entity sign-off before public launch.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 6a (2026-05-22)

AI sponsor-profile drafting + MyNadi admin API (backend; the admin console UI is 6b).

### Added
- **`SponsorProfile` model** (OneToOne application; `draft_markdown`/`edited_markdown`, status
  draft→approved→published, `model_used`, timestamps; migration 0005, RLS).
- **`profile_engine.py`** — `generate_sponsor_profile()` drafts a sponsor-ready Markdown profile
  from intake + deeper-info + funding + grades + referee via the Gemini cascade (graceful error).
- **Admin API** (reuses `PartnerAdminMixin`, super-admin sees all): list applications (status/bucket
  filter), full detail (intake/funding/docs/referees/consents/profile), generate-profile, edit
  profile, publish — under `/api/v1/admin/scholarship/`.

### Tests
- 9 new (`test_admin_scholarship.py`, Gemini mocked). Full backend suite **1086 pass, 0 fail**;
  golden masters unchanged.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 5b (2026-05-22)

Document upload + referee + consent UI (frontend) — completes Sprint 5.

### Added
- **`ScholarshipDocuments`** — per-doc-type upload (sign → PUT straight to Supabase Storage →
  record), list with signed-URL view links + delete.
- **`ScholarshipReferee`** — add/list referees.
- **`ScholarshipConsent`** — DRAFT consent text + checkbox; guardian name/relationship fields when
  the applicant is a minor; "consent given" once recorded.
- Wired as steps 4–6 of the next-steps checklist.
- API client: sign-upload, direct PUT, record/list/delete docs, referee CRUD, consent get/record;
  `DOC_TYPES` + `formatFileSize` helpers.
- i18n: `scholarship.docs/referee/consent` + step 4–6 labels in EN/MS/TA (856 keys, parity verified).

### Tests
- 2 new helper tests (frontend suite **37 pass**); check-i18n PASS; `next build` success.

### Notes
- UI + network glue; the upload PUT-to-Storage and consent round-trip need the live `b40-documents`
  bucket — folded into the browser smoke-test carry-forward.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 5a (2026-05-22)

Document vault + referee + e-consent (backend; frontend is 5b).

### Added
- **`ApplicantDocument`, `Referee`, `Consent` models** (migration 0004; all RLS deny-by-default).
- **`storage.py`** — signed upload/download URLs for a private Supabase Storage bucket
  (`b40-documents`) via stdlib `urllib` + the service key; file bytes go browser↔Storage, never
  through Django. Best-effort (returns None on failure).
- **Endpoints** (scoped to the caller's shortlisted application): `documents/sign-upload/`,
  `documents/` (list/record), `documents/<id>/` (delete), `referees/`, `consent/`.
- **Consent + guardian gate** — versioned (`CONSENT_VERSION`), withdrawable, supersedes prior; a
  **minor (<18, age from NRIC DOB) requires a guardian** (name + relationship) or consent is rejected.
- `age_from_nric` / `is_minor` / `record_consent` services.

### Tests
- 18 new (`test_consent.py` 9, `test_documents.py` 9). Full backend suite **1077 pass, 0 fail**;
  golden masters unchanged.

### Notes
- Two deploy carry-forwards: create the `b40-documents` private bucket; replace the DRAFT consent
  text (`CONSENT_VERSION = '2026-draft-1'`) with the lawyer-reviewed version.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 4b (2026-05-21)

Post-shortlist next-steps flow (frontend) — completes Sprint 4.

### Added
- **`ScholarshipNextSteps` component** — a 3-step checklist driven by the `completeness` block:
  course quiz (links to the existing `/quiz`), about-you textareas, and a funding-need line-item
  form with a live RM total. PATCHes to the Sprint 4a details endpoint; "all done" banner on completion.
- Shortlisted applications on `/scholarship/apply` now render this flow (rejected/submitted keep
  the status card).
- `scholarship.ts` helpers: `fundingTotal`, `buildDetailsPayload`, `applicationToDetailsForm`,
  `emptyDetailsForm`.
- API: extended `ScholarshipApplication` type (`funding_need`, `completeness`, deeper-info) +
  `updateScholarshipDetails()` PATCH.
- i18n: `scholarship.nextSteps.*` in EN/MS/TA (819 keys, parity verified).

### Tests
- 5 new helper tests (frontend suite **35 pass**); check-i18n PASS; `next build` success.

### Notes
- Verified at compile + unit + i18n level; the PATCH round-trip + quiz-then-return flow need a
  browser smoke test against a live backend before Phase 1 ships (existing carry-forward).

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 4a (2026-05-21)

Post-shortlist data layer: funding need + deeper info + completeness (backend; frontend is 4b).

### Added
- **`FundingNeed` model** (OneToOne → application, `funding_needs`) — line items (tuition_gap,
  laptop, hostel, transport, books, monthly_allowance × allowance_months, other, other_desc) + a
  computed `total`. Quantifies the funding ask (the B40 analysis flagged its absence).
- **Deeper-info fields** on `ScholarshipApplication`: `aspirations`, `plans`, `fears`, `justification`.
- **`PATCH /api/v1/scholarship/applications/<id>/`** — saves deeper-info + funding need for the
  caller's own **shortlisted** application; read serializer now returns `funding_need` + a
  `completeness` block (`quiz_done` / `details_done` / `funding_done` / `complete`).
- `application_completeness()` + `save_application_details()` services. Migration 0003.
- `funding_needs` added to the deny-by-default RLS SQL.

### Tests
- 11 new (`test_details.py`). Full backend suite **1059 pass, 0 fail**; golden masters unchanged.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 3 (2026-05-21)

Mechanical shortlisting engine + Bucket A/B + pass/fail decision emails.

### Added
- **`apps/scholarship/shortlisting.py`** — pure `evaluate(app, cohort)` → status/bucket/reason.
  Per-criterion OK/marginal/fail across academic (A-count or PNGK), income (STR anchor + ceiling
  × 1.15 marginal band), intent and consent. All-OK → Bucket A; exactly one marginal → Bucket B;
  otherwise rejected. All thresholds read from `ScholarshipCohort`.
- **`shortlist_application()`** wired into the intake view — runs synchronously on submit, persists
  status/bucket/reason/shortlisted_at, sends the pass email immediately.
- **Trilingual pass + fail emails** (refactored `emails.py` onto a shared `_send` helper).
- **`send_pending_decision_emails` management command** — sends the courteous "not this round"
  email after `fail_email_delay_days`; `--dry-run`, prints the DB host, reads config from settings.
- Model fields `shortlisted_at`, `decision_email_sent_at`, `locale`, `notify_email` (migration 0002).

### Changed
- Submitting now triggers an instant shortlist: a qualifying applicant receives the acknowledgement
  *and* a congratulations email; a rejected applicant receives only the acknowledgement, with the
  fail email deferred to the command after the cohort delay.

### Tests
- 25 new (`test_shortlisting.py` 19, `test_decision_emails.py` 6) + updated intake tests. Full
  backend suite **1048 pass, 0 fail**; SPM/STPM golden masters unchanged.

### Notes
- The fail-email command's scheduler (e.g. Cloud Scheduler) is not yet wired — deploy work,
  deferred with the Supabase migration/RLS to the end of Phase 1.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 2 (2026-05-21)

Native application form + single front door (frontend), wired to the Sprint 1 intake API.

### Added
- **`/scholarship/apply` page** — trilingual application form with a requirements intro and
  status-gated rendering (loading / sign-in gate / form / success / already-applied), pre-filled
  from the AuthProvider profile. Lightweight academic capture (SPM A-count or STPM PNGK); full
  grades + quiz stay deferred to STEP 1A.
- **`src/lib/scholarship.ts`** — pure, node-testable helpers (`countAGrades`,
  `profileToApplyDefaults`, `buildApplicationPayload`, `applyFormError`).
- **API client** — `submitScholarshipApplication` + `getMyScholarshipApplications`.
- **`'apply'` auth-gate reason** — new branch in `auth-context` + `AuthGateModal` that reuses the
  existing Google sign-in + NRIC-claim flow and returns the user to `/scholarship/apply`.
- **"B40 Aid" header nav link.**
- **i18n** — `scholarship.*` block + `authGate.applyReason` in EN/MS/TA (793 keys, parity verified).

### Tests
- 13 new (`src/lib/__tests__/scholarship.test.ts`); full frontend suite **30 pass** (17 + 13).
- check-i18n PASS; `next build` success (`/scholarship/apply` compiles + prerenders).

### Notes
- Verified at compile + unit + i18n level. The OAuth round-trip (sign-in → return to apply) has
  not been browser-smoke-tested against a live backend — do so before Phase 1 ships.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 1 (2026-05-21)

New `apps/scholarship/` app — the financing extension's intake backbone. Phase 1 carries
no sponsor or money flow (those are Phases 2-3). See `docs/scholarship/b40-assistance-prd.md`
and `docs/scholarship/b40-phase1-roadmap.md`.

### Added
- **`ScholarshipCohort` model** (`scholarship_cohorts`) — per-round config holding the
  configurable shortlisting thresholds (`min_spm_a_count`, `min_stpm_pngk`, `income_ceiling`,
  `bucket_b_margin`) and funding/workflow parameters (`funding_envelope`, `fail_email_delay_days`)
  that the Sprint 3 rules engine will read.
- **`ScholarshipApplication` model** (`scholarship_applications`) — one application per student
  per cohort (partial unique constraint), with explicit shortlisting inputs (qualification,
  spm_a_count, stpm_pngk, household_income/size, receives_str/jkm, intended_pathway,
  intends_tertiary_2026, consent_to_contact), workflow fields (status, bucket, shortlist_reason,
  acknowledged_at) and a free-form `form_data` blob.
- **Intake API** — `GET/POST /api/v1/scholarship/applications/` (list own + submit) and
  `GET /api/v1/scholarship/applications/<id>/` (own detail). Submit resolves the active open
  cohort, snapshots the SPM A-count from the linked `StudentProfile` (A+/A/A- all count), sends
  a trilingual acknowledgement email, and stamps `acknowledged_at`. Default-deny auth; anonymous
  users and the duplicate/closed-round cases are rejected (403/409).
- **Trilingual acknowledgement email** (EN/MS/TA) via the existing Gmail SMTP infra; best-effort
  send that never blocks recording the application.
- **RLS policy SQL** (`apps/scholarship/sql/rls_policies.sql`) — enables RLS deny-by-default on
  both new tables (Django service role bypasses; direct PostgREST access denied). Apply before
  first deploy, then confirm Security Advisor 0 errors.

### Tests
- 17 new tests (`apps/scholarship/tests/`): models + defaults + partial-unique constraint +
  A-count helper (test_models.py, 4); intake create/ack-email/snapshot/consent/duplicate/
  closed-round/anonymous/no-profile/list-own/detail/cross-user-404/auth (test_api.py, 13).
- Full backend suite: **1023 passed, 0 failures** (1006 existing + 17 new); SPM/STPM golden
  masters unchanged.

### Notes
- Backend only — the native application form (frontend) is Sprint 2.
- Comms via email + in-app for Phase 1; WhatsApp deferred to Phase 2.

## [Unreleased] — Admin CSV Full Field Set (2026-05-02)

### Changed
- **Partner admin CSV export expanded from 7 columns to 27** (`/api/v1/admin/students/export/`). Now carries every field admins see in the dashboard detail view: identity (Name, IC, Angka Giliran, Email, Phone, School), demographics (Gender, Nationality), address (Address, Postal Code, City, State), eligibility context (Family Income, Siblings, Colorblind, Disability), academic (Exam Type, SPM Grades, STPM Grades, STPM CGPA, MUET Band), preferences (Financial Pressure, Travel Willingness), attribution (Referral Source, Referred By Org), and timestamps (Date Joined, Last Sign-In).
- `_fetch_auth_emails` → `_fetch_auth_data`: now fetches `last_sign_in_at` alongside `email` from `auth.users` in the same query.
- Export queryset now uses `select_related('referred_by_org')` to avoid N+1 lookups for the org-name column.

### Added
- **`Email` and `Last Sign-In` columns** joined from Supabase Auth's `auth.users` by `supabase_user_id`. Anonymous-only users (no email or phone) appear as blank in those columns; everyone else has them populated.
- JSON fields (SPM Grades, STPM Grades) are compactly stringified; empty `{}` renders as blank.
- Booleans render as `Yes`/`No` for human readability.

### Tests
- 5 tests in `apps/courses/tests/test_admin_export.py`: full 27-column header, full SPM profile rendering, STPM-specific columns, ghost-row blank rendering, auth-query-failure fallback.

---

## [2.0-rc] — 2026-03-20

### Added
- **OpenAI GPT-4o Mini fallback** for AI report generation when all Gemini models fail.
- **GCP cost monitoring**: RM50/month budget alert, BigQuery billing export.

---

## [Unreleased] — Auth Flow Canonical Refactor (2026-03-20)

### Changed
- **AuthProvider is single routing authority**: `status` + `profile` live in React context. Routing reads AuthProvider, never localStorage directly.
- **localStorage is write-only cache**: AuthProvider fetches from API, writes to localStorage as cache. `profile-restore.ts` deleted.
- **Callback page simplified**: Just establishes session, delegates all routing to AuthProvider status machine.
- **AuthGateModal reads context**: No more standalone `getProfile()` calls — reads `status`/`profile` from AuthProvider.
- **useOnboardingGuard reads AuthProvider**: Guards use AuthProvider state with loading support, not localStorage.
- **IC page guard reads status from AuthProvider**: Redirects if anonymous or already has NRIC.
- **STPM fields added to StudentProfile TS type**: Cached in AuthProvider alongside SPM fields.
- **Dashboard ranked results flattened to single list**: Removed dual-list display.

### Fixed
- **Rules of Hooks crash**: Moved `pendingProfileRedirect` useEffect before early return.
- **Onboarding redirect loop**: Resolved empty profile creation causing infinite redirects.
- **OAuth amnesia**: Stopped premature profile creation; fixed `signInWithGoogle` vs `linkIdentity` for login.
- **IC format**: Hyphens inserted before API call; loading race condition fixed.

### Removed
- `profile-restore.ts` — AuthProvider handles caching.
- TD-003 — auth flow refactored, localStorage no longer routing authority.

### Docs
- Comprehensive auth/onboarding flow documentation (`docs/auth-onboarding-flow.md`).
- Sprint retrospective, decisions, lessons.

### Tests
- 966 backend tests, 17 frontend, 0 failures.

---

## [Unreleased] — W14+W21 Ranking Sprint (2026-03-20)

### Added
- **W14**: 5-level STPM sort tiebreaking — score → uni tier → min_cgpa → difficulty → name.
- **W21**: `TRACK_FIELD_MAP` — matric:sains + stpm:sains → health + agriculture.
- 8 new tests.

---

## [Unreleased] — NRIC Hard Gate Sprint (2026-03-20)

### Added
- **Anonymous sign-in**: Auto-sign-in anonymously on first visit via Supabase; `isAnonymous` flag in AuthProvider.
- **linkIdentity helpers**: For upgrading anonymous sessions to Google-linked accounts.
- **NRIC hard gate middleware**: Blocks protected endpoints without NRIC — returns 403 `nric_required`.
- **Auth gate rewrite**: NRIC-first identity flow with `linkIdentity()`, replaces login page with redirect.
- **403 handler**: Frontend auto-shows auth gate on `nric_required` response.
- **Header updates**: Different UI for anonymous vs identified users.
- **IC page guard**: Redirect if anonymous or already has NRIC.
- 18 new integration tests for NRIC hard gate flow.

### Changed
- `isAuthenticated` now means has-NRIC; `hasSession` added as separate flag.
- Removed `get_or_create` from protected views — profiles must exist via NRIC claim.
- `is_anonymous` extracted from JWT in auth middleware.
- Course display limit unified to 9; explore filters sorted alphabetically.

---

## [Unreleased] — W7 FIELD_KEY_MAP Sprint (2026-03-20)

### Added
- 7 new `field_key` → signal mappings in `FIELD_KEY_MAP`.
- Search filter alphabetical sort.
- 8 new tests.

---

## [Unreleased] — Ranking Improvements Sprint (2026-03-19)

### Changed
- **W4**: 73 PISMP course tags backfilled for ranking accuracy.
- **W11**: STPM pre-quiz RIASEC signal derived from subjects (no quiz needed).
- Ranking audit doc added.
- W16 resolved.

### Fixed
- localStorage restoration from Supabase on login.
- Frontend boolean conversion — stopped converting booleans to Ya/Tidak before API calls.
- localStorage migration for legacy Ya/Tidak strings.

### Tests
- 40 new tests.

---

## [Unreleased] — i18n Sprint 2: Admin Pages (2026-03-19)

### Changed
- **All 7 admin pages internationalised**: 118 keys × 3 languages (EN/MS/TA).
- Zero hardcoded admin strings remaining.

---

## [Unreleased] — i18n & Bug Fixes Sprint (2026-03-19)

### Changed
- **BooleanField conversion**: `colorblind`/`disability` CharField → BooleanField (fixes dashboard 400 bug). Migration 0046.
- **Error mapping layer**: `ERROR_MAP` + `PATTERN_MAP` for i18n error translation.
- **Trilingual email verification**: EN/MS/TA templates.
- **Dynamic HTML lang attribute**: Set from locale.
- **Translated aria-labels**: Accessibility i18n.

### Fixed
- Dashboard 400 error from boolean field type mismatch.
- Hardcoded strings in auth callback, quiz, report, and IC onboarding pages replaced with `t()` calls.
- Stats display, login button, and incomplete badge UI fixes.

### Tests
- 4 new tests.

---

## [Unreleased] — STPM Quiz Sprint 5: Deploy & Validate (2026-03-18)

### Changed
- **Migrations 0042-0045 applied to Supabase**: MUET float type, postal_code/city/address profile fields, RIASEC/difficulty/efficacy enrichment fields, is_active flag — all applied via raw SQL (bypassing InconsistentMigrationHistory blocker).
- **RIASEC enrichment applied to production**: 867 STPM courses + 28 field taxonomy entries enriched with riasec_type, difficulty_level, efficacy_domain via `enrich_stpm_riasec --apply`.
- **Backend deployed**: `halatuju-api-00131-p7l` on Cloud Run asia-southeast1.
- **Frontend deployed**: `halatuju-web-00160-rql` on Cloud Run asia-southeast1.

### Verified
- Supabase Security Advisor: 0 new issues after schema changes.
- Smoke tests: STPM quiz questions (branch routing), quiz submit (signal accumulation), eligibility check (545 courses for strong science student), all passing on production.

## [Unreleased] — STPM Quiz Engine Sprint 4: Frontend (2026-03-18)

### Added
- **STPM quiz page** (`halatuju-web/src/app/stpm/quiz/page.tsx`): Branching card-based quiz UI with dynamic Q3/Q4 resolution after Q2. Reads subjects from localStorage, routes Science/Arts/Mixed branches via backend API, auto-advances between questions.
- **STPM quiz API client** (`halatuju-web/src/lib/api.ts`): 3 functions — `getStpmQuizQuestions`, `resolveStpmQuizQ3Q4`, `submitStpmQuiz` — plus `StpmResultFraming` type for ranking response framing.
- **Subject-to-API key mapping** (`halatuju-web/src/lib/subjects.ts`): `STPM_SUBJECT_TO_API_KEY` maps 20 frontend subject IDs (e.g. `PHYSICS`) to backend keys (e.g. `physics`).
- **STPM quiz storage keys** (`halatuju-web/src/lib/storage.ts`): `KEY_STPM_QUIZ_SIGNALS`, `KEY_STPM_QUIZ_BRANCH` for persisting quiz results across sessions.
- **Trilingual STPM quiz strings** (`messages/en.json`, `ms.json`, `ta.json`): Loading, error, skip, take/retake quiz labels.

### Changed
- **Dashboard shows quiz-informed framing** (`halatuju-web/src/app/dashboard/page.tsx`): When STPM quiz signals exist, dashboard header shows result framing (confirmatory/guided/discovery heading + subtitle). Quiz CTA routes to `/stpm/quiz`. Retake button shown after quiz completion.
- **Dashboard reads STPM quiz signals** (`dashboard/page.tsx`): STPM ranking now uses `KEY_STPM_QUIZ_SIGNALS` (falling back to `KEY_QUIZ_SIGNALS`), and displays framing from ranking API response.

## [Unreleased] — STPM Quiz Engine Sprint 3: Ranking Integration (2026-03-18)

### Changed
- **STPM ranking formula rewritten** (`stpm_ranking.py`): 7-component scoring — BASE(50) + CGPA_MARGIN(+20) + FIELD_MATCH(+12) + RIASEC_ALIGNMENT(+8) + EFFICACY_MODIFIER(+4/-2) + GOAL_ALIGNMENT(+4) - INTERVIEW(-3) - RESILIENCE_DISCOUNT(0/-3). Max score 98.
- **Eligibility output enriched** (`stpm_engine.py`): Eligible course dicts now include `riasec_type`, `difficulty_level`, `efficacy_domain` for ranking engine consumption
- **Ranking API returns framing** (`views.py`): `POST /stpm/ranking/` now includes `framing` object with mode (confirmatory/guided/discovery), heading, and subtitle from Q1 crystallisation signal

### Added
- **Result framing logic**: 3 modes based on Q1 — confirmatory ("Your profile aligns with..."), guided ("Based on your interests..."), discovery ("Here are fields worth exploring")
- **STPM field_key → field_interest reverse mapping** (`_FK_TO_INTEREST`): Maps Q3 sub-field signals back to Q2 broad interest for secondary field matching

### Tests
- 58 ranking tests (was 11): CGPA margin (5), field match (9), RIASEC alignment (8), efficacy modifier (6), goal alignment (7), resilience discount (7), interview (2), full integration (4), framing (5), ranked results (5)
- 881 backend tests, 0 failures
- Golden masters: SPM=5319, STPM=2026 (unchanged)

## [Unreleased] — STPM Quiz Engine Sprint 2: Data Enrichment (2026-03-18)

### Added
- **3 new fields on StpmCourse**: `riasec_type` (R/I/A/S/E/C), `difficulty_level` (low/moderate/high), `efficacy_domain` (quantitative/scientific/verbal/practical) — for quiz-informed ranking in Sprint 3
- **`riasec_primary` field on FieldTaxonomy**: maps each field to its primary Holland RIASEC type
- **`enrich_stpm_riasec` management command**: deterministic classifier using field_key → RIASEC/difficulty/efficacy mappings from the design doc. Covers 37 field_keys (all except `umum` catch-all). Dry-run by default, `--apply` to save.
- **Migration 0044**: `add_riasec_difficulty_efficacy_fields`

### Tests
- 40 new enrichment tests (mapping completeness, correctness, consistency, DB fields, management command)
- 829 backend tests, 0 failures
- Golden masters: SPM=5319, STPM=2026 (unchanged)

## [Unreleased] — STPM Quiz Engine Sprint 1: Foundation (2026-03-18)

### Added
- **STPM quiz data** (`stpm_quiz_data.py`): ~35 questions × 3 languages (EN/BM/TA) with subject-seeded branching design grounded in Holland's RIASEC, SCCT, SDT, and Super's Career Development Theory
- **STPM quiz engine** (`stpm_quiz_engine.py`): RIASEC seed calculation from STPM subjects, branch routing (Science/Arts/Mixed), grade-adaptive Q4 resolution, cross-domain Q5 stream filtering, signal accumulation into 9-category taxonomy
- **3 new API endpoints**: `GET /stpm/quiz/questions/` (returns branch-specific questions), `POST /stpm/quiz/resolve/` (resolves Q3+Q4 after Q2 answer), `POST /stpm/quiz/submit/` (processes answers → signals)
- **STPM signal taxonomy**: 9 categories (riasec_seed, field_interest, field_key, cross_domain, efficacy, resilience, motivation, career_goal, context)
- **Cross-domain asymmetry enforcement**: Science students see 6 Q5 options; arts students see only achievable options (no science-prerequisite programmes)
- **Grade-adaptive confidence check**: Q4 uses actual STPM grades — weak grades (≤B-) trigger honest framing, strong grades trigger confirmatory framing

### Tests
- 102 new STPM quiz tests (56 engine + 22 data + 24 API)
- 775 backend tests, 0 failures
- Golden masters: SPM=5319, STPM=2026 (unchanged)

## [Unreleased] — STPM Requirements Pipeline Rebuild Sprint 3: Validator + Workflow (2026-03-17)

### Added
- **Validator tool** (`Settings/_tools/stpm_requirements/validate_stpm_requirements.py`): 6 automated quality checks — completeness, subject key validity (validates against canonical key sets), grade validity, count sanity, cross-reference with source CSV, sample audit against raw HTML
- **Reusable workflow** (`Settings/_workflows/stpm-requirements-update.md`): Annual STPM requirements refresh SOP covering all 5 pipeline stages with checkpoints and failure modes

### Fixed
- Validator subject key check now catches invalid keys beyond `UNKNOWN:` prefix (validates against `VALID_STPM_KEYS`/`VALID_SPM_KEYS` sets)
- Validator handles `stpm_named_subjects` as list of dicts (real data format), not just list of strings
- Validator CSV cross-reference gracefully handles missing files instead of crashing
- Validator sample audit uses isolated PRNG (`random.Random(42)`) instead of global seed

### Tests
- 49 new validator tests (248 total pipeline tool tests)
- 590 backend tests, 17 frontend tests, 0 failures
- Golden masters: SPM=5319, STPM=2103

## [Unreleased] — STPM Requirements Pipeline Rebuild Sprint 2: Backend Integration (2026-03-16)

### Added
- **Fixture converter** (`Settings/_tools/stpm_requirements/stpm_json_to_fixture.py`): Converts structured JSON → Django fixture format with null-safety for non-nullable model fields
- **4 new StpmRequirement boolean fields**: `req_male`, `req_female`, `single`, `no_disability` (migration 0031)
- **List-aware subject group engine**: `check_stpm_subject_group()` and `check_spm_prerequisites()` now handle both single dict (legacy) and list of dicts (new pipeline) formats with AND semantics
- **Exclusion list support**: SPM prerequisites engine checks `exclude` lists — student needs min_count subjects at min_grade from any subject NOT in the exclude list
- **Demographic eligibility checks**: `check_stpm_eligibility()` now enforces `req_male`, `req_female`, `no_disability`
- **API fields**: STPM course detail response includes `req_male`, `req_female`, `single`, `no_disability`
- **SpecialConditions component**: Renders gender, marital, disability conditions with colour-coded indicators
- **i18n keys**: `maleOnly`, `femaleOnly`, `unmarriedOnly`, `noDisability` in EN/MS/TA
- **Search page fix**: SPM grades merged from `KEY_GRADES` into profile for eligibility checks
- **Dashboard fix**: Report existence synced with DB on fresh devices

### Changed
- **STPM golden master**: 1811 → 2103 (richer requirement data = more eligible matches)
- **stpm_requirements.json fixture**: Regenerated from new pipeline (1,113 courses)

### Tests
- 32 new fixture converter tests (199 total pipeline tool tests)
- 590 backend tests, 17 frontend tests, 0 failures
- Golden masters: SPM=5319, STPM=2103

## [Unreleased] — STPM Requirements Pipeline Rebuild Sprint 1: Parser Rewrite (2026-03-16)

### Added
- **Subject key registry** (`Settings/_tools/stpm_requirements/subject_keys.py`): 135+ subject mappings (25 STPM + 110 SPM), slash-combo handling, `UNKNOWN:` fallback
- **HTML→JSON parser** (`Settings/_tools/stpm_requirements/parse_stpm_html.py`): Per-`<li>` block parsing via BeautifulSoup, 11 block types, multi-tier STPM groups, exclusion lists
- **Pipeline test suite**: 167 tests (subject keys + parser + integration)
- Parsed 1,680 courses (1,003 science + 677 arts): 1.4% warning rate, 0 unknown subjects

## [Unreleased] — MASCO Career Mappings Sprint B: AI Mapping Pipeline (2026-03-16)

### Added
- **FIELD_KEY_TO_MASCO mapping**: Deterministic mapping from 31 field_keys to MASCO 2-digit occupation groups for pre-filtering
- **filter_masco_by_field_key**: Filters 4,854 MASCO jobs to ~200-400 relevant jobs per field
- **map_course_careers command**: AI-assisted career mapping pipeline
  - Generate mode (`--output`): iterates unmapped courses, calls Gemini, outputs review CSV
  - Apply mode (`--apply`): reads reviewed CSV, writes M2M links to DB
  - Supports both SPM (`--source-type`) and STPM (`--stpm`) courses
  - Rate limiting (`--delay`), batch size (`--limit`), Gemini model cascade

### Tests
- 12 new tests (5 mapping, 3 filter, 2 generate, 2 apply)
- Total: 568 backend + 17 frontend, 0 failures
- Golden masters: SPM=5319, STPM=1811 (unchanged)

## [Unreleased] — MASCO Career Mappings Sprint A: Backend Foundation (2026-03-16)

### Added
- **Full MASCO 2020 dataset**: `load_masco_full` management command loads 4,854 occupations from CSV with auto-generated eMASCO URLs (`https://emasco.mohr.gov.my/masco/{code}`)
- **StpmCourse.career_occupations**: New M2M field mirrors SPM `Course` model — STPM degree courses can now link to MASCO job codes
- **STPM detail API**: Now returns `career_occupations` array (same shape as SPM detail)
- **CareerPathways component**: Extracted from SPM detail page into shared component used by both SPM and STPM course detail pages; jobs with `emasco_url` are clickable, without are plain tags; hidden when empty

### Tests
- 10 new tests (4 data loading, 3 model, 3 API)
- Total: 556 backend + 17 frontend, 0 failures
- Golden masters: SPM=5319, STPM=1811 (unchanged — no eligibility/ranking changes)

## [Unreleased] — Field Taxonomy Sprint 5: Cleanup & Legacy Removal (2026-03-16)

### Changed
- **`field_key` non-nullable** — both `Course` and `StpmCourse` now require `field_key` (was nullable); all 1,503 courses already populated
- **Frontend field fallbacks** — all `course.field` references replaced with `getFieldName(course.field_key)` from taxonomy hook (detail pages, saved page, CourseCard)
- **Search API** — removed `?field=` fallback from frontend; only `field_key` sent

### Removed
- `frontend_label` column from `Course` model (migration 0028)
- `category` column from `StpmCourse` model (migration 0029)
- `frontend_label` from `CourseSerializer` output and TypeScript `Course` type
- `field` from `SearchParams` TypeScript type

### Tests
- Total: 530 backend + 17 frontend, 0 failures
- Golden masters: SPM=5319, STPM=1811 (unchanged)

## [Unreleased] — Field Taxonomy Sprint 4: Frontend Integration (2026-03-16)

### Changed
- **CourseCard images** — replaced 150-line `getImageSlug()` keyword matcher with taxonomy-driven lookup via `field_key` → `image_slug`; images now resolve from `FieldTaxonomy.image_slug` instead of hardcoded keyword rules
- **Search field filter** — dropdown now uses `/api/v1/fields/` taxonomy API with trilingual labels (EN/MS/TA) and filters by `field_key` instead of raw `frontend_label`/`field` strings
- **Search API** — `?field_key=` parameter now preferred over `?field=` for filtering; `field_keys` list added to search filter response
- **Dashboard** — STPM course cards now pass `field_key` through to CourseCard for correct image resolution

### Added
- `useFieldTaxonomy` hook — fetches taxonomy once, caches module-level, provides `getImageUrl(fieldKey)` and `getFieldName(fieldKey)` for trilingual field labels
- `fetchFieldTaxonomy()` API client function for `/api/v1/fields/`
- `field_key` added to `EligibleCourse`, `SearchCourse`, `StpmEligibleCourse` TypeScript types
- 2 new backend tests: `field_key` filter, `field_keys` in search filters

### Tests
- Total: 546 backend + 17 frontend, 0 failures

## [Unreleased] — Field Taxonomy Sprint 3: Ranking Engine field_key Integration (2026-03-16)

### Changed
- **SPM ranking** — field interest matching now uses `field_key` (taxonomy key) instead of `frontend_label` strings; `FIELD_LABEL_MAP` replaced by `FIELD_KEY_MAP`
- **STPM ranking** — keyword-based `_match_field_interest()` replaced with `field_key` lookup against shared `FIELD_KEY_MAP` (DRY); removed 48-line `COURSE_FIELD_MAP`
- **`field_health` signal** — now correctly maps to health fields (`perubatan`, `farmasi`, `sains-hayat`) instead of agriculture (was a bug)
- **`field_key` in eligibility results** — added to both SPM and STPM eligibility response dicts so ranking engines can use it

### Tests
- Updated 7 field interest tests (5 SPM, 2 STPM) from `frontend_label`/keyword to `field_key`
- Added 3 new tests: double-match bonus, no-field_key edge case (SPM + STPM)
- Total: 544 tests, 0 failures

---

## [Unreleased] — Field Taxonomy Sprint 2: STPM Classification + API Integration (2026-03-16)

### Added
- **STPM deterministic classifier** — `classify_stpm_course()` maps `category + field + course_name` to taxonomy key; handles ~170 category values across 29 taxonomy keys
- **`_classify_spm_matching()` helper** — sub-classifies 10 SPM-matching STPM categories using `course_name` (STPM field == category aggregate, not specific sub-discipline)
- **`FieldTaxonomySerializer`** — recursive serializer with `children` field for nested group→leaf structure
- **`GET /api/v1/fields/`** — returns 10 field groups with nested children (37 leaf fields)
- **`?field_key=` filter** — backwards-compatible query parameter on search endpoints (alongside existing `?field=`)
- **`field_key` in API responses** — added to SPM search, STPM search, and STPM course detail
- **`classify_stpm_fields` management command** — dry-run/save modes, distribution summary, safety checks
- **57 new STPM classifier tests** + 4 API endpoint tests (total 118 in test_field_taxonomy.py)
- **SQL reference script** — `scripts/stpm_backfill_field_key.sql` for documentation

### Database
- Backfilled all 1,113/1,113 STPM courses with `field_key_id` (0 unclassified)
- Distribution: 29 of 37 taxonomy keys used (top: pertanian=100, pendidikan=97, umum=77, sains-hayat=65, it-perisian=65)

---

## [Unreleased] — Field Taxonomy Sprint 1: Model + Migration + SPM Backfill (2026-03-16)

### Added
- **FieldTaxonomy model** — canonical table with 37 leaf fields + 10 parent groups, trilingual names (EN/MS/TA), image slugs, parent-child hierarchy
- **field_key FK** on `Course` and `StpmCourse` — nullable foreign key to FieldTaxonomy (will become non-nullable in Sprint 5)
- **Data migration** — populates all 47 taxonomy entries with trilingual names and sort orders
- **Deterministic classifier** — `classify_course()` maps `frontend_label + field + course_name` to taxonomy key; handles 16 production frontend_label variants
- **Backfill management command** — `backfill_spm_field_key` with `--save` flag (dry-run by default), safety check for PostgreSQL
- **Admin registration** — FieldTaxonomyAdmin with list/filter/search; CourseAdmin updated with field_key display/filter
- **55 new tests** — 7 model integrity tests + 48 classifier tests (including 24 production frontend_label tests)

### Database
- Created `field_taxonomy` table (47 entries) with RLS enabled (public read)
- Added `field_key_id` column to `courses` and `stpm_courses`
- Backfilled all 390 SPM courses (0 unmapped)
- Recorded Django migrations 0025 + 0026

---

## [Unreleased] — Special Conditions, Report Guard & Search Fix (2026-03-15)

### Added
- **Special Conditions expansion** — SpecialConditions component now shows gender restrictions (male/female only), unmarried requirement, and no-disability condition with colour-coded dots (blue/pink/purple/red)
- **i18n keys** — `maleOnly`, `femaleOnly`, `unmarriedOnly`, `noDisability` in EN/MS/TA
- **Contact form** — Supabase-backed contact form replaces raw email on contact page (name, email/phone, category, message)
- **Onboarding guard** — `useOnboardingGuard` hook protects dashboard/saved/profile/outcomes from users without grades
- **IC gate** — post-login IC + name collection page for users without NRIC
- **Smart auth routing** — Google OAuth and OTP login check NRIC → grades → route appropriately
- **Profile redesign** — two-column layout, amber incomplete indicators, email/phone/angka giliran fields, Yes/No toggles

### Fixed
- **Search "Eligible only" broken** — grades stored in `KEY_GRADES` but search page only read `KEY_PROFILE`; now merges both (root cause of 0 results)
- **"Generate Report" shown alongside "Read Report"** — syncs `reportGenerated` state from DB when localStorage flag missing (cross-device/cache clear)
- **Profile i18n bug** — `onboarding.name` key replaced with `profile.name` in all 3 languages
- **Mobile nav auth gate** — uses `link.authReason` instead of hardcoded `'profile'`

### Database
- Set `single = true` for 4 courses (IKBN-CET-005, UZ0520001, UZ0345001, UZ0721001) — recovered from deleted `details.csv`
- Created `contact_submissions` table with RLS (anon insert, service_role manage)

---

## [Unreleased] — Tech Debt Quick Wins 2 (2026-03-15)

### Added
- **Trilingual pre-U descriptions** — i18n keys (EN/MS/TA) for all 6 pre-U course headlines and descriptions in message files, replacing empty DB fields
- **Gemini API rate limiting** — max 3 reports per user per 24 hours via Django cache, returns 429 when exceeded (TD-009)
- **CourseListView pagination** — optional `?page=1&page_size=50` query params, backwards-compatible (TD-046)
- **Fallback description template** — `courses.descriptionFallback` i18n key replaces hardcoded fallback strings in course detail page

### Fixed
- **Engine field naming** — `three_m_only` used directly instead of runtime column rename hack in `apps.py` (TD-023)
- **Bug 4** — reclassified as "not a bug" (pre-U entry requirements are genuinely broad, not generic)
- **Bug 5** — pre-U description content added via i18n system (proper trilingual approach)

### Changed
- **Dependency pins relaxed** — `sentry-sdk>=1.39,<3.0` (was `<2.0`), `numpy>=1.24,<3.0` (was `<2.0`) (TD-039, TD-040)
- **Tech debt doc** — updated 10 items to reflect resolved status (5 from earlier sprints not marked, 5 new). Now 48/52 resolved.

---

## [Unreleased] — Bug Fixes & Auth Gating (2026-03-15)

### Added
- **Centralised localStorage keys** — `storage.ts` with 19 key constants + `clearAll()` helper, all 15 pages updated (TD-014 resolved)
- **Auth gating** — My Profile nav link, Load More buttons (dashboard SPM/STPM/ranked + search), and profile page now show sign-up modal for anon users
- **Saved courses UX** — institution name + course ID on saved cards, unified status toggle with correct state transitions (un-toggle "Got Offer" falls back to "Applied")
- **Error boundary pages** — `error.tsx`, `loading.tsx`, `not-found.tsx` for graceful error handling
- **Backend** — `institution_name` returned for both SPM and STPM saved courses
- **i18n** — `profileReason`, `loadmoreReason` auth gate messages in EN/MS/TA; error/loading/not-found page keys

### Changed
- About page tagline: removed "No sign-ups" (all 3 languages) since sign-up is now required for key features

---

## [Unreleased] — Saved Courses Sprint 2 (2026-03-15)

### Added
- **`useSavedCourses()` shared hook** — single source of truth for save state, auth gating, optimistic updates, toast feedback, and resume-after-login across all pages
- **Toast notification system** — `ToastProvider` + `useToast()` hook with success/error variants, auto-dismiss after 3s, slide-in animation
- **Search page save** — bookmark icon on search results now reflects actual saved state and toggles correctly
- **Detail page visual states** — save button shows green "Saved" when saved, red "Remove from Saved" on hover, blue "Save This Course" when not saved (both SPM and STPM detail pages)
- **Saved page SPM/STPM tabs** — tabbed interface with counts, correct detail page links per type (`/course/` for SPM, `/stpm/` for STPM)
- **Translation keys** — `courseDetail.saved`, `saved.noSpm`, `saved.noStpm` in EN/MS/TA

### Changed
- **Dashboard** — replaced ~50 lines of inline save logic with `useSavedCourses()` hook call
- **SPM detail page** — replaced broken `handleSave` (no auth, no token) with hook
- **STPM detail page** — same fix as SPM detail page

### Removed
- Inline `savedIds` state, `handleToggleSave`, `handleSaveOrGate` from dashboard (moved to hook)
- Direct `saveCourse`/`unsaveCourse` imports from detail pages (now via hook)

---

## [Unreleased] — Saved Courses Sprint 1 (2026-03-15)

### Added
- **STPM course saving** — SavedCourse model supports both SPM and STPM courses via dual nullable FKs with DB check constraint
- **Qualification filter** — `GET /saved-courses/?qualification=SPM|STPM` filters saved courses by type
- **Auto-detect STPM** — POST with `stpm-*` prefix or explicit `course_type` saves to correct FK
- **`course_type` in response** — GET /saved-courses/ returns `course_type: 'spm' | 'stpm'` per entry
- **Frontend types** — `SavedCourseWithStatus.course_type`, `saveCourse` accepts optional `courseType`, `getSavedCourses` accepts optional `qualification` filter

### Changed
- **SavedCourse model** — `course` FK now nullable, `stpm_course` FK added, `unique_together` replaced with partial unique indexes
- **SavedCourseDetailView** — DELETE/PATCH check both FKs when looking up saved course

### Database
- Supabase migration: `stpm_course_id` column, nullable `course_id`, check constraint, partial unique indexes

### Tests
- Saved courses tests expanded from 3 to 17 (SPM CRUD, STPM CRUD, qualification filter, idempotent save, check constraint enforcement)
- Full suite: 425 pass, 0 fail, 0 skip

---

## [Unreleased] — External Links & MOHE Sprint (2026-03-14)

### Added
- **MOHE ePanduan integration** — `mohe_url` field on StpmCourse, auto-generated URL pattern for 1,113 STPM courses, validated with Selenium-based page content checker
- **MOHE scraper + sync** — `scrape_mohe_courses` and `sync_stpm_mohe` management commands for auditing MOHE catalogue against DB
- **STPM URL validator** — Selenium-based validator (not HTTP status — MOHE always returns 200). Checks rendered page content for "daripada 0 carian" to detect dead links
- **Course-level "More Info" pill** — About section on course detail pages now shows a contextual "More Info" link: MOHE ePanduan for UA/poly/kkom, polycc for poly (TBD), MOE sites for matric/form 6/PISMP, institution hyperlink for TVET
- **Institution website links** — Institution cards now link to the institution's own website URL instead of the course-level hyperlink
- **STPM institution cards** — Rich institution card on STPM detail page with acronym, type, category, state, and website link (looked up from Institution table)
- **ILJTM/ILKBS filter split** — Search API resolves `tvet` source_type into `iljtm`/`ilkbs` using `course_pathway_map`; filter dropdown shows them separately
- **IPG campus URLs** — 27 IPG campuses populated with correct website URLs
- **Annual STPM data refresh procedure** — Documented in `docs/stpm-annual-refresh.md`

### Changed
- **Search limit** — Backend limit bumped from 100 to 10000 for full result sets
- **Merit colour logic** — STPM mata gred courses use inverted colours (low = green/good); arts stream ≤12 green, science ≤18 green
- **Pre-U course detail** — Department and WBL fields hidden for pre-U courses (not meaningful)
- **"More Info" pill style** — STPM detail page changed from "View on ePanduan (MOHE)" text link to compact pill button

### Fixed
- **1 dead MOHE URL** — UJ6521004 cleared after Selenium validation confirmed "daripada 0 carian"
- **Kolej Komuniti URL** — 1 missing institution URL fixed
- **Search pathway_type** — Search results now include `pathway_type` and `qualification` fields for correct badge rendering

---

## [Unreleased] — Security, API Consistency & Refactoring Sprints (2026-03-14)

### Changed
- **Default permissions flipped** — `DEFAULT_PERMISSION_CLASSES` changed from `AllowAny` to `SupabaseIsAuthenticated` (TD-012). 16 public views explicitly marked.
- **401 for unauthenticated** — Added `SupabaseAuthentication` DRF class; unauthenticated requests now return 401 with `WWW-Authenticate: Bearer` instead of 403 (TD-011)
- **DRF status constants** — All raw integer status codes replaced with DRF constants (TD-004)
- **EligibilityCheckView refactored** — Extracted 5 pure functions into `eligibility_service.py`, view reduced from 310 → 100 lines (TD-045)
- **Double DataFrame iteration eliminated** — `_apply_pismp_dedup()` no longer iterates twice (TD-044)

### Fixed
- **ProfileUpdateSerializer** — PUT/PATCH profile now validates via serializer instead of accepting arbitrary fields (TD-008)
- **SECRET_KEY guard** — Production raises ValueError if SECRET_KEY equals insecure dev default (TD-036)
- **CORS wildcard guard** — Production raises ValueError if CORS_ALLOWED_ORIGINS=* (TD-038)

---

## [Unreleased] — Tech Debt Sprint 4 (2026-03-14)

### Fixed
- **TD-001: STPM SPM prerequisite check** — Added `spm_pass_bi` and `spm_pass_math` to `SIMPLE_CHECKS` in `stpm_engine.py`. Zero programmes currently set these flags, so no eligibility results changed. STPM golden master baseline unchanged at 1,811.
- **TD-050: Quiz language bug** — Quiz page now reads locale from i18n context (`useT()`) instead of non-existent `halatuju_lang` localStorage key. Quiz loads in the user's selected language (EN/BM/TA).
- **TD-007: Bare except in engine.py** — `check_merit_probability()` now catches `(ValueError, TypeError)` instead of bare `except:`.
- **TD-020: Duplicate serializer key** — Removed duplicate `credit_stv` entry in `SPECIAL_FIELDS` dict.
- **TD-018: Duplicate import** — Removed redundant `from django.db.models import Count, Subquery, OuterRef` inside `EligibilityCheckView.post()`.
- **TD-019: Inline imports** — Moved `json` and `defaultdict` imports from inline method bodies to top of `views.py`.

---

## [Unreleased] — Hotfix Sprint (2026-03-14)

### Added
- **STPM programme institution enrichment** — Detail API now looks up university in `institutions` table, returning acronym, type, category, state, URL; frontend renders rich institution card matching SPM style
- **i18n: Max Grade Points** — New key `courseDetail.maxGradePoints` in EN ("Max Grade Points"), BM ("Mata Gred Maksimum"), TA ("அதிகபட்ச தர புள்ளிகள்")

- **STPM sidebar redesign** — Entry Requirements consolidated into unified card matching SPM route: General Requirements (checkmarks), STPM Requirements (key-value table), STPM Subjects (blue pills), SPM Prerequisites (green pills), Special Conditions (separate card with warning icon). STPM Subjects and SPM Prerequisites moved from left column to sidebar.

### Changed
- **Search: ILJTM/ILKBS resolution** — Search API now resolves `tvet` → `iljtm`/`ilkbs` using `course_pathway_map`; filter options show ILJTM and ILKBS separately instead of hidden `tvet`
- **Search: course limit removed** — Backend no longer caps at 100 courses; explore page shows all results
- **Course detail: merit label** — "Avg. Mata Gred" → "Max Grade Points" (i18n) for `stpm_mata_gred` merit type
- **Course detail: merit colour logic** — Arts stream: ≤12 green, 13-18 amber, >18 red; Science stream: ≤18 green, >18 amber

### Fixed
- **ILJTM/ILKBS badges on explore page** — CourseCard now receives `pathway_type` from search API, showing correct ILJTM/ILKBS badges instead of undefined
- **DB: Arts merit cutoff** — `stpm-sains-sosial` cutoff updated from 18 → 12 in Supabase

---

## [Unreleased] — UI Polish & Consistency Sprint

### Added
- **Rich institution cards for pre-U courses** — STPM course detail (`/course/stpm-*`) now shows schools with PPD, subjects (colour-coded badges), phone numbers from frontend JSON data; matric courses show colleges with tracks, phone, website
- **Subject Key legend** — STPM course detail pages include a sidebar legend explaining subject abbreviations (BT, L.ENG, etc.)
- **STPM programme detail redesign** — `/stpm/[id]` now matches SPM course detail format: header with level+stream badges, About section with AI description, Quick Facts sidebar (field, category, merit), institution card, save/actions buttons
- **STPM API enrichment** — Detail endpoint now returns `field`, `category`, `description`, `merit_score`

### Changed
- **Search filter labels standardised to Malay** — Universiti, IPGM, Politeknik, Kolej Komuniti, Kolej Matrikulasi, Tingkatan 6, ILJTM, ILKBS
- **TVET removed from search filter** — ILJTM and ILKBS appear separately; redundant "tvet" option hidden

### Fixed
- **Dashboard pathway pills** — matric/stpm pills now appear; university pill fixed (`'ua'` → `'university'` key)
- **Badge key case** — TYPE_LABELS/TYPE_COLORS changed from uppercase to lowercase keys to match API response
- **University ranking** — Added `'university'` key to PATHWAY_PRIORITY (was only `'ua'`)
- **Pathway priority** — Corrected order: asasi(8) > matric(7) > stpm(6) > university(5) > poly(4) > pismp(3) > kkom(2) > iljtm/ilkbs(1)
- **Institution name on SPM cards** — Dashboard course cards now show institution name, state, and count
- **DB state normalisation** — "Kuala Lumpur" → "WP Kuala Lumpur" (3 IPG campuses), "Labuan" → "WP Labuan" (1 matric college)
- **Level rename** — "Ijazah Sarjana Muda Pendidikan" → "Ijazah Sarjana Muda" (73 rows in Supabase)

## [Unreleased] — STPM Entrance (Sprints 1–5)

### Fixed (Sprint 5)
- **STPM grade scale** — Replaced E with D+(1.33), corrected C- from 2.00→1.67, kept E/G as legacy aliases in GRADE_ORDER for backward compatibility with parsed requirement data
- **Quiz signal localStorage key** — Dashboard STPM path read `halatuju_student_signals` (nonexistent) instead of `halatuju_quiz_signals`; quiz signals now reach STPM ranking correctly
- **STPM ranking field_interest format** — Fixed default value from `[]` to `{}` to match quiz engine's dict format

### Changed (Sprint 5)
- **STPM grade entry page redesign** — Stream selector (Science/Arts) as Section 1; 3 stream-filtered subject slots + 1 open elective; co-curriculum score input (0.00–4.00); overall CGPA = 90% academic + 10% co-curriculum; MUET as plain numbers; SPM prereqs split into 4 compulsory + 2 optional
- **Frontend CGPA points** — `lib/stpm.ts` updated to match backend (C-=1.67, D+=1.33, removed E)
- **SPM prereq constants** — Split `SPM_PREREQ_SUBJECTS` into `SPM_PREREQ_COMPULSORY` (4) + `SPM_PREREQ_OPTIONAL` (2)
- **i18n** — 9 new keys × 3 locales (stream, koko, formula labels)

### Added (Sprint 4)
- **STPM search API** — `GET /api/v1/stpm/search/` with text, university, stream filters + cursor pagination (20/page)
- **STPM programme detail API** — `GET /api/v1/stpm/programmes/<id>/` with human-readable subject labels, SPM prereqs, flags
- **STPM search page** — `/stpm/search` with debounced text input, dropdown filters, responsive card grid, load-more
- **STPM detail page** — `/stpm/[id]` with breadcrumb, stream badge, subject pills, quick facts sidebar, requirement flags
- **i18n** — 33 new `stpm.*` keys in EN/BM/TA for search and detail pages
- **Dashboard link** — "Browse All Programmes" button linking to STPM search

### Added (Sprint 3)
- **Supabase migration** — `stpm_courses` + `stpm_requirements` tables with RLS policies, 2,226 rows loaded
- **STPM ranking engine** — `stpm_ranking.py` (BASE=50, CGPA margin +20, field match +10, interview -3)
- **STPM ranking API** — `POST /api/v1/stpm/ranking/` endpoint
- **Frontend fit scores** — `rankStpmProgrammes()` API client, colour-coded badges (green ≥70, amber ≥55, grey <55)

### Added (Sprint 1)
- **StpmCourse & StpmRequirement models** — Django models for ~1,113 unique STPM degree programmes across ~20 public universities
- **STPM CSV data loader** — `load_stpm_data` management command loads science (1,003) + arts (677) CSVs with idempotent update_or_create
- **STPM eligibility engine** — `stpm_engine.py` with CGPA calculator, grade comparison, SPM prerequisite checks, STPM subject/group requirements, demographic filters
- **STPM eligibility API** — `POST /api/v1/stpm/eligibility/check/` endpoint accepting STPM grades, SPM grades, CGPA, MUET band
- **STPM golden master** — baseline 1811 across 5 test student profiles
- **Implementation plan** — `docs/plans/2026-03-12-stpm-entrance.md` (5 sprints, 22 tasks)

### Added (Sprint 2)
- **STPM subject definitions** — `lib/subjects.ts` constants (20 subjects, grade scale, MUET bands, SPM prereqs) aligned with backend engine keys
- **Frontend CGPA calculator** — `lib/stpm.ts` mirrors backend `stpm_engine.py` grade-point mapping
- **Exam type activation** — `/onboarding/exam-type` page now enables STPM selection (was "Coming Soon"), sets `halatuju_exam_type` in localStorage
- **STPM grade entry page** — `/onboarding/stpm-grades` single combined page with STPM subjects (PA compulsory + 4 optional), MUET band pills, auto-calculated CGPA, SPM prerequisites (6 subjects)
- **STPM API client** — `checkStpmEligibility()` in `lib/api.ts` with typed request/response interfaces
- **Dashboard STPM routing** — `dashboard/page.tsx` conditionally renders STPM programme cards or SPM course cards based on `exam_type`
- **Backend STPM profile fields** — `StudentProfile` gains `exam_type`, `stpm_grades`, `stpm_cgpa`, `muet_band`, `spm_prereq_grades` fields with profile sync + API support
- **i18n support** — 14 new translation keys across EN/MS/TA for STPM onboarding flow

### Stats
- Tests: 320 collected, 287 passing (1 new in Sprint 5, 12 in Sprint 4, 13 in Sprint 3, 6 in Sprint 2) | SPM golden master: 8283 | STPM golden master: 1811
- STPM programmes: 1,113 unique (from 1,680 CSV rows with 567 overlapping)

## [1.33.0] - 2026-03-12 — Unified Pre-U Backend & IPGM Integration

### Added
- **Backend Matric/STPM eligibility** — `pathways.py` port of all frontend eligibility logic (4 Matric tracks, 2 STPM bidangs, 32 tests)
- **Matric/STPM in API response** — eligible tracks returned in `eligible_courses` with merit labels, display fields, mata_gred
- **Unified pre-U ranking** — `calculate_matric_stpm_fit_score()` routes matric/stpm through prestige + academic + field preference + signal scoring (12 tests)
- **27 IPG campuses** — all Institut Pendidikan Guru campuses added as institutions, linked to 73 PISMP courses (1,971 offerings)
- **Pathway-based sort priority** — `PATHWAY_PRIORITY` dict replaces `SOURCE_TYPE_PRIORITY` for correct Asasi > Matric > STPM > UA > Poly > PISMP > KKOM ordering

### Fixed
- **PISMP ranking** — credential priority changed from 4 to 2.5; pathway priority from 5 to 3. Now sorts below Poly High, above KKOM High
- **ILJTM/ILKBS sort placement** — merit fallback 1.5 places them between Fair and Low tiers
- **Matric/STPM credential priority** — was returning 0 (fell through all checks); now returns 5 via source_type and name-based fallback
- **Course name capitalisation** — fixed BAHASA MELAYU → Bahasa Melayu, SAINS PENDIDIKAN → Sains Pendidikan, Ukm → UKM

### Removed
- **Frontend synthetic pre-U entries** — 201 lines removed from `dashboard/page.tsx` (pathwayResults, mergedRankingData, syntheticFlat useMemos)

### Stats
- Tests: 259 collected, 250 passing | Golden master: 8283
- Institutions: 239 (212 existing + 27 IPG)
- Course offerings: +1,971 PISMP-IPG links

## [1.32.2] - 2026-03-11 — Unified Pre-U Scoring & Pathway Fixes

### Added
- **Unified pre-U scoring system** — Asasi, Matric, and STPM all use consistent prestige + academic + field preference + signal adjustment scoring
  - Prestige order: Asasi (+12) > Matric (+8) > STPM (+5)
  - Academic bonus: Matric >=94:+8, >=89:+4; STPM <=4:+8, <=10:+4; Asasi >=90:+8, >=84:+4
  - Field preference bonus (+3) when quiz field interest matches pathway variant
- **Asasi-specific scoring in ranking engine** — replaces generic course-tag matching for pathway_type == 'asasi'
- **Matric/STPM cards for non-authenticated users** — synthetic pathway entries now appear in flat course list (without quiz)
- **Pre-U scoring design document** — `docs/plans/2026-03-11-pre-u-scoring-design.md`

### Changed
- **STPM progress bar scale** — uses full 3-27 mata gred range; shows raw values ("You: 4 | Need: 18") instead of converted 0-100
- **STPM Social Science 13-18 label** — changed from "Low" to "Fair" (appeal zone via Autonomi Pengetua)
- **Pathway card links** — now pass track/stream query params (was defaulting to Science)
- **MeritIndicator component** — accepts `displayStudent`/`displayCutoff` props for raw value display

### Removed
- **"Your Eligible Tracks" section** from Matric detail page (redundant with card grid)

## [1.32.1] - 2026-03-11 — Pathway Chance Indicator

### Added
- **Merit chance bar on Matric/STPM cards** — same High/Fair/Low indicator as regular courses
  - Matric: >= 94 High, 89-93 Fair, < 89 Low
  - STPM Science: always High (guaranteed place if eligible)
  - STPM Social Science: <= 12 High, 13-18 Low

### Changed
- **STPM Social Science eligibility expanded** — maxMataGred raised from 12 to 18; students with 13-18 now appear as Low chance instead of being excluded

## [1.32.0] - 2026-03-11 — Pathway Ranking, Quiz Flow, Data Persistence

### Added
- **Matric/STPM in ranked results** — pre-university pathways now compete in the ranked course list as synthetic entries with prestige + academic + quiz signal scoring (fit score range ~103-122)
- **Prestige scoring system** — `getPathwayFitScore()` in pathways.ts combines base score, prestige bonus (+8), academic bonus (merit/mata gred thresholds), and quiz signal adjustments
- **Supabase profile restore on login** — returning users get grades, demographics, and quiz signals restored from Supabase into localStorage automatically
- **localStorage cleanup on logout** — all `halatuju_*` keys wiped when signing out (multi-user device safety)

### Changed
- **Quiz signal adjustments for pathways** — 8 quiz questions now boost or penalise Matric/STPM scoring (e.g. concept-first learners +2, hands-on preference -1, pathway priority +3)
- **Report generation gated** — report can only be generated once per quiz run; retaking quiz resets the gate
- **Retake quiz navigation** — "Retake Quiz" button now navigates to `/quiz` instead of staying on dashboard

### Fixed
- **STPM subject data** — removed duplicate `pp` from 2 schools, fixed `PK`→`PAKN` mapping, removed redundant `MM/PP` from Kolej T6 Tun Fatimah
- **Missing STPM subjects** — added BT, BC, KMK, ICT, L.ENG to subject key legend with colours and full names

## [1.31.0] - 2026-03-11 — STPM UX Polish, WP Schools, MASCO Backfill

### Added
- **16 WP Kuala Lumpur Form 6 schools** — added to STPM school dataset from MOE SST6 portal
- **MASCO backfill management command** — `backfill_masco` command populates MASCO codes for 62 courses missing them, using Supabase lookup
- **Stream-filtered subjects** — STPM detail page filters school subjects by selected stream (Sains/Sastera)

### Changed
- **Average merit cutoff** — Quick Facts now shows average merit cutoff across all institutions offering the course, instead of student's own merit score
- **Pathway track cards on dashboard** — pills now show track cards inline when selected, with stream badge filtering
- **Card badge vs title** — pathway card badge shows short label (e.g. "Matric") while title keeps the full pathway name
- **STPM school data** — converted to title case at source for consistency
- **Mobile layout** — shorter labels, better spacing for pathway cards and course detail on small screens
- **Subject badges** — coloured by stream, phone number formatting improved, legend added to STPM detail page

### Fixed
- **WP and JPN preserved as uppercase** — title-case conversion no longer lowercases state abbreviations
- **School acronyms preserved** — e.g. "SMK" stays uppercase in school names

## [1.30.0] - 2026-03-10 — Matric/STPM Detail Pages, About Page, UX Fixes

### Added
- **Matriculation detail page** (`/pathway/matric`) — course-detail-style layout with header card, About This Track, Where to Study (15 KPM colleges), Quick Facts, Eligible Tracks sidebar, merit score with traffic light
- **STPM detail page** (`/pathway/stpm`) — same layout with 568 schools, state + PPD filters, stream badges, load-more pagination
- **Pathway track cards** — dashboard shows cards for each eligible matric track and STPM bidang when pills are active, with images, duration, fee, and institution count
- **Static data files** — `matric-colleges.ts` (15 colleges with track assignments from MOE Soalan Lazim Nov 2024) and `stpm-schools.json` (568 schools from MOE SST6 portal)
- **PathwayTrackCard component** — card component for matric tracks and STPM bidang with Supabase field images
- **About page content** — full mission statement: problem, what it does, who's behind it, how to help
- **About page i18n** — all content localised in EN, BM, and Tamil
- **Pathway detail i18n** — 30 keys across EN/BM/TA for matric/STPM detail pages
- **Student merit in Quick Facts** — course detail sidebar now shows student's merit score with colour coding

### Changed
- **Pathway pills** — matric and STPM pills now navigate to detail pages instead of filtering courses
- **Pathway pills as clickable filters** — all other pills toggle dashboard course filter; Clear button resets
- **Pathway pill order** — Asasi, Matric, Form 6 shown first; count shows eligible tracks (not scores)
- **Course detail header** — removed duplicate field name and duration (already in Quick Facts)
- **Institution link** — "Apply" button renamed to "More Info"
- **Phone login** — gracefully blocked with "coming soon" message directing users to Google sign-in

### Removed
- **Filter dropdowns** — removed institution type and course level dropdowns from dashboard (replaced by clickable pills)
- **"Ranked Courses" heading** — removed as redundant with Top Matches section

## [1.29.0] - 2026-03-10 — 9 Post-SPM Pathway Summary

### Added
- **Expanded pathways** — dashboard now shows 9 post-SPM options: Asasi, Matriculation, Form 6, PISMP, Polytechnic, University, Kolej Komuniti, ILJTM, ILKBS
- **Backend pathway_type** — eligibility API returns `pathway_type` field distinguishing Asasi from University (within UA), and ILJTM from ILKBS (within TVET) via institution category lookup
- **Course pathway map** — built at startup from CourseRequirement source_type, Course level, and Institution category
- **Compact badge layout** — PathwayCards redesigned as compact flex-wrap badges with unique SVG icons per pathway type
- **Pathway i18n** — 9 pathway type labels in EN/BM/TA plus "courses" count label

### Changed
- **PathwayCards component** — rewritten from individual track cards to compact summary badges showing eligible pathway types with course counts
- **Dashboard** — merges pathway engine results (Matric/STPM) with API eligibility counts by pathway_type

## [1.28.0] - 2026-03-10 — Matriculation & STPM Pathways

### Added
- **Matriculation eligibility** — 4 tracks (Sains, Kejuruteraan, Sains Komputer, Perakaunan) with subject requirements, minimum grade thresholds, and merit calculation (academic 90% + CoQ 10%)
- **STPM eligibility** — 2 bidang (Sains, Sains Sosial) with mata gred scoring. Best 3 credits from different subject groups, thresholds 18/12
- **Pathway engine** — pure TypeScript module (`lib/pathways.ts`) computing eligibility and scores entirely on the frontend
- **PathwayCards component** — dashboard cards showing eligibility status, merit scores (Matric) or mata gred (STPM), with reasons for ineligibility
- **4 stream subjects** — grades page expanded from 2 to 4 stream subject slots. Best 2 count as stream for UPU merit; weaker 2 compete with electives
- **Pathway i18n** — 14 translation keys across EN/BM/TA for pathway cards and eligibility reasons

### Changed
- **Grades page** — `aliranSubj1`/`aliranSubj2` state replaced with `aliranSubjects` array. Generic `handleAliranChange(index, id)` handler
- **UPU merit calculation** — sorts 4 stream grades, routes best 2 to stream section and weaker 2 to elective competition pool
- **Dashboard** — pathway cards rendered above course list, computed via `useMemo` from localStorage grades

## [1.27.0] - 2026-03-10 — Visual Quiz Redesign

### Added
- **Visual card quiz** — 8+1 questions with 2×2 icon card grids replacing old radio buttons. Each option has an emoji icon and short label
- **Multi-select** — Q1 ("What catches your eye?") and Q2 ("And this?") allow picking up to 2 options with weight splitting (3→2 each)
- **Conditional branching** — Q2.5 ("Which kind?") appears only when "Big Machines" is selected in Q2, splitting heavy industry into Electrical/Civil/Aero-Marine/Oil & Gas
- **"Not Sure Yet" option** — Q1, Q2, Q4 have a 5th option for undecided students. Q1/Q2 distribute +1 evenly across fields; Q4 generates zero signal
- **Field interest category** — new 6th signal category with 11 signals (`field_mechanical`, `field_digital`, `field_business`, `field_health`, `field_creative`, `field_hospitality`, `field_agriculture`, `field_electrical`, `field_civil`, `field_aero_marine`, `field_oil_gas`), capped at ±8
- **Field interest matching** — courses matched against `frontend_label` via `FIELD_LABEL_MAP`. Primary match +8, secondary +4
- **New signal wiring** — `rote_tolerant` (+3 for assessment-heavy courses), `high_stamina` (+2 for demanding courses), `quality_priority` (+1 for pathway-friendly/regulated courses)
- **Quiz i18n** — 12 new translation keys across EN/BM/TA for quiz UI (pickUpTo, notSureYet, becauseYouPicked, etc.)
- **Interpolation in i18n** — `t()` function now supports `{key}` parameter substitution

### Changed
- **Quiz data** — rewritten from 6 to 8+1 questions × 3 languages with `icon`, `select_mode`, `max_select`, `condition`, `not_sure` fields
- **Quiz engine** — handles both `option_index` (single) and `option_indices` (multi), weight splitting, "Not Sure Yet" exclusivity validation
- **Quiz submit API** — accepts either `option_index` or `option_indices` per answer
- **Ranking engine** — work preference cap lowered from ±6 to ±4; field interest cap ±8 (new)
- **Quiz page design** — gradient blue-purple header, progress bar, step dots, auto-advance on selection (no Next button), larger icons (text-5xl), mobile-first max-w-md layout

### Removed
- Dead signals: `organising`, `meaning_priority`, `exam_sensitive`, `time_pressure_sensitive`, `no_preference`
- Next button — auto-advance handles all navigation (300ms single-select, 400ms multi-select)

### Technical Notes
- 24 quiz tests + 16 ranking tests added. Total: 212 collected, 203 pass (9 pre-existing JWT failures). Golden master: 8245
- Stitch mockup: `projects/16660567457727755942` (10 screens)
- Design doc: `docs/quiz-redesign-final.md`
- Implementation plan: `docs/plans/2026-03-10-visual-quiz-redesign.md`
- Deployed as backend rev 41, frontend rev 47

## [1.26.0] - 2026-03-09 — My Profile & Course Interests

### Added
- **My Profile page** (`/profile`) — new page with 4 sections: Personal Details, Contact & Location, Family & Background, My Course Interests
- **Expanded student profile** — NRIC, address, phone number, family monthly income, number of siblings fields added to `StudentProfile` model (migrations 0010, 0011)
- **Course interest status** — saved courses now have a student-set status tag: Interested / Planning to apply / Applied / Got offer. Stored in `SavedCourse.interest_status` field
- **PATCH endpoint** — `PATCH /api/v1/saved-courses/<course_id>/` for updating interest status
- **Nav bar integration** — "My Profile" link added to top nav, dropdown menu, and mobile menu (all point to `/profile`)
- **i18n** — profile page translated in EN, BM, and TA (16 keys per language)
- **Exam-type page redesign** — gradient icon boxes, decorative corners, left-aligned layout, hover effects
- **Course detail page review** — documented 10 issues and prioritised fixes in `docs/Course Detail Page.pdf`

### Changed
- Profile API (`GET/PUT /api/v1/profile/`) returns and accepts new fields
- Profile sync (`POST /api/v1/profile/sync/`) accepts new fields
- Saved courses API (`GET /api/v1/saved-courses/`) returns `interest_status` per course
- "My Profile" links in header dropdown and mobile menu now point to `/profile` (was `/onboarding/grades`)

### Technical Notes
- 13 new backend tests (6 model + 3 SavedCourse + 4 API). Total: 188 collected, 179 pass (9 pre-existing JWT failures). Golden master: 8280
- Frontend build passes clean. `/profile` route: 4.3 kB (169 kB first load)
- Deployed as backend rev 40, frontend rev 44
- Design doc: `docs/plans/2026-03-09-my-profile-design.md`
- Stitch mockup: `projects/13238979537238863747`

## [1.25.1] - 2026-03-09 — Merit Score Fix

### Fixed
- **Merit score mismatch** — grades page showed 68.88 but course cards showed 56.38 for the same student. The backend was recalculating merit using a different subject grouping (5/3/1) instead of the correct UPU formula (4/2/2). Now the frontend sends its pre-computed merit score to the backend, eliminating the duplicate calculation entirely.

### Changed
- **Eligibility endpoint** — accepts optional `student_merit` field. When provided, skips backend recalculation. Falls back to old calculation for backwards compatibility.

### Technical Notes
- Frontend: grades page saves `finalMerit` to localStorage; dashboard includes it in API payload
- Backend: serializer accepts `student_merit`; view uses it directly when present
- 166 tests pass (9 pre-existing JWT failures unchanged). Golden master: 8280
- Deployed as backend rev 33, frontend rev 42

## [1.25.0] - 2026-02-26 — Eligible Toggle Auth Gate + Merit Progress Bar

### Added
- **Eligible toggle prompts login** — clicking the "Eligible Only" toggle on `/search` now opens the auth gate modal if the user is not logged in, encouraging account creation. Previously the toggle was permanently disabled because `halatuju_eligible_courses` was never written to localStorage.
- **`eligible` auth gate reason** — new `AuthGateReason` type, i18n strings (EN, BM, TA), resume action so toggle auto-activates after login
- **Merit progress bar indicator (Variation C)** — replaced simple traffic-light dot with a visual progress bar showing the student's score inside the bar, a dashed cutoff line, and "High/Fair/Low Chance" label with numeric scores (e.g. "You: 72 | Need: 65")
- **`eligibleMap` state** on search page — stores full `EligibleCourse` data (not just IDs), enabling merit scores to flow into CourseCard on the search page

### Changed
- **Eligible toggle** — changed from disabled `<label>` to always-clickable `<button>` element
- **MeritIndicator component** — now accepts `studentMerit` and `meritCutoff` props; falls back to simple dot+label when numeric scores are unavailable

### Technical Notes
- Frontend only — no backend changes, no migrations
- Build passes cleanly
- Deployed as frontend rev 40 (eligible toggle) and rev 41 (merit progress bar)
- Backend rev remains 32

## [1.23.4] - 2026-02-26 — Stitch Design Polish

### Changed
- **Pill labels shortened** — "All Institution Types" → "Institution Type", "All Levels" → "Course Level", etc. (EN, BM, TA)
- **Pill background** — white → gray-100 fill matching Stitch design
- **Search placeholder** — descriptive: "Search for courses, institutions, or fields (e.g. Computer Science, UM)..."
- **Clear Filters always visible** — greyed out when no filters active, blue when filters applied

## [1.23.3] - 2026-02-26 — Filter Pill Dropdown Redesign

### Changed
- **Filter dropdowns restyled as pill/chip buttons** — replaced 4 native HTML `<select>` elements with custom `FilterPill` component matching Stitch design (compact rounded pills, chevron icon, dropdown panels)
- **Active filter state** — selected pills highlight with primary blue border/background
- **Clear Filters button** — now has funnel icon and rounded-full styling to match pills
- **Outside-click dismiss** — dropdown panels close when clicking outside

### Technical Notes
- New component: `src/components/FilterPill.tsx` (~100 lines, uses `clsx`)
- No new dependencies, no backend changes, no i18n changes
- Build passes cleanly

## [1.23.2] - 2026-02-25 — Search Page Stitch Alignment

### Added
- **Institution info on search cards** — each course card now shows the primary institution name, state (pin icon), and "+N more" count when offered at multiple institutions
- **Book icon** on field text in course cards for visual consistency with Stitch design
- **Clear Filters button** — appears in the filter row when any filter is active, resets all filters in one click
- **Eligibility toggle redesign** — replaced plain checkbox with a styled pill toggle, moved into the filter row with descriptive subtitle text
- **Search API: institution fields** — backend now returns `institution_name` and `institution_state` per course via Django Subquery (alphabetically first offering)
- **3 new backend tests** for institution name, state, and empty-offering fallback
- **3 new i18n keys** (`clearFilters`, `eligibleToggleDesc`, `moreInstitutions`) in EN, BM, TA

### Technical Notes
- Backend tests: 173 collected, 164 passing (9 pre-existing JWT failures — not production)
- Golden master: 8280 (unchanged)
- Files changed: 8 (1 backend view, 1 test, 1 API type, 3 i18n, 1 component, 1 page)

## [1.23.1] - 2026-02-25 — Deploy Fix: Suspense Boundary

### Fixed
- **Next.js prerender crash** — `/search` page crashed during Cloud Run build because `useSearchParams()` requires a `<Suspense>` boundary for static generation. Wrapped `SearchPageInner` in `<Suspense>` with a loading spinner fallback.
- **Stale container image** — previous failed deploy pushed a stale image to gcr.io (old Container Registry). Redeployed from source to Artifact Registry (`asia-southeast1-docker.pkg.dev`), restoring correct build. Frontend now on rev 35.

### Technical Notes
- Backend tests: 173 passing (13 pre-existing JWT test failures — not a production issue)
- Golden master: 8280 (unchanged)

## [1.23.0] - 2026-02-25 — Course Search / Explorer

### Added
- **Course search page** (`/search`) — browse the full course catalogue with text search and 4 filters (Institution Type, Course Level, State, Field)
- **Search API** (`GET /api/v1/courses/search/`) — server-side filtering, pagination, dynamic filter options, institution count per course
- **Eligible-only toggle** — if student has eligibility data, toggle to show only courses they qualify for
- **"Explore" nav link** — added to header between Dashboard and Saved
- **i18n** — full search page translations in EN, BM, TA
- **10 backend tests** for the search endpoint (text, level, field, source_type, state, pagination, combined, institution count)

### Changed
- **Institution URLs** — corrected 7 broken/outdated institution website links in `data/institutions.csv`

## [1.22.4] - 2026-02-25 — Profile Page Polish

### Changed
- **Profile icons** — replaced emoji icons (🇲🇾, 🌍, 👨, 👩, 🎨, ♿) with inline SVG icons for nationality, gender, and health condition buttons; icons change colour when selected
- **"Non-Malaysian" label** — renamed to "Foreign" (EN), "Asing" (BM), "வெளிநாட்டவர்" (TA) for clarity

## [1.22.3] - 2026-02-23 — Merit Formula Fix + Supabase Security

### Fixed
- **UPU merit formula** — replaced incorrect engine.py port with correct UPU calculation: `weighted = (core/72×40) + (stream/36×30) + (elective/36×10)`, `academic = weighted × 9/8`, cap 90 + CoQ
- **Stale grades bug** — grades from previously-selected subjects lingered in localStorage, inflating merit score; now only grades for currently-selected subjects (core + aliran + electives) are loaded
- **Dynamic merit on subject switch** — clearing old subject grades when switching stream, aliran, or elective subjects so merit updates immediately
- **14 Supabase RLS initplan warnings** — rewrote all RLS policies using `(select auth.uid())` subselect for performance
- **Supabase `django_migrations` RLS** — enabled Row Level Security on Django migrations table (security advisory)

### Changed
- **Merit score display** — removed green/yellow colour coding; score displays in neutral grey (no judgement)
- **Merit calculation** — grades page now passes categorised grades (core/stream/elective) directly instead of flat map with heuristic splitting

## [1.22.2] - 2026-02-23 — UI Polish: Grades Page

### Changed
- **Subject renames** — "Bahasa Tamil" → "Bahasa Cina/Tamil", "Bahasa Cina" → "Kesusasteraan Cina/Tamil" (combined options to shorten dropdown)
- **Stream pills** — equal-width grid layout, less rounded (rounded-xl), two-tone SVG icons (flask/book/wrench)
- **Shadow/depth treatment** — subtle shadows on core subject cards, stream pills, compact subject rows, merit panel, grade buttons (modern soft style)

### Added
- **Lukisan** — new subject in Arts stream pool and elective list (distinct from PSV)
- **StreamIcon component** — two-tone SVG icons for science/arts/technical streams

## [1.22.1] - 2026-02-23 — Sprint 20: Merit Score & CoQ

### Added
- **Co-curricular (CoQ) score input** — decimal number input (0-10, e.g. 5.50, 7.85) on profile page
- **Live merit score panel** — grades page shows real-time academic merit (/ 90) + CoQ (/ 10) = total (/ 100) as grades are entered
- **Client-side merit calculator** — TypeScript port of `engine.py` formula in `lib/merit.ts` (`prepareMeritInputs` + `calculateMeritScore`)
- New translation keys in EN, BM, TA: coqScore, coqHint, meritScore, academicMerit, coqMerit, meritTotal

### Fixed
- **Stream subject pre-population** — first-time visitors now see default stream subjects (PHY/CHE for science) instead of empty dropdowns

### Changed
- **Backend CoQ passthrough** — `EligibilityRequestSerializer` now accepts `coq_score` (float, 0-10); `views.py` uses it instead of hardcoded 5.0
- Dashboard passes saved CoQ from profile localStorage to eligibility API
- `StudentProfile` interface updated with optional `coq_score` field

## [1.22.0] - 2026-02-23 — Sprint 20: Onboarding Redesign

### Added
- **SPM/STPM exam type selection** — new `/onboarding/exam-type` screen with SPM card (active) and STPM card (coming soon)
- **Progress stepper** — shared `ProgressStepper` component shows "Step 1 of 3" with visual progress bars across all onboarding screens
- **Negeri (state) dropdown** — 16 Malaysian states/territories added to profile page
- **Elective subject add button** — "Tambah Subjek Elektif" dashed button to dynamically add 0-2 elective subjects
- New translation keys in EN, BM, TA for all new UI elements

### Changed
- **Stream + grades merged** — stream selection (compact pill buttons) now lives on the grades page, removing one navigation step
- **Core subjects redesign** — button grid with green checkmark on completion, clear icon, responsive 5+5 mobile layout
- **Stream/elective subjects redesign** — compact dropdown + grade badge dropdown rows replacing full button grids
- **Profile page compact layout** — single card with Negeri, Jantina toggle, Nationality toggle, Keperluan Khas checkboxes with accessibility icons
- **Improved helper text** — contextual subtitles on each screen ("Enter your grades so we can find courses that match your results")
- All `/onboarding/stream` links updated to `/onboarding/exam-type` across landing, dashboard, footer, login pages

### Removed
- `/onboarding/stream` page — stream selection moved into grades page

### Technical Notes
- Next.js build: 20 routes, 0 errors
- Files: 10 modified/created, 1 deleted
- Backend tests: 176 (unchanged — frontend-only sprint)
- Golden master: 8280 (unchanged)

## [1.21.0] - 2026-02-23 — Course Image Classification (37 Categories)

### Added
- **37 AI-generated course images** — replaced 9 generic field images with 37 category-specific images generated via Gemini 2.5 Flash Image, covering all 383 courses
- **Keyword-based image matching** — `CourseCard.tsx` now uses a multi-level matcher (`getImageSlug`) that routes courses to images based on field name and course name keywords
- **Sub-routing for large fields** — Pendidikan (73 courses) splits into 5 teaching-subject images; Mekanikal & Pembuatan (24) into 4; Elektrik & Elektronik (13) into 3; Teknologi Maklumat into 2
- **"Umum" dissolution** — 17 miscategorised "Umum" courses now route to proper categories via course name matching (e.g. perikanan → pertanian, bank → perakaunan)
- **Future STPM images** — pre-created images for Undang-undang and Farmasi categories

### Changed
- **Every course now has an image** — previous system had 97% of courses showing a grey placeholder (only 13/383 matched). Now 383/383 resolve to a relevant image
- **`getFieldImageUrl` signature** — now takes `(field, courseName)` instead of just `(field)`, enabling course-name-based sub-routing
- **Image generation script** — `tools/generate_field_images.py` rewritten with 37 categories, detailed Malaysian-context prompts, and `--skip-existing` flag

### Technical Notes
- 37 images uploaded to Supabase Storage `field-images` bucket (~1.5-2 MB each)
- 15-max rule: no image category covers more than 15 courses
- Next.js build: 20 routes compiled successfully
- Modified files: `CourseCard.tsx`, `generate_field_images.py`, `CHANGELOG.md`

## [1.20.0] - 2026-02-23 — Sprint 18: Header & Footer Redesign

### Added
- **AppHeader component** — shared responsive header with logo (120px), Dashboard/Saved nav links with active indicator, profile dropdown (name, email, My Profile, My Applications, Settings, Log Out), mobile hamburger menu with slide-out drawer
- **AppFooter component** — shared footer with brand column + tagline, Quick Links (Dashboard, Start Here, Saved), Legal links (About, Privacy, Terms, Cookies), copyright bar with Contact Us link
- **Profile dropdown** — shows user initials avatar, full name and email from Supabase session metadata, grouped account actions, red Log Out button with sign-out via Supabase
- **Cookies page** (`/cookies`) — explains essential cookies only, no tracking/analytics, links to Settings for data clearing
- **Contact page** (`/contact`) — Tamil Foundation (MCEF) contact info, email for enquiries and data deletion requests
- **Logout functionality** — first time users can sign out (calls `supabase.auth.signOut()`, redirects to landing)
- **i18n keys** — `header.*` (myProfile, myApplications, logout), `footer.*` (tagline, quickLinks, legal, startHere), `common.cookies`, `common.contact` in all 3 languages (EN, BM, TA)

### Changed
- **Logo optimised** — compressed from 6.2 MB to 27 KB (99.6% reduction), transparent background, 480px wide for retina
- **Logo size increased** — rendered at 120×40px across all pages (was 60×32px), improves brand visibility
- **All pages now use shared header/footer** — dashboard, saved, settings, outcomes, about, privacy, terms, course detail, report. Landing page uses shared footer with its own hero header. Quiz page keeps focused workflow header.
- **About/Privacy/Terms pages** — upgraded from back-arrow mini-headers to full AppHeader + AppFooter
- **Privacy page** — added contact email link

### Technical Notes
- Backend tests: 176 (unchanged) | Golden master: 8280 (unchanged)
- Next.js build: 20 routes compiled successfully
- New files: `AppHeader.tsx`, `AppFooter.tsx`, `/cookies/page.tsx`, `/contact/page.tsx`
- Modified: 15 frontend files, 0 backend files

## [1.19.1] - 2026-02-22 — Post-Sprint 17 Hotfixes

### Fixed
- **ES256 JWT authentication**: Supabase user access tokens use ES256 (JWKS), but middleware only accepted HS256 — all authenticated API calls (saved-courses, reports, outcomes) returned 403. Middleware now checks token `alg` header and routes to HS256 (JWT secret) or ES256 (JWKS public key via `PyJWKClient`).
- **Missing Cloud Run env vars**: Added `SUPABASE_JWT_SECRET`, `GEMINI_API_KEY`, and `SUPABASE_URL` to backend Cloud Run service.
- **Google name pre-fill**: AuthGateModal now pre-fills the user's name from their Google profile on OAuth sign-in.

### Added
- **"Read Report" button**: Dashboard shows "Read Report" (linking to existing report) instead of "Generate Report" when a report already exists. Reverts to "Generate Report" on quiz retake.
- **3 i18n keys**: `dashboard.readReport` in EN ("Read Report"), BM ("Baca Laporan"), TA ("அறிக்கையைப் படி")

### Technical Notes
- Backend tests: 176 (unchanged) | Golden master: 8280 (unchanged)
- Deployed: backend rev 26, frontend rev 20
- Cloud Run env vars added: `SUPABASE_JWT_SECRET`, `GEMINI_API_KEY`, `SUPABASE_URL`
- JWKS client uses `PyJWKClient` from `PyJWT` with automatic key caching

## [1.19.0] - 2026-02-22 — Sprint 17: Outcome Tracking

### Added
- **AdmissionOutcome model** — tracks student application outcomes (applied/offered/accepted/rejected/withdrawn) per course+institution, with intake year, session, notes, and date fields
- **CRUD endpoints** (`/api/v1/outcomes/` and `/api/v1/outcomes/<id>/`) — list, create, update status, delete. All auth-required, filtered to own outcomes.
- **"I Applied!" / "I Got an Offer!" buttons** on saved courses page — inline outcome creation with optimistic UI
- **Outcomes page** (`/outcomes`) — "My Applications" page listing all outcomes with colour-coded status badges, inline status editing, and delete
- **Track Applications CTA** on saved courses page — links to outcomes page
- **20 i18n keys** in `outcomes.*` section across all 3 locales (EN, BM, Tamil)
- 10 new backend tests: CRUD, duplicate (409), auth enforcement (403), cross-user isolation

### Technical Notes
- Backend tests: 176 (+10) | Golden master: 8280 (unchanged)
- Frontend build: passes clean
- Migration 0009 applied: `admission_outcomes` table with RLS + 5 policies
- Supabase security advisor: 0 errors (excluding known `django_migrations`)
- Sprint 16 deployed: backend rev 21, frontend rev 17

## [1.18.0] - 2026-02-22 — Sprint 16: Registration Gate

### Added
- **AuthGateModal** (`components/AuthGateModal.tsx`): Multi-step registration modal with inline Phone OTP + Google OAuth sign-in, reason-specific messaging (quiz/save/report), benefit bullets, and name+school profile completion form
- **AuthContext** (`lib/auth-context.tsx`): `AuthProvider` + `useAuth()` hook wrapping Supabase session state, providing `token`, `isAuthenticated`, `showAuthGate(reason)`, `hideAuthGate()`. Detects pending Google OAuth actions on mount.
- **ProfileSyncView** (`POST /api/v1/profile/sync/`): New backend endpoint that bulk-pushes localStorage data (grades, gender, quiz signals, name, school) to backend after first login — creates or updates profile in one call
- **`name` + `school` fields** on `StudentProfile` model (migration 0008) — for follow-up tracking
- **Profile sync API** (`syncProfile()` in `api.ts`) + `SyncProfileData` type
- **21 i18n keys** in `authGate.*` section across all 3 locales (EN, BM, Tamil)
- 4 new backend tests: sync creates profile, sync updates existing, sync rejects anon, profile PUT accepts name/school

### Changed
- **Dashboard**: Save button always visible (gates on auth if not logged in), Report CTA always visible (was hidden for guests), Quiz CTA triggers auth gate instead of direct navigation. Actions auto-resume after auth completion via localStorage resume action.
- **Quiz page**: Gated behind authentication — shows sign-in prompt with auth gate trigger for unauthenticated visitors
- **Dashboard imports**: Replaced ad-hoc `getSession()` with `useAuth()` hook for consistent auth state

### Technical Notes
- Backend tests: 166 (+4) | Golden master: 8280 (unchanged)
- Frontend build: passes clean
- Google OAuth edge case handled: pending action stored in localStorage before redirect, AuthProvider restores it on mount, modal opens at profile step
- New files: `components/AuthGateModal.tsx`, `lib/auth-context.tsx`
- Modified: `providers.tsx`, `dashboard/page.tsx`, `quiz/page.tsx`, `api.ts`, `views.py`, `models.py`, `urls.py`, `en.json`, `ms.json`, `ta.json`

## [1.17.0] - 2026-02-22 — Sprint 16: Bilingual Descriptions Pipeline

### Added
- `headline_en` and `description_en` fields on Course model (migration 0007)
- `load_course_descriptions()` method in data loader — reads `course_descriptions.json`, populates all 4 description fields
- `data/course_descriptions.json` — 383 bilingual course descriptions extracted from `src/description.py`
- Course detail page now shows locale-appropriate headline and description (BM for `ms`, EN for `en`/`ta`)
- `courseDetail.*` i18n keys added to all 3 locale files (EN, BM, Tamil)
- 6 new tests: bilingual API fields, empty defaults, description loading, TVET overwrite protection

### Fixed
- TVET metadata loader no longer overwrites rich descriptions with thin CSV text (conditional update)

### Technical Notes
- CourseSerializer now exposes `headline_en`, `description_en`
- Frontend `Course` interface updated with new fields
- Supabase migration applied: `ALTER TABLE courses ADD COLUMN headline_en/description_en`
- Backend tests: 162 (was 156) | Golden master: 8280 (unchanged)

## [1.16.1] - 2026-02-21 — Description Sprint: Quality Audit + English Translations

### Added
- English translations (`headline_en`, `synopsis_en`) for all 383 course descriptions in `src/description.py` — enables bilingual course cards
- `headline` field added to all entries (previously only `synopsis` existed)
- English fallback defaults in `get_course_details()` function

### Fixed
- 33 description quality issues across all 6 institution types:
  - 25 "mereka" (third-person) pronoun fixes → "anda" (second-person, direct address)
  - 2 typos: "DANN" → "DAN", "turu padang" → "turun padang"
  - 2 thin descriptions expanded (IJTM-CET-035, IJTM-CET-037)
  - 3 headline fixes ("Suara Untuk Mereka" → "Suara Untuk Semua")
  - 1 "kita" → "anda" fix

### Technical Notes
- `src/description.py`: ~2,400 → ~3,090 lines
- All 383 entries verified via AST parsing — 100% bilingual coverage
- British English spelling throughout translations
- Backend tests: 156 (unchanged) | Golden master: 8280 (unchanged)

## [1.16.0] - 2026-02-20 — Sprint 15: Career Pathways (MASCO Integration)

### Added
- **MascoOccupation model**: New Django model with `masco_code` (PK), `job_title`, `emasco_url` — stores 272 MASCO-classified occupations from Malaysia's official eMASCO portal
- **Course ↔ Occupation M2M**: `Course.career_occupations` ManyToManyField links courses to career outcomes (531 unique links across all TVET and Polytechnic courses)
- **Career Pathways on course detail**: New "Career Pathways" section on `/course/[id]` page shows clickable indigo pill badges linking to eMASCO portal pages for each linked occupation
- **API: career_occupations in course detail**: `GET /api/v1/courses/<id>/` now returns `career_occupations` list with `masco_code`, `job_title`, and `emasco_url`
- **MASCO data loaders**: Two new methods in `load_csv_data.py` — `load_masco_occupations` (from `masco_details.csv`) and `load_course_masco_links` (from `course_masco_link.csv` with deduplication)
- **8 new tests**: 3 API tests (career occupations in detail, field validation, empty list) + 5 model tests (PK, M2M, reverse relation, idempotent update_or_create, __str__)
- Migration `0005_add_masco_occupations`

### Technical Notes
- Backend tests: 156 (+8) | Golden master: 8280 (unchanged)
- Data loaded into Supabase with RLS enabled (public read) on both `masco_occupations` and `courses_course_career_occupations` tables
- MASCO data sourced from existing project files (`data/masco_details.csv`, `data/course_masco_link.csv`) — originally used by legacy Streamlit app
- eMASCO portal pages contain starting salary, annual increment, demand status, and job descriptions

## [1.15.0] - 2026-02-20 — Sprint 14: TVET Data Fix + UX Polish

### Fixed
- **TVET orphaned courses**: All 84 TVET courses had zero institution links because `load_course_details` used `.filter().update()` on non-existent `CourseInstitution` records. Changed to `update_or_create` so TVET rows in `details.csv` create links when none exist.
- **Institution taxonomy**: 55 ILKBS/ILJTM institutions were incorrectly typed as `IPTA`. Changed to `ILKA` in `data/institutions.csv` and Supabase DB (157 IPTA + 55 ILKA).

### Added
- **181 TVET course-institution links** now loaded correctly — IKBN/IKTBN/IKSN courses linked to ILKBS institutions, ILP/ADTEC/JMTI courses linked to ILJTM institutions, with fees, allowances, and application hyperlinks.
- **Settings page redesign** (`settings/page.tsx`): Language selector, clear profile data button, about section — fully localised (EN/BM/TA).
- **Saved page i18n**: Localised with `useT()` hook across all 3 locales.
- **Settings and saved i18n keys**: Added `settings.*` and `saved.*` translation keys to all 3 locale files.

### Changed
- **Gemini SDK migration**: `google-generativeai` (deprecated) replaced with `google-genai` v1.x Client API pattern in `report_engine.py`. Updated mocks in `test_report_engine.py`.
- **`requirements.txt`**: `google-generativeai>=0.3,<1.0` → `google-genai>=1.0,<2.0`

### Technical Notes
- Backend tests: 148 (unchanged) | Golden master: 8280 (unchanged)
- Both `halatuju-api` and `halatuju-web` deployed to Cloud Run
- Data fix applied directly to Supabase DB (55 institution type updates + 181 link inserts)

## [1.14.0] - 2026-02-18 — Sprint 13: Localisation (EN/BM/TA)

### Added
- **i18n infrastructure** (`lib/i18n.tsx`): React context with `useT()` hook, localStorage-persisted locale preference, static JSON imports for zero-latency switching
- **Language selector** (`components/LanguageSelector.tsx`): Dropdown in landing page nav and dashboard header — switches between English, Bahasa Melayu, and Tamil
- **142 translation keys** per locale across 6 sections: common, landing, onboarding, dashboard, login, subjects
- **i18n validation script** (`scripts/check-i18n.js`): Checks JSON parsing, key completeness across all 3 locales, and no empty values

### Changed
- **6 core pages localised**: Landing, stream selection, grades input, profile input, dashboard, and login — all hardcoded strings replaced with `t('key')` calls
- **Landing page** converted from server component to client component to support `useT()` hook
- **Grades page**: Core subject labels now use translated `t('subjects.XX')` keys; stream/elective subjects retain official Malay names
- **Dashboard sub-components** (`InsightsPanel`, `FilterDropdown`, `RankedResults`, `LoadingScreen`) each call `useT()` for their own translated strings
- **Tamil translations** quality-reviewed per style guide: brand name kept as "HalaTuju", compound words joined, sandhi rules applied

### Technical Notes
- Backend tests: 148 (unchanged) | Golden master: 8280 (unchanged)
- Frontend-only sprint — no backend changes, no migrations
- New files: `lib/i18n.tsx`, `components/LanguageSelector.tsx`, `scripts/check-i18n.js`
- Modified: 3 JSON translation files + 6 page files + `providers.tsx`

## [1.13.0] - 2026-02-18 — Sprint 12: Report Frontend + PDF

### Added
- **Report display page** (`/report/[id]`): Renders AI counsellor report as formatted markdown with `react-markdown` and Tailwind Typography prose styling
- **PDF download**: "Download PDF" button using `window.print()` with `@media print` stylesheet (A4, clean layout, hidden nav)
- **Generate Report CTA** on dashboard: Auth-protected button calls `POST /api/v1/reports/generate/`, redirects to report page on success
- **Report API client functions** in `api.ts`: `generateReport()`, `getReport()`, `getReports()` with TypeScript types
- 4 new view tests: report list (own reports only), report detail, cross-user 404 regression, validation

### Fixed
- **FK bug in report views**: `ReportDetailView` and `ReportListView` filtered by `student_id=request.user_id` (comparing integer PK with UUID string — would never match). Fixed to `student__supabase_user_id=request.user_id`

### Dependencies
- Added `react-markdown@10.1.0` for markdown rendering
- Added `@tailwindcss/typography` for prose styling

## [1.12.0] - 2026-02-18 — Sprint 11: AI Report Backend

### Added
- **Report engine** (`apps/reports/report_engine.py`): Gemini-powered narrative counselor report generator with model cascade fallback (gemini-2.5-flash → gemini-2.5-flash-lite → gemini-2.0-flash)
- **Report prompts** (`apps/reports/prompts.py`): BM and EN counselor report templates ported from legacy Streamlit, with counselor personas (Cikgu Venu, Cikgu Gopal, Cikgu Guna)
- **Report API endpoints**: `POST /api/v1/reports/generate/` (generate report), `GET /api/v1/reports/` (list), `GET /api/v1/reports/<id>/` (detail) — all auth-protected
- 12 new tests: format helpers (grades, signals, courses, insights), prompt templates (BM/EN), persona mapping, Gemini mock (success, cascade fallback, missing API key)

### Changed
- Report views wired up (previously stubs returning "coming soon")
- Reports URL config updated with list endpoint

## [1.11.0] - 2026-02-18 — Sprint 10: Deterministic Insights

### Added
- **Insights engine** (`insights_engine.py`): Pure function that generates structured summaries from eligibility results — stream breakdown, top fields, level distribution, merit summary, and Malay summary text
- **Insights in eligibility response**: `POST /api/v1/eligibility/check/` now returns an `insights` key alongside `eligible_courses` and `stats`
- **InsightsPanel component** on dashboard: Three-column layout showing top fields (Bidang Teratas), level distribution (Tahap Pengajian), and merit bar chart (Peluang Kemasukan)
- 8 new tests: empty input, stream breakdown, labels, top fields ranking, merit counts, level distribution, summary text
- **KKOM separation**: Kolej Komuniti requirements split into dedicated `kkom_requirements.csv` with `source_type: 'kkom'`

### Changed
- Eligibility API response now includes `insights` object for frontend consumption
- Dashboard displays insights panel between stats cards and quiz CTA
- API types updated with `Insights`, `InsightsStreamItem`, `InsightsFieldItem`, `InsightsLevelItem` interfaces

## [1.10.0] - 2026-02-18 — Sprint 9: Data Gap Filling

### Added
- **TVET course metadata**: 84 TVET courses enriched with names, levels, departments, descriptions, semesters, and WBL flags from `tvet_courses.csv`
- **PISMP course metadata**: 73 PISMP courses enriched with level (Ijazah Sarjana Muda Pendidikan), department, field, semesters (8), and auto-generated Malay descriptions
- **Institution modifiers in DB**: Added `modifiers` JSONField to Institution model — ranking modifiers (urban, cultural_safety_net, etc.) now stored in PostgreSQL instead of loaded from filesystem JSON
- **`audit_data` management command**: Reports data completeness across courses, requirements, institutions, offerings, and tags
- 5 new tests: TVET enrichment, PISMP enrichment, institution modifiers storage

### Fixed
- **Institution modifiers not working on Cloud Run**: Modifiers were read from `data/institutions.json` at startup, but this file isn't in the Docker image. Now loaded from DB via `load_csv_data`.

### Technical Notes
- Migration 0004: adds `modifiers` JSONField (default={}) to Institution
- All 383 courses now have complete metadata (description, level, department, field, frontend_label, semesters)
- `load_csv_data` now runs 9 loaders in sequence: courses → requirements → tvet_metadata → pismp_metadata → institutions → modifiers → links → details → tags

## [1.9.0] - 2026-02-18 — Sprint 8: Course Detail Enhancement

### Added
- **Course offering details** in `/course/[id]` API response — tuition fees, hostel fees, registration fee, monthly/practical allowances, free hostel/meals flags, application hyperlink
- **"Apply" button** on institution cards linking to official application portals (407 courses with hyperlinks)
- **Fee display** on institution cards — tuition, hostel, and registration fees in a clean grid layout
- **Benefit badges** — "Free Hostel", "Free Meals", and "RM{amount}/month" allowance badges on institution cards
- **`load_course_details`** management command method — loads `details.csv` to enrich CourseInstitution rows (TVET: per-institution, Poly/Univ: per-course)
- 5 new backend tests: offering fees, hyperlink, allowances, free badges, empty field handling

### Technical Notes
- No schema migration needed — CourseInstitution model already had fee fields from initial setup
- `details.csv` (407 rows): TVET rows have institution_id (per-institution fees), Poly/Univ rows don't (shared fees across all institutions)
- Golden master unchanged at 8280 (no engine changes)

## [1.8.0] - 2026-02-18 — Sprint 7: PISMP Integration

### Added
- **73 PISMP (teacher training) courses** integrated into eligibility engine — new `source_type: 'pismp'`
- **PISMP data file** (`data/pismp_requirements.csv`) — cleaned and formatted from draft
- **"Teacher Training" filter** in dashboard dropdown and stat card
- **Amber badge styling** for PISMP courses (`bg-amber-100 text-amber-700`)
- 8 new backend tests: eligibility, exclusion, borderline, subject-specific, Malaysian-only, stats, merit labels, subject requirements
- Django migration `0003_add_pismp_source_type`

### Fixed
- **Empty subjects bug** in `check_subject_group_logic`: rules with `subjects: []` (meaning "any N subjects at grade X") were silently skipped. Now counts from all student grades. Critical for PISMP's "5 Cemerlang from any subjects" requirement.
- **NaN guard** in `check_subject_group_logic` and `check_complex_requirements`: non-string input (NaN from DataFrame concat) no longer crashes the engine

### Technical Notes
- Golden master unchanged at 8280 (PISMP data is additive, no existing courses affected)
- PISMP courses have no `merit_cutoff` — merit labels are `null` (same as TVET)
- `age_limit` field in PISMP data not implemented (not in student profile) — documented as future enhancement

## [1.7.0] - 2026-02-17 — Sprint 6: Dashboard Redesign (Card Grid)

### Added
- **Merit traffic lights** on course cards: Green (High Chance), amber (Fair Chance), red (Low Chance) indicators based on student merit vs course cutoff
- **Student merit calculation** in eligibility endpoint: Computes merit score from SPM grades using UPU-style formula, returns `merit_label`, `merit_color`, `student_merit` per course
- **CourseCard component** (`components/CourseCard.tsx`): Extracted reusable vertical card with field image header, merit indicator, rank badge, and fit reason tags
- 2 new backend tests for merit labels in eligibility response

### Changed
- **Dashboard layout**: Responsive card grid (3 col desktop, 2 tablet, 1 mobile) replaces single-column list
- **Card design**: Vertical layout with field image on top instead of horizontal flex
- Low merit courses (`merit_label === 'Low'`) rendered with reduced opacity
- TVET courses show no merit indicator (no cutoff data)
- Dashboard reduced from ~764 to ~370 lines by extracting CourseCard and FilterDropdown

### Fixed
- **Ranking merit penalty** now works correctly: `student_merit` included in eligibility response flows through to ranking API (previously defaulted to 0)
- Grade key mismatch: `prepare_merit_inputs` expects `'history'`, serializer produces `'hist'` — adapted in eligibility view

### Technical Notes
- Backend tests: 106 (+2) | Golden master: 8280 (unchanged)
- New files: `src/components/CourseCard.tsx` | Modified: `views.py`, `test_api.py`, `api.ts`, `dashboard/page.tsx`
- CoQ (co-curricular quality) score defaults to 5.0 — future enhancement to ask user

## [1.6.0] - 2026-02-17 — Sprint 5: Quiz Frontend

### Added
- **Quiz page** (`/quiz`): Interactive 6-question quiz with step-by-step navigation, progress bar, and auto-advance on selection
- **Quiz API integration** (`lib/api.ts`): `getQuizQuestions()`, `submitQuiz()`, `getRankedResults()` functions with TypeScript types
- **Take Quiz CTA** on dashboard: Prominent gradient banner inviting users to personalise their rankings
- **Ranked results view** on dashboard: Top 5 matches with rank badges and fit reason tags, plus "Other Eligible Courses" section
- **Quiz state management**: Signals stored in localStorage; retake quiz option clears and resets
- **Quiz completed banner**: Green confirmation with retake link when quiz has been completed

### Changed
- Dashboard dynamically switches between flat eligibility list (no quiz) and ranked results (after quiz)
- Dashboard subtitle updates based on whether quiz has been taken

### Technical Notes
- Frontend-only sprint — no backend changes, no migrations
- Backend tests: 104 (unchanged) | Golden master: 8280 (unchanged)
- New files: `src/app/quiz/page.tsx` | Modified: `src/lib/api.ts`, `src/app/dashboard/page.tsx`
- Quiz signals persisted in `halatuju_quiz_signals` localStorage key
- Ranking query uses React Query with eligibility + signals as combined query key

## [1.5.0] - 2026-02-17 — Sprint 4: Ranking Engine Backend

### Added
- **Ranking engine** (`apps/courses/ranking_engine.py`): Ported 551-line Streamlit ranking engine to Django — pure functions, no globals, no file I/O
- **Ranking endpoint** (`POST /api/v1/ranking/`): Accepts eligible courses + student signals, returns top 5 + rest with fit scores and natural language reasons
- **RankingRequestSerializer**: Validates eligible_courses (each must have course_id) and student_signals
- **Institution data loading**: AppConfig now loads course tags map, institution subcategories, and institution modifiers (from JSON) at startup
- **Ranking tests** (`test_ranking.py`): 34 new tests covering score calculation, category/institution/global cap enforcement, merit penalty (High/Fair/Low), sort tie-breaking (5 levels), credential priority, top_5/rest split, API endpoint validation

### Technical Notes
- Test count: 70 → 104 (+34 ranking tests)
- Golden master: 8280 (unchanged)
- No migrations, no deploy (backend only)
- Ranking engine uses dependency injection — course tags and institution data passed as parameters, not loaded from files
- Institution modifiers (urban, cultural_safety_net) loaded from `data/institutions.json` at startup; future sprint will migrate to model fields

## [1.4.0] - 2026-02-16 — Sprint 3: Quiz API Backend

### Added
- **Quiz data module** (`apps/courses/quiz_data.py`): 6 psychometric questions in 3 languages (EN, BM, TA), ported from `src/quiz_data.py`
- **Quiz engine** (`apps/courses/quiz_engine.py`): Stateless signal accumulator — takes answers in, returns categorised signals in 5-bucket taxonomy
- **Quiz questions endpoint** (`GET /api/v1/quiz/questions/?lang=en`): Returns quiz questions in requested language, public (no auth)
- **Quiz submit endpoint** (`POST /api/v1/quiz/submit/`): Accepts 6 answers, returns `student_signals` + `signal_strength`, public (no auth)
- **Quiz tests** (`test_quiz.py`): 14 new tests covering endpoint behaviour, signal accumulation, taxonomy mapping, validation, and language parity

### Technical Notes
- Test count: 56 → 70 (+14 quiz tests)
- Golden master: 8280 (unchanged)
- No migrations, no deploy (backend only)
- `ProfileView.put()` already accepts `student_signals` — no change needed
- Quiz engine is fully stateless: no session, no DB writes. Frontend sends all 6 answers in one POST.

## [1.3.0] - 2026-02-16 — Sprint 2: Saved Courses Fix + Page Shells

### Added
- **Saved courses page** (`/saved`): Lists saved courses from API, remove button, login prompt for guests
- **Settings page** (`/settings`): Links to edit grades, saved courses, about, privacy, terms
- **About page** (`/about`): Project description and mission
- **Privacy policy page** (`/privacy`): Data collection, usage, and storage disclosure
- **Terms of service page** (`/terms`): Disclaimer and liability
- **Auth callback page** (`/auth/callback`): Handles OAuth redirect from Supabase, redirects to dashboard
- **Saved course CRUD tests**: 3 new tests covering save (201), list (appears), and delete (removed) (`test_saved_courses.py`)
- **Bookmark button on dashboard**: Logged-in users see a save/unsave bookmark icon on each course card with optimistic updates

### Fixed
- **`unsaveCourse` API call**: Changed from body-based DELETE (`/api/v1/saved-courses/` + body) to URL-based DELETE (`/api/v1/saved-courses/<course_id>/`) matching the backend route
- **`getSavedCourses` return type**: Updated from `string[]` to `Course[]` to match actual backend response

### Changed
- **Dashboard CourseCard**: Refactored from single `<Link>` wrapper to `<div>` with separate link area and save button, so save/click targets are independent
- **Dashboard saved state**: Now fetches from Supabase API when session exists (was not wired at all)

### Technical Notes
- Test count: 53 → 56 (+3 saved course CRUD tests)
- Golden master: 8280 (unchanged)
- TypeScript: 0 errors
- Frontend deployed: revision `halatuju-web-00007-wd8`

## [1.2.0] - 2026-02-16 — Sprint 1: Git Housekeeping + Auth Enforcement

### Added
- **Sprint roadmap**: 15-sprint migration plan across 4 phases (`docs/roadmap/sprint-roadmap-v1.x.md`)
- **DRF permission class**: `SupabaseIsAuthenticated` for class-based views (`halatuju/middleware/supabase_auth.py`)
- **Auth enforcement**: `SavedCoursesView`, `SavedCourseDetailView`, `ProfileView` now require valid Supabase JWT
- **Auth tests**: 11 new tests covering protected endpoint rejection (403), authenticated access (200), and public endpoint openness (`test_auth.py`)
- **Git tracking**: All project code (`halatuju_api/`, `halatuju-web/`, `tools/`) now under version control
- **`.gitignore`**: Covers Node.js (`node_modules/`, `.next/`), Django (`*.sqlite3`, `staticfiles/`), and temp files (`.tmp/`)

### Changed
- **Protected views**: Replaced manual `if not request.user_id` checks with `permission_classes = [SupabaseIsAuthenticated]`
- **Migration 0002**: Renames `student_profiles` table to `api_student_profiles` (matching model's `db_table`), adds missing fields (`credit_math_or_addmath`, `credit_sci`, `credit_science_group`, `pass_sci`)

### Fixed
- **Table mismatch**: `StudentProfile.Meta.db_table = 'api_student_profiles'` didn't match migration 0001's `student_profiles` — generated migration 0002 to correct this

### Technical Notes
- DRF returns 403 (not 401) for unauthenticated requests when no `WWW-Authenticate` header is configured — this is expected behaviour
- Test count: 42 → 53 (+11 auth tests)
- Golden master: 8280 (unchanged)

## [1.1.0] - 2026-02-04

### 🎓 Major Feature: University Course Integration

Added comprehensive support for 87 Malaysian public university (IPTA) Asasi and Foundation programs across 20 institutions.

### ✨ New Features

#### Data Layer
-   **New Data Files**:
    -   `data/university_requirements.csv` - 87 university course eligibility rules
    -   `data/university_courses.csv` - Course metadata (department, field, frontend_label)
    -   `data/university_institutions.csv` - 20 IPTA universities with constituency data
-   **Course Catalog Expansion**: 727 → 814 courses (+12% growth)

#### Eligibility Engine (`src/engine.py`)
-   **Grade B Requirements**: New tier stricter than Credit C (Grade B or better)
    -   `credit_bm_b`, `credit_eng_b`, `credit_math_b`, `credit_addmath_b`
-   **Distinction Requirements**: Grade A- or better
    -   `distinction_bm`, `distinction_eng`, `distinction_math`, `distinction_addmath`
    -   `distinction_bio`, `distinction_phy`, `distinction_chem`, `distinction_sci`
-   **Complex OR-Group Logic**: JSON-based multi-subject requirements
    -   Example: "Need 2 subjects with Grade B from [Physics, Chemistry, Biology]"
    -   Supports AND logic between groups, OR logic within groups
-   **Pendidikan Islam/Moral Support**: `pass_islam`, `credit_islam`, `pass_moral`, `credit_moral`
-   **Additional Science Requirements**: `pass_sci`, `credit_sci`, `credit_addmath`

#### UI Updates (`main.py`, `src/dashboard.py`, `src/translations.py`)
-   **Institution Filter**: Added "Public University" (Universiti Awam) option
-   **Dashboard Metrics**: Expanded from 4 to 5 columns to include UA course count
-   **Translations**: Added `inst_ua` key in English/Bahasa Melayu/Tamil
-   **Grade Input**: Added "Pendidikan Islam" and "Pendidikan Moral" to Other Subjects dropdown

#### Data Manager (`src/data_manager.py`)
-   **University Data Merging**:
    -   Extracts course name and institution from `notes` column
    -   Merges with institution metadata for state/URL
    -   Maps to consistent type naming: "Universiti Awam"
-   **Type Standardization**: All institution types now use Bahasa Melayu for filter compatibility

### 🧪 Testing

-   **Golden Master Test Expansion** (`tests/test_golden_master.py`):
    -   Added 8 new student profiles (43-50) for UA requirement testing
    -   Grade B testing, Distinction testing, Complex OR-group testing
    -   Updated baseline: 5,318 → 8,280 eligible matches (+2,962)
    -   Test coverage: 50 students × 407 courses = 20,350 checks
-   **University Integration Tests** (`test_university_integration.py`):
    -   Data loading verification
    -   Eligibility engine testing with strong/weak students
    -   Complex requirements JSON parsing

### 🐛 Bug Fixes

-   **NaN Handling**: Fixed AttributeError in `check_complex_requirements()` when pandas passes NaN as float type
-   **Type Consistency**: Changed UA type from 'UA' to 'Universiti Awam' for UI compatibility
-   **Windows Console**: Removed Unicode emojis from test output for cp1252 encoding compatibility

### 📝 Documentation

-   **README.md**: Updated course catalog numbers and feature descriptions
-   **DATA_DICTIONARY.md**: Documented all 20+ new UA requirement columns and complex_requirements JSON format
-   **docs/university_integration_complete.md**: Comprehensive implementation summary

### ⚙️ Technical

-   **Engine Functions**:
    -   `is_credit_b(grade)` - Checks if grade is B or better
    -   `is_distinction(grade)` - Checks if grade is A- or better
    -   `check_complex_requirements(grades, json_str)` - Evaluates OR-group logic
    -   `map_subject_code(code)` - Maps 60+ SPM subjects to internal keys
-   **Performance**: No noticeable impact despite 12% course increase (~140KB additional data)

### 🔄 Backward Compatibility

-   All changes fully backward compatible with existing Poly/KK/TVET courses
-   New requirement columns default to 0 (not required)
-   Existing eligibility logic unchanged

## [1.0.0] - 2026-01-24

### 🚀 Initial Release
First official stable release of **HalaTuju**, the SPM Leaver Course Recommender.

### ✨ Key Features
-   **Eligibility Engine**: 
    -   Exact matching against General and Specific requirements for Polytechnics, Community Colleges, ILKBS, and ILJTM.
    -   Support for gender-specific, physically demanding, and interview-based course rules.
-   **Ranking System**: 
    -   Weighted scoring based on Student Interest (RIASEC), Work Preferences (Hands-on vs Theory), and Learning Styles.
    -   Tie-breaking logic using Credential Priority (Diploma > Certificate) and Institution Tier functionality.
-   **Dashboard**:
    -   Interactive filtering and "Tiered" display (Top 5 Matches vs Rest).
    -   Visual indicators for specific requirements (Medical checks, Interviews).
-   **Reports**:
    -   AI-generated personalized career pathway reports (Gemini Pro + OpenAI Fallback).
    -   PDF export functionality.
-   **Localization**: Full English, Malay, and Tamil language support.

### 🐛 Key Fixes & Stability
-   **Gender Logic**: Fixed regression where engine hardcoded Malay gender terms, causing rejection of eligible students using English/Tamil UI.
-   **Data Integerity**: Implemented a "Golden Master" regression test suite (`tests/test_golden_master.py`) achieving 100% integrity on 13,000+ test cases.
-   **Cleanup**: Removed unused dependency `match_jobs_rag` and unused `InsightGenerator`, consolidated imports, and verified no hardcoded secrets exist.

### ⚙️ Technical
-   **Stack**: Streamlit, Pandas, Supabase (Auth/DB), Google Gemini.
-   **Testing**: Automated Golden Master testing for the engine.
