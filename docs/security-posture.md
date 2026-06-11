# HalaTuju — Security Posture

**Last audited:** 2026-06-11 · **Method:** read-only configuration + code review (Supabase security advisors, live RLS-policy inspection, code audit, infra config). **NOT** a penetration test.
**Scope:** both products in the one database — the **course-advisory** app (browser ↔ Supabase directly, RLS-guarded) and the **B40 scholarship** app (browser ↔ Django ↔ DB, Django-guarded).

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

## 🟡 Hardening backlog (none urgent; ordered by ease)

| # | Item | Severity | Who / how |
|---|------|----------|-----------|
| 1 | Enable **leaked-password protection** (HaveIBeenPwned check) | Low | **Dashboard toggle** — Auth → Providers/Policies → Password security |
| 2 | **Back up the document Storage bucket.** Daily DB backups **exclude Storage objects** (and PITR would too) — so the 311 ID/income/STR scans in `b40-documents` currently have **NO backup**. This is the real backup gap (PITR is *not* — skip that). Set up a periodic **off-platform export** of the bucket. | **Med-High** | Manual download now (Storage → bucket → download to Drive); scheduled bucket→GCS/Drive sync later (small-change-lane) |
| 3 | Confirm tracked `halatuju-web/.env.production` + `Dockerfile` hold only `NEXT_PUBLIC_*` (no service-role key / DB URL) | Med | Read-only check (done in this audit — see note) |
| 4 | Add **request rate-limiting** on sensitive custom DRF endpoints (login itself is covered by Supabase's built-in limits) | Med | **Code** — DRF throttles; small-change-lane (test + deploy) |
| 5 | Tighten `field-images` public-listing; add captcha/limit to the anonymous contact form | Low | **Code/policy** — small-change-lane |
| 6 | Add **breach/anomaly detection** (action-audit data exists; nothing alerts on a mass-read) | Med | **Code/infra** — design + small-change-lane |
| 7 | Add explicit **deny policies** on the deny-all tables to match the repo's own "RLS + policies" standard | Low | **Migration** — clarity only; behaviour already deny-all |

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
