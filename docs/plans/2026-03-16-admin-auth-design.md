# Admin Auth & Session Isolation — Design

## Goal

Completely separate admin authentication from student authentication. Admin and student sessions are independent — even if the same person holds both roles, they log in separately and get separate sessions.

## Data Model

### New table: `partner_admins`

| Column | Type | Notes |
|--------|------|-------|
| `id` | BigAuto PK | |
| `supabase_user_id` | CharField(100), unique, nullable | From JWT `sub`. NULL until first login. |
| `org` | FK → PartnerOrganisation, nullable | NULL for super admin |
| `is_super_admin` | Boolean, default False | Sees all students, can invite |
| `name` | CharField(200) | Display name |
| `email` | EmailField, unique | Must match Supabase Auth email |
| `created_at` | DateTimeField | |

### Changes to PartnerOrganisation

Add optional fields:
- `contact_person` (CharField, blank)
- `phone` (CharField, blank)

### Removed from StudentProfile

- `admin_org_code` field deleted (migration)

### RLS

Enable on `partner_admins` with read-own-row policy.

## Auth & Session Isolation

### Second Supabase client

`getAdminSupabase()` in `lib/admin-supabase.ts`:
- Same Supabase project URL and anon key
- Different `auth.storageKey`: `halatuju_admin_session`
- Admin and student sessions use different localStorage keys — fully independent

### Admin auth context

`AdminAuthProvider` in `lib/admin-auth-context.tsx`:
- Wraps only `/admin/*` routes
- Reads from admin Supabase client
- On load, checks `partner_admins` via `/api/v1/admin/role/`

### Login page — `/admin/login`

- Email + password form (Supabase `signInWithPassword`)
- Google sign-in button (redirect to `/admin/auth/callback`)
- "Forgot password?" → Supabase `resetPasswordForEmail`
- After login, checks `/api/v1/admin/role/` — if not an admin, shows error and signs out

### Callback — `/admin/auth/callback/route.ts`

Handles Google OAuth redirect, exchanges code, redirects to `/admin`.

## Invite Flow

### Super admin invite page — `/admin/invite`

- Form: Organisation (dropdown or "New"), admin name, admin email
- If new org: inline fields for org name, contact person, phone
- Submit calls `POST /api/v1/admin/invite/`

### Backend invite endpoint

- Super admin only
- Creates PartnerOrganisation if new
- Calls Supabase Admin API `inviteUserByEmail(email)` — sends magic link
- Creates `partner_admins` row with `supabase_user_id=NULL`
- Service role key required (Cloud Run env var `SUPABASE_SERVICE_ROLE_KEY`)

### First login resolution

- Admin clicks invite link → sets password → redirected to `/admin/auth/callback`
- Backend `/api/v1/admin/role/` checks by UID first, then falls back to email match → backfills `supabase_user_id`

## Backend Changes

### PartnerAdminMixin rewrite

- Looks up `partner_admins` table (not StudentProfile)
- Super admin: sees all students
- Partner admin: sees only their org's referred students

### Endpoints

- `GET /api/v1/admin/role/` — role check with email fallback + UID backfill
- `GET /api/v1/admin/dashboard/` — unchanged logic, new auth source
- `GET /api/v1/admin/students/` — unchanged
- `GET /api/v1/admin/students/<id>/` — unchanged
- `GET /api/v1/admin/students/export/` — unchanged
- `POST /api/v1/admin/invite/` — new, super admin only
- `GET /api/v1/admin/orgs/` — new, list organisations for invite dropdown

### Password reset

Frontend calls Supabase `resetPasswordForEmail` directly (no backend needed).

## Frontend Structure

### New files

- `lib/admin-supabase.ts` — isolated Supabase client
- `lib/admin-auth-context.tsx` — AdminAuthProvider + useAdminAuth()
- `app/admin/login/page.tsx` — email/password + Google + forgot password
- `app/admin/auth/callback/route.ts` — OAuth redirect handler
- `app/admin/invite/page.tsx` — invite form (super admin only)

### Modified files

- `app/admin/layout.tsx` — AdminAuthProvider, role check, redirect to login
- `lib/admin-api.ts` — use admin token
- `components/AppFooter.tsx` — Admin link stays (login gate handles access)

### Admin navigation

Dashboard | Pelajar | Invite (super admin only) | Log Out

## Out of Scope

- Admin profile/settings page
- Revoking admin from UI (use Django admin or DB)
- Admin editing org details from UI
- Audit log
- Multi-org admin (one admin = one org)

## Cost

Zero additional — Supabase free tier covers email auth + invite emails.
