# HalaTuju — Security Posture

**Last audited:** 2026-06-11 · **Method:** read-only configuration + code review (Supabase security advisors, live RLS-policy inspection, code audit, infra config). **NOT** a penetration test.
**Scope:** both products in the one database — the **course-advisory** app (browser ↔ Supabase directly, RLS-guarded) and the **B40 scholarship** app (browser ↔ Django ↔ DB, Django-guarded).

> **Hardening shipped 2026-06-12 — backlog items A–E all LIVE.** Document-vault off-platform backup (A), DRF rate-limiting (B), Cloudflare Turnstile captcha on every auth entry point + the contact form (C), access-anomaly detection on applicant-record reads (D), and explicit deny policies on the deny-all tables (E). Leaked-password protection (item 1) also enabled. **All seven hardening-backlog items are now closed.** See the backlog table below for per-item status.

> Re-run this audit after any migration or auth/storage change. The repo's pre-deploy checklist already requires the Supabase Security Advisor; this doc is the broader companion. Re-run commands are in the appendix.

---

## Overall verdict
**Strong for a small-organisation build. No critical holes found.** The common ways an app like this gets breached — a leaky public key, public document storage, one user reading another's records, SQL injection, cross-site scripting — were each checked and are **closed**. What remains is *hardening*, not *holes*.

## ✅ Verified solid

