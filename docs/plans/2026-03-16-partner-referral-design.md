# Partner Referral & Admin Portal — Design Document

**Date:** 2026-03-16
**Status:** Approved

## Goal

Enable partner organisations (CUMIG, etc.) to track students they onboard via HalaTuju, and provide them a read-only admin portal to view their students' progress.

## Architecture

Two features sharing one data model:

1. **Referral capture** — silent auto-tagging via `?ref=code` URL param, with optional fallback chips on the IC page
2. **Partner admin portal** — same Next.js app, role-gated pages showing partner's students

## Data Model

### New model: `PartnerOrganisation`

| Field | Type | Notes |
|-------|------|-------|
| `code` | CharField(50), unique | URL slug: `cumig`, `partner2` |
| `name` | CharField(200) | Display name: "CUMIG" |
| `contact_email` | EmailField, nullable | For admin login matching |
| `is_active` | BooleanField, default=True | Soft disable |

### New fields on `StudentProfile`

| Field | Type | Notes |
|-------|------|-------|
| `referral_source` | CharField(50), nullable | Raw ref code or chip value |
| `referred_by_org` | FK(PartnerOrganisation), nullable | Set when ref code matches a partner |

### Supabase auth user metadata

| Field | Values |
|-------|--------|
| `role` | `student` (default), `partner_admin` |
| `org_code` | Partner's code, e.g. `cumig` |

## Referral Capture Flow

### Primary path: URL auto-tagging

1. Partner distributes link: `halatuju.com/?ref=cumig`
2. Landing page reads `ref` query param → saves to `localStorage` (`KEY_REFERRAL_SOURCE`)
3. Persists across sign-up (shared device at roadshow = multiple students tagged)
4. On profile sync (end of onboarding), sends `referral_source` to backend
5. Backend looks up `PartnerOrganisation` by code → sets `referred_by_org` FK
6. If code doesn't match any partner (e.g. `whatsapp`, `google`), stores string only (analytics)

### Fallback: Optional chips on IC page

- Only shown if `KEY_REFERRAL_SOURCE` is not already set in localStorage
- Small pill chips below IC number and name fields: WhatsApp | Google | FB/IG | CUMIG | Lain-lain
- Label: "Bagaimana anda tahu tentang HalaTuju? (Pilihan)"
- Selected chip saves to `KEY_REFERRAL_SOURCE`
- Skippable — student can proceed without selecting

### UI Reference

- Approved mockup: `docs/ic_referral_a.png` (Stitch screen "HalaTuju IC Verification & Referral A")
- Stitch screen ID: `39d5d8188aac476bae8e906b89457f70`

## Partner Admin Portal

### Authentication

- Same Supabase auth as students (email/password)
- `role: partner_admin` + `org_code` in user metadata
- Frontend checks role → shows admin UI instead of student dashboard
- Partners created manually (no self-registration in v1)

### Pages

| Route | Content |
|-------|---------|
| `/admin` | Dashboard — total students, completed onboarding, top fields |
| `/admin/students` | Student list — name, IC, Angka Giliran, state, exam type, date joined |
| `/admin/students/[id]` | Student detail — grades, saved courses, fit scores, field of interest |

### CSV Export

- Button on student list page: "Download CSV"
- Endpoint: `GET /api/v1/admin/students/export/`
- Contents: name, full IC, Angka Giliran, state, exam type, grades summary, top 3 saved courses, field of interest, date joined
- Scoped to partner's org (backend enforced)

### Access Control

- Partners see ONLY students where `referred_by_org` matches their org
- Read-only — no editing student data
- Full IC and Angka Giliran visible (partners need these to follow up with students)
- Backend enforces via `referred_by_org` filter on all queries

## Scope

### In scope (v1)

- `PartnerOrganisation` model + referral fields on `StudentProfile`
- `?ref=code` auto-tagging via URL + localStorage persistence
- Optional fallback chips on IC page (Design A approved)
- Partner admin role in Supabase auth
- Admin pages: dashboard stats, student list, student detail
- CSV export with full IC, Angka Giliran, grades, saved courses
- RLS on Supabase tables

### Out of scope (future)

- Partner self-registration
- Partners onboarding students on their behalf (proxy sign-up)
- Multi-partner attribution (one student, one source)
- Push notifications or messaging between partner and student
- Username/password login (planned separately)
