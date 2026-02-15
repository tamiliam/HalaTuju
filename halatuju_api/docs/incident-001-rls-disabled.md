# Incident Report #001 — Row Level Security Disabled on All Tables

**Date discovered**: 2026-02-11
**Date resolved**: 2026-02-11
**Severity**: HIGH
**Duration of exposure**: ~4 days (2026-02-07 to 2026-02-11)
**Data affected**: All 10 public tables in Supabase project `pbrrlyoyyiftckqvzvvo`

---

## What Happened

All 10 tables in the HalaTuju Supabase database had Row Level Security (RLS) disabled. This means anyone who obtained the Supabase anon key (which is a publishable key, embedded in frontend code) could have:

- **Read** all course data, student profiles, grades, AI reports
- **Written** arbitrary data to any table
- **Deleted** any row from any table

The Supabase PostgREST API exposes every table with RLS disabled to anyone with the anon key. This is by design — Supabase assumes you will enable RLS and write policies.

## Impact Assessment

| Table | Rows | Sensitive? | Risk |
|-------|------|-----------|------|
| student_profiles | 30 | YES — names, phones, grades | PII exposure |
| api_student_profiles | 0 | YES (empty) | Future PII risk |
| saved_courses | 0 | Low (empty) | N/A |
| generated_reports | 0 | YES (empty) | Future PII risk |
| courses | 310 | No — public data | Data tampering |
| course_requirements | 310 | No — public data | Data tampering |
| course_tags | 226 | No — public data | Data tampering |
| institutions | 212 | No — public data | Data tampering |
| course_institutions | 633 | No — public data | Data tampering |

**Actual damage**: None detected. The anon key was not publicly exposed in any deployed frontend (the Next.js app talks to Django, not directly to Supabase). However, the key exists in the Supabase dashboard and could be extracted from Django settings if the backend were compromised.

**Worst case if exploited**: 30 student profiles (names, phone numbers, grades) could have been read by an attacker.

## Root Cause

When the database tables were created via Django migrations (2026-02-07), RLS was not enabled. Django's migration system creates tables via the `postgres` superuser role, which bypasses RLS entirely — so the developer (me) never encountered access errors that would have surfaced the missing RLS.

The Supabase Security Advisor flagged this immediately, but the warnings were not checked until the user received a weekly security email on 2026-02-11.

## Fix Applied

Two migrations applied:

1. **`enable_rls_all_tables`** — Enabled RLS on all 10 tables with appropriate policies:
   - Reference data (courses, requirements, tags, institutions, links): `SELECT` allowed for all, no write access via anon
   - User data (profiles, saved courses, reports): Only authenticated users can access their own rows (`auth.uid()` check)

2. **`cleanup_legacy_rls_policies`** — Removed 3 overly permissive legacy policies on `student_profiles` from the old Streamlit setup (including `Allow anon insert` which let anyone create profiles)

**Verification**: Supabase Security Advisor shows 0 errors, 0 warnings after fix.

## Timeline

| Time | Event |
|------|-------|
| 2026-02-07 | Tables created via Django migrations. RLS not enabled. |
| 2026-02-08 | Supabase Security Advisor flags 10 RLS errors. Weekly email queued. |
| 2026-02-11 10:00 | User receives Supabase security email. |
| 2026-02-11 10:15 | RLS enabled on all tables with proper policies. |
| 2026-02-11 10:20 | Legacy permissive policies cleaned up. |
| 2026-02-11 10:20 | Security Advisor confirms 0 errors. |

---

## Lessons Learnt

### 1. Django + Supabase is a two-layer security model

Django connects as `postgres` (superuser) and bypasses RLS. This means:
- Django's own auth/permission system handles API-level access control
- RLS handles direct Supabase API access (PostgREST)
- **Both layers must be configured independently**

When you create tables via Django migrations, you are only setting up the Django layer. You must separately configure the Supabase layer (RLS + policies).

### 2. Run the Security Advisor after every DDL change

**New rule**: After any migration that creates or alters tables, immediately run:

```
Supabase Dashboard → Advisors → Security Advisor → Rerun linter
```

Or programmatically via the MCP tool:
```
get_advisors(project_id, type="security")
```

This should be part of the deployment checklist, not an afterthought.

### 3. The anon key is not a secret

Supabase's anon key is designed to be embedded in frontend code. It is **not** a secret — it's a publishable key. The only thing protecting your data from the anon key is RLS. If RLS is disabled, the anon key becomes a master key.

This is counterintuitive if you come from a Django background where the database connection string is always secret. In Supabase, the connection is public; the security is in the policies.

### 4. Add RLS to the migration template

Every future table creation should include `ENABLE ROW LEVEL SECURITY` and at least a default-deny policy. Never create a table without RLS in Supabase.

Template for reference data:
```sql
ALTER TABLE public.new_table ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read" ON public.new_table FOR SELECT USING (true);
```

Template for user data:
```sql
ALTER TABLE public.new_table ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users own rows" ON public.new_table FOR SELECT
  USING (auth.uid()::text = user_id_column);
```

### 5. Security checks are not optional retrospective items

This was flagged by Supabase on day 1 but not acted on for 4 days. Security issues should be treated with the same urgency as broken tests — they block deployment, not get queued for later.

---

## Action Items

- [x] Enable RLS on all existing tables
- [x] Write appropriate policies (read-only for reference data, owner-only for user data)
- [x] Clean up legacy permissive policies
- [x] Verify with Security Advisor (0 errors)
- [ ] Add "Run Security Advisor" to deployment checklist in CLAUDE.md
- [ ] Ensure all future migrations include RLS
