# Retrospective — B40 Phase E/F Sprint 5: Reviewer profile (F6)

**Date:** 2026-06-09
**Branch:** `main` (held local, not pushed — deploy owner-gated, batched for go-live)
**Migration:** `0051_reviewerprofile` (new model — apply via Supabase MCP + enable RLS at deploy; TD-098)

## What Was Built

A reviewer's own credentials + contact details, surfaced as new cards on the **existing** `/admin/profile` page
(rendered only for `reviewer`/`super`; a `viewer` never sees them).

- **Model** — new `ReviewerProfile` in `apps/scholarship`: a OneToOne to `courses.PartnerAdmin` (mirroring the app's
  existing cross-app FK to `courses`) with `highest_qualification`, `university`, `graduation_year`, `field_of_study`,
  and the sensitive staff PII `phone`/`address`. **No password field** (auth is Supabase's). `db_table =
  'reviewer_profiles'`.
- **Endpoint** — self-scoped `GET/PATCH /api/v1/admin/reviewer-profile/` (`ReviewerProfileView`, `_AdminBase`): always
  resolves the calling admin's own row via `get_admin` (`get_or_create`), so one reviewer can never read or edit
  another's. Reviewer + super only (`has_role(admin, 'reviewer')`); a viewer gets 403 and no row is created.
- **Serializer** — a narrow `ReviewerProfileSerializer` exposing only the six editable fields (the FK is never
  exposed or accepted; a plausible-year validator on `graduation_year`).
- **Frontend** — `getReviewerProfile`/`updateReviewerProfile` + a role-gated two-card section ("Reviewer credentials"
  + "Contact details 🔒") on `/admin/profile`, saved by the page's single Save button (one submit → admin-profile
  PATCH + reviewer-profile PATCH). Trilingual `admin.reviewer.*` (Tamil first-draft, TD-097).
- **Stitch** — `My profile — Reviewer Settings` generated + owner-approved before the template was coded.

## What Went Well

- **PII isolation by construction.** `phone`/`address` live in their own table with their own (deploy-time) RLS and a
  narrow serializer; they are reachable by **no** outward student/sponsor serializer because the model is separate —
  the structural-data-wall pattern, not a remembered exclude.
- **Self-scoping is structural, tested.** The endpoint only ever resolves the caller's own row; a dedicated test
  (`test_self_scoped_isolation`) plants another reviewer's PII and asserts GET never returns it and PATCH never
  touches it.
- **Reframed greenfield → extension cheaply.** A 30-second `Glob` of `admin/**/page.tsx` revealed the `/admin/profile`
  page + `AdminProfileView` already existed, turning "build a new page + model" into "extend an existing surface" and
  surfacing the dependency-direction call before any code was written.

## What Went Wrong

- **The Stitch generation timed out and didn't appear in `list_screens` after two polls — nearly burned time chasing
  it.** *What happened:* `generate_screen_from_text` timed out client-side (the known content-dense behaviour); two
  `list_screens` polls didn't show the new "My profile" screen (the list is paged/capped ~30 items and the gen
  persisted late). *Why:* Stitch persists a timed-out gen asynchronously, and `list_screens` isn't a reliable way to
  find a specific just-created screen. *Fix (and the system change):* instead of a poll loop, I presented the design as
  an `AskUserQuestion` ASCII preview for sign-off; the owner replied with the actual preview `node-id`, which
  `get_screen` resolved for a faithful build. Captured as a lesson — present a concrete mock rather than poll, and let
  the owner paste the node-id.

## Design Decisions

- **`ReviewerProfile` in `apps/scholarship` (cross-app FK) with its own endpoint, not fields on `courses.PartnerAdmin`
  / a widened `courses.AdminProfileView`.** (Logged in `decisions.md`.) Keeps the dependency direction correct
  (scholarship→courses, never the reverse), keeps the sensitive PII in its own RLS'd table, and leaves the existing
  org/name profile view untouched. The cost is a second endpoint + a second fetch on the one page.
- **"Highest qualification" stays a free-text input.** The Stitch render showed a dropdown, but the field is a free
  `CharField`; a text input in the same slot is faithful to the approved *layout* and avoids an enum + extra i18n.

## Numbers

- **Backend:** 892 scholarship pytest (+10 new) green; migration check clean (`0051`).
- **Frontend:** `next build` clean (`/admin/profile` 4.08 kB); 276 jest green (page is render-only — covered by build
  typing, not jest).
- **i18n:** parity 2325 × en/ms/ta (+13 `admin.reviewer.*`; Tamil first-draft, TD-097).
- **Files touched:** ~12 (model + migration + serializer + view + url + test BE; api-client + page + 3 message files FE).
- **Deploys:** 0 (held; owner-gated batch for go-live).
- **Carried:** TD-097 (reviewer Tamil refine), TD-098 (apply `0051` via MCP + enable RLS at deploy).
