# Supabase row-level and storage policy review (advisor action 4, part 2)

Date: 13 Nov 2026. Read-only catalogue queries on the live database, plus the Supabase security advisor.

## How access works

- The Django API connects as the database owner. That role bypasses row-level security (RLS).
  So the real access control for the app is in Django. Part 1 of action 4 (the role-by-endpoint test) covers it.
- RLS only matters for direct calls to the Supabase data API with the public (anon) key or a user's login token.
  The web app uses Supabase only for login and for signed document links.

## Results

| Check | Result |
| --- | --- |
| Tables in `public` with RLS off | 0 of 135 |
| Tables with no policy at all | 0 (every table has at least the service-role policy) |
| Policies that give `anon` or `authenticated` access to private data | 0 |
| Public-read policies (`qual = true`) | 12, all course and field reference data (courses, institutions, requirements, tags, occupations, field taxonomy, field images). Public by design. |
| Own-row read policies | 6: admission_outcomes, api_student_profiles, generated_reports, saved_courses, email_verifications, partner_admins. Each matches `auth.uid()` to the row owner. |
| "Block anonymous users" policies | 5, all RESTRICTIVE (they narrow access; they never grant it). |
| Functions in `public` callable by anon/authenticated | 0 (`rls_auto_enable` only; no execute grant). |
| `storage.objects` policies for anon/authenticated | 0. Only the service role can read or write files. |
| `b40-documents` bucket | private, 25 MB limit, 13 file types (SEC-18 applied). |
| `field-images` bucket | public, 5 MB limit, 3 image types. Public by design. |
| `field-images-concept` bucket | public, NO size or type limit. Writes are service-role only. |

Supabase security advisor: 21 WARN "anonymous access policies". All are the public-read reference tables, the own-row policies above, and Supabase's own `cron` tables. None exposes private data: an anonymous login gets a new user id that owns no rows.

## Verdict

No hole found. RLS and storage policies keep private data away from the public key and from logged-in users.

## Tidy-ups (low; owner runs any DDL)

1. L1 `field-images-concept`: add a size limit and image-only types, or delete the bucket if unused.
2. L2 Old backup tables still hold copies of live data: `partner_org_programme_backup_td379`, `partner_org_show_in_apply_backup_sources_d`, `referral_chip_backup_20261019`, `referral_link_backup_20261009`, `student_profile_source_backup_sources_d`. Service-role only, but drop them when no longer needed (data minimisation).
3. L3 `partner_admins` own-row policy is on role `public`; scope it to `authenticated` and add the restrictive anonymous block, to match the other own-row tables.
4. L4 Check in the Supabase dashboard that anonymous sign-ins are OFF if the app does not use them. That clears most advisor warnings.
