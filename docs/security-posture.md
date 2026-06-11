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
| **Data isolation — advisory** | User tables (`api_student_profiles`, `saved_courses`, `admission_outcomes`, `generated_reports`, `email_verifications`) enforce own-row access (`auth.uid() = student_id`) **and** carry an explicit "block anonymous users" policy. | `pg_policies` inspection of `using/with_check` expressions |
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