| Area | Finding | How it was verified |
|------|---------|---------------------|
| **Data isolation — advisory** | User tables (`api_student_profiles`, `saved_courses`, `admission_outcomes`, `generated_reports`, `email_verifications`) enforce own-row **read** access (`auth.uid() = student_id`) **and** carry an explicit "block anonymous users" policy. **Since 2026-10-05 they are read-only to students through the public key** — see the write-integrity note below. | `pg_policies` inspection of `using/with_check` expressions |
| **Data isolation — scholarship** | Sensitive tables (`scholarship_applications`, `applicant_documents`, `consents`, `funding_needs`, `interview_sessions`, `semester_results`, sponsor/*) are **RLS deny-all** to the public key; reachable only via Django, which scopes every query to the caller (`filter(pk=pk, profile_id=request.user_id)`) — no IDOR. | Supabase advisor + `views.py`/`views_admin.py` review |
| **Document privacy** | All 311 ID/income/STR scans are in the **private** `b40-documents` bucket (`public=false`). | `storage.buckets` query |
| **Master key safety** | The `service_role` key is **not** in the frontend; all three clients use only `NEXT_PUBLIC_SUPABASE_ANON_KEY`. | Read `lib/supabase.ts`, `admin-supabase.ts`, `sponsor-supabase.ts` |
| **Injection** | The only raw SQL (`courses/views.py` profile-claim) is parameterized with `%s`; table/column names come from a hardcoded list, not user input. | Code review |
| **Cross-site scripting** | No dangerous raw-HTML-injection sinks in the frontend (checked the React raw-HTML prop + direct DOM HTML writes — none present). | Grep `halatuju-web/src` |
| **Session isolation** | Separate PKCE auth clients (student/admin/sponsor) with isolated storage keys, to stop OAuth sessions bleeding across roles. | Code review |
| **Defence in depth** | `NricGateMiddleware` blocks data access without a verified identity. | Code review |
| **Backups (database)** | Supabase **Pro** — **daily backups verified** (last 7 days present + restorable). PITR is a paid add-on (~US$100/mo); **deliberately not enabled** — cost not justified at this write-volume (worst case without it = ~24h of a few applications, recoverable). | `get_organization` + dashboard (Database → Backups) |
| **Process** | Documented pre-deploy security checklist + RLS discipline, written after a prior RLS incident (`docs/incident-001-rls-disabled.md`). | `halatuju_api/CLAUDE.md` |

## 🟡 Hardening backlog — status (as of 2026-06-12)

| # | Item | Severity | Status |
|---|------|----------|--------|
| 1 | Enable **leaked-password protection** (HaveIBeenPwned check) | Low | ✅ **Done** — Auth → Attack Protection toggle ENABLED |
| 2 | **Back up the document Storage bucket** (daily DB backups exclude Storage objects). | **Med-High** | ✅ **Done (item A)** — `backup_documents` management command mirrors `b40-documents` → GCS `halatuju-doc-backups` (versioned), weekly Cloud Scheduler (Mon 03:00 MYT), incremental/resumable; 320 docs backfilled |
| 3 | Confirm tracked `Dockerfile` / env hold only `NEXT_PUBLIC_*` (no service-role key / DB URL) | Med | ✅ **Done** — verified; the only added build var is the **public** Turnstile site key |
| 4 | Add **request rate-limiting** on sensitive custom DRF endpoints | Med | ✅ **Done (item B)** — proxy-aware DRF throttles (`halatuju/throttling.py`): anon/upload/public-count scopes |
| 5 | Add **captcha/limit to the anonymous contact form** (+ tighten `field-images` listing) | Low | ✅ **Done** — captcha (item C): contact form posts to the `contact-submit` Edge Function (Turnstile-verified, service-role insert, anon INSERT revoked). `field-images` listing: dropped the over-broad `storage.objects` SELECT policy so the public bucket is readable-by-URL but no longer **enumerable** (verified: public read 200, anon list `[]`). SQL: `docs/security/field-images-revoke-list.sql` |
| 6 | Add **breach/anomaly detection** (action-audit data exists; nothing alerts on a mass-read) | Med | ✅ **Done (item D)** — `AdminApplicationDetailView` emits a per-read audit line; Cloud Logging metric `applicant_record_reads` (per `admin_id`) + alert policy email the admin if one account reads **> 30 records in 10 min**. Config: `docs/security/monitoring/` |
| 7 | Add explicit **deny policies** on the deny-all tables | Low | ✅ **Done (item E)** — `Backend service role only` policies on 19 tables (`docs/security/deny-all-policies.sql`) |

**Also shipped with C:** Cloudflare Turnstile captcha (invisible, Managed mode) now gates **every** Supabase Auth entry point — student anonymous sign-in, sponsor/admin sign-in, sign-up, password reset — enforced via the project-wide captcha toggle. Rollout/rollback: `halatuju_api/docs/security/turnstile-rollout.md`.

**Remaining:** nothing on this backlog — all items closed. (Standing recommendation: an independent pen-test before scaling the user base.)

## Write integrity — correction 2026-10-05
The 2026-06-11 audit checked that a student could not **read** another student's row. It did not check what a student could **write** to their own row. Eight leftover policies let a signed-in student insert, update or delete their own rows in `api_student_profiles`, `admission_outcomes`, `generated_reports` and `saved_courses` directly through the public key — bypassing every rule Django enforces (NRIC verification, income/benefit flags, verification flags, the parent-phone signing freeze). Found by the request #26 adversarial review.

- **Fixed 2026-10-05** (owner ran the SQL): all eight dropped. Remaining policies: the RESTRICTIVE "block anonymous users", own-row SELECT, and service-role full access (role `service_role` only). RLS stays on for all four tables. Nothing legitimate used them — the web app makes zero direct table calls.
- **Exposure check:** edge logs (retained from 2026-07-07) show **no** direct `/rest/v1/` write by anyone, ever, in that window. The only direct calls were: our own service-key reads from Malaysia (2026-07-08, 07-09), and two outside probes with the public key that got nothing back (2026-07-31 Google Cloud US: 404 + 0 rows; 2026-09-12 netcup DE: 401).
- **Undo:** `docs/security/2026-10-05-restore-student-write-policies.sql` recreates the eight exactly. Run it only if something breaks.
- **Re-audit rule:** the policy check in the appendix must now look at `cmd` (INSERT/UPDATE/DELETE), not only `qual`.

## Release review — v3.0.0, 2026-10-06
The release workflow's security and access review (`Settings/_workflows/release.md` step 3). A
read of the code, the settings and this repository's records, plus one dated read-only measurement
of the database by the lead (below). Everything else here is **what the repository records**, dated
by the sprint that recorded it — not a fresh reading of production. Check the list at the end of this
section before relying on any of it. Release notes: `docs/releases/release-notes-v3.0.0.md`.

**Roles** (`PartnerAdmin.role`, `apps/courses/models.py`; matrix `docs/scholarship/role-matrix.md`):
- `super` — the platform owner; everything, across organisations; the only role on the platform
  surfaces (Dashboard, Students directory, Course Data).
- `org_admin` — one organisation's lead: its B40 reads, the QC gate, staff management for its own
  organisation only.
- `admin` (view-only), `reviewer` (only the applicants assigned to them), `qc` (the QC gate only),
  `finance` (the payment-run checker; no applicant data beyond the payments allowlist), `partner`
  (a referral organisation's own students — referral, not tenancy).
- `is_super_admin` is still kept beside `role` (TD-064). Sponsors are a separate `Sponsor` identity
  with their own Supabase client; a sponsor never sees a student's identity (allowlist serializers).

**Fences:**
- **Organisation fence** — every admin view inherits `_AdminBase`; `_org_scoped` / `_org_allows`
  decide. A guard fails the build if a wired route is not driven by a test, and the fence scan
  covers `views_sponsor.py` (TD-258 was found that way and fixed 2026-09-18).
- **Gift gate** — `?programme=<code>` narrows inside the fence and never widens it; an unknown or
  cross-tenant code is 404. An **organisation-less super must name a gift** on the payment-run list,
  the funding summary and Spending (`400 programme_required`, TD-334, 2026-10-05). Open: the
  Programme Overview still pools platform-wide money for such a super (TD-336); Sponsors and Sources
  do not narrow by organisation yet (TD-228).
- **Referral fields** (`PartnerAdmin.org`, `referred_by_org`) are never used for access control.
- **Identity** — the IC claim is a link row behind a code to an already-verified contact; the endpoint
  never names the holder; staff and sponsor identity resolve on the real token subject
  (`request.auth_sub`), never through an alias (TD-254/TD-259, 2026-09-19).

**RLS state:**
- **Measured 2026-10-06 (the lead, read-only):** 94 tables in `public`, RLS on for all 94; 86 policies
  on 79 tables; 60 of them `service_role` policies. The ONLY policies for the `authenticated` role are
  five RESTRICTIVE "Block anonymous users" policies (`admission_outcomes`, `api_student_profiles`,
  `email_verifications`, `generated_reports`, `saved_courses`; qual
  `coalesce((auth.jwt()->>'is_anonymous')::boolean, false) is false`). **No permissive write policy for
  `authenticated` or `anon` remains.**
- The repository records the event trigger `rls_auto_enable` (since 2026-09-16) switching RLS on for
  every new table at creation; it adds no policy. Scholarship and sponsor tables are recorded as
  deny-all to the public key with an explicit `service_role` policy.
- The four advisory tables' eight student write policies were dropped on 2026-10-05 (the
  write-integrity correction above); the restore script is only an undo. The re-audit query in the
  appendix must read `cmd`, not only `qual`.

**Keyless Google (TD-125, TD-329):**
- Meet, Drive and Sheets act as `MEET_ORGANISER_EMAIL` through domain-wide delegation. By design
  (`apps/scholarship/google_dwd.py`) the api's runtime service account signs the delegation assertion
  as `halatuju-meet@…` through the IAM Credentials API (`GOOGLE_DWD_SERVICE_ACCOUNT`), which needs
  `roles/iam.serviceAccountTokenCreator` on that account.
- Recorded 2026-10-04 (TD-329): the user-managed key was deleted, leaving only Google's two
  system-managed keys; the env var `GOOGLE_MEET_SA_JSON` and the code path are gone (the code half is
  pinned by `test_google_dwd.test_the_key_path_is_gone`).
- Recorded 2026-10-04: the alert policy "Google Workspace keyless path failed (Sheets / Drive / Meet)"
  (`alertPolicies/10163327245873580870`) emails tamiliam@gmail.com, at most once an hour, on a
  `severity>=WARNING` log line from those paths. It can only fire because logs carry a real
  `severity` since TD-290 (2026-10-03).

**Secrets inventory (names only; values live in Cloud Run env vars or a provider's dashboard):**
- Cloud Run `halatuju-api`: `SECRET_KEY`, `DB_PASSWORD` (with `DB_HOST`/`DB_USER`), `SUPABASE_JWT_SECRET`,
  `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_CLOUD_VISION_API_KEY` (if
  set), `EMAIL_HOST_PASSWORD` (Brevo SMTP), `CRON_SECRET`, `TWILIO_AUTH_TOKEN` (with
  `TWILIO_ACCOUNT_SID`), `VIRCLE_AIRTABLE_PUSH_URL`, `VIRCLE_AIRTABLE_SECRET`, `SENTRY_DSN`.
- Outside Cloud Run: Supabase Auth's own SMTP password (Brevo — rotate it together with
  `EMAIL_HOST_PASSWORD`), the Turnstile secret (Supabase Auth captcha), the Twilio and Vircle
  dashboards.
- Public by design (web build): `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_TURNSTILE_SITE_KEY`.
- No secret is in a tracked file; local development uses a gitignored `.env`. No service-account
  key exists anywhere.

**Audit lines:**
- 41 distinct `AUDIT <event>` log lines (staff and money actions: QC decisions, closures, award amounts,
  wallet ids, programme and intake-year changes, theme publishes, NRIC-lock releases, invitation
  cancels, spend-category corrections, …).
- `AUDIT applicant_detail_read` feeds the `applicant_record_reads` metric and its alert (> 30 reads by
  one account in 10 minutes).
- `ProfileClaimEvent` is the append-only record of every IC-claim step; `GuardianContactChange`
  records every parent-phone change and parent call (request #26).
- ICs never go into an application log.

**Open security-relevant debt** (all in the register): TD-348 (two submits racing the
one-application rule), TD-367 (a payment run can pay a closed student), TD-365 (a close and a fund can
race), TD-336 and TD-228 (organisation scope gaps above), TD-058 (no Django bookkeeping tables in
production). The standing recommendation stands: an independent penetration test before the user
base grows.

**Verify live before relying on this** (all read-only; `--account tamiliam@gmail.com --project
gen-lang-client-0871147736` on every gcloud call):
1. `SELECT tablename, policyname, roles, cmd, permissive FROM pg_policies WHERE schemaname='public'
   ORDER BY cmd, tablename;` — no permissive INSERT/UPDATE/DELETE/ALL policy for `authenticated` or `anon`.
2. Supabase Security Advisor (`get_advisors(project_id="pbrrlyoyyiftckqvzvvo", type="security")`) — 0 errors.
3. `SELECT evtenabled FROM pg_event_trigger WHERE evtname = 'rls_auto_enable';` — `'O'`.
4. `gcloud iam service-accounts keys list --iam-account halatuju-meet@gen-lang-client-0871147736.iam.gserviceaccount.com --managed-by user`
   — empty.
5. `gcloud alpha monitoring policies describe projects/gen-lang-client-0871147736/alertPolicies/10163327245873580870`
   — `enabled: true`, and its notification channel still points at tamiliam@gmail.com.

## ⚠️ Caveats (state these to anyone who asks)
- This is a **static/config audit, not a penetration test.** Before scaling the user base, commission an **independent pen-test** — for government-adjacent PII (B40/NRIC/STR) it's the right assurance layer and it exercises the *running* system in ways a code review can't.
- Security is **ongoing** — patching, monitoring, incident response — not a one-time stamp. Re-run this audit (appendix) after every migration or auth/storage change.

---

## Appendix — how to re-run each check
```text
# Supabase security advisors (RLS gaps, exposed buckets, anon policies)
MCP: get_advisors(project_id="pbrrlyoyyiftckqvzvvo", type="security")

# RLS coverage per table
SELECT c.relname, c.relrowsecurity,
  (SELECT count(*) FROM pg_policy p WHERE p.polrelid=c.oid) AS policies
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relrowsecurity, c.relname;

# RLS policy expressions for the advisory user tables
SELECT tablename, policyname, roles, cmd, qual, with_check FROM pg_policies
WHERE schemaname='public' AND tablename IN
 ('api_student_profiles','saved_courses','admission_outcomes','generated_reports');

# Storage bucket privacy
SELECT id, public, (SELECT count(*) FROM storage.objects o WHERE o.bucket_id=b.id)
FROM storage.buckets b;

# Frontend uses only the anon key (should return ANON, never SERVICE_ROLE)
grep -rn "SUPABASE_.*KEY" halatuju-web/src/lib/*supabase*.ts

# Cross-site-scripting sinks: grep halatuju-web/src for the React raw-HTML prop
#   and direct DOM HTML writes (none found in this audit)

# Backup tier
MCP: get_organization(id="wgkfortqdceiixptcijz")   # plan should be >= pro
```
