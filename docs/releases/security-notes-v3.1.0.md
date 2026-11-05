# HalaTuju v3.1.0 - Security and access notes

Release review for 2026-11-05 (`Settings/_workflows/release.md` step 3). Builds on the v3.0.0 review in `docs/security-posture.md` ("Release review - v3.0.0"). This is what the repository records; it is not a fresh read of production.

## What changed since v3.0.0
- **Roles and hats.** `PartnerAdmin.role` is unchanged (super, org_admin, admin, reviewer, qc, finance, partner, plus staff-mentor). A person can now carry several hats (Team tables T1); permissions are read through the v2 permission catalogue with aliases (T5a). Matrix: `docs/scholarship/role-matrix.md`.
- **Pages open by keys (T5c part 1).** A page's door is a permission key, not a role name. The Overview landing is the one deliberate exception: it has no key (every staff login opens it), the owner ruled this 2026-11-04. What it shows is decided by `my_programmes.lands` and by `my_pending` per card: a card the caller may not see is absent.
- **Fences.** `GET admin/scholarship/my-programmes/` and `my-pending/` are organisation-scoped; a reviewer sees only programmes with a case of hers, a mentor only programmes of current mentees; `?intake=` side door closed; a reviewer opening another programme gets 404. QC separation (`qc_separation.barred_ids`) is applied to the QC card. Mentors log in (Sprint 7a) with the self-mentoring guard `mentoring.is_the_student`.
- **Auth flow.** Unchanged: Supabase JWT for staff, students and sponsors; Turnstile on sign-in; source sign-in arc (2026-10-30) adds code-linked source sign-in.
- **Data classes (PII).** New personal data: staff profile cards (photo, job title, phone), mentoring meeting logs, student survey answers, announcements, the maintenance activity log. All sit behind the organisation fence; none is served to sponsors.
- **Secrets, by name only.** No new secret classes. Existing names and where they live are listed in `docs/deployment.md` (Cloud Run environment variables; local gitignored `.env`).

## Open security items
- **Dependency advisories (TD-506), after the pre-v3.1.0 security patch.**
  - Fixed: `next` 14.2.0 to 14.2.35 (exact pin; the critical advisory and the other fixes available inside 14.2.x); `eslint-config-next` to match; image optimiser turned off (`images.unoptimized`); `npm audit fix` without `--force` (nanoid, picomatch and other in-range fixes).
  - Left: the remaining Next.js advisories are fixed only in Next 15.5.28 or later, a major upgrade (React 19 era, async request APIs) that is the FIRST audit fix sprint. Python: Pillow 11.3.0, pillow-heif 0.22.0 and pypdf 5.9.0 are deferred to the audit (pypdf pinned on purpose; Pillow touches document reading, so it needs a MODEL_VERSION check).
  - `npm audit --omit=dev` after the patch: 4 left (1 critical, 1 high, 2 moderate): `next` (critical; GHSA-h25m-26qc-wcjf, -q4gf-8mx6-v5v3, -8h8q-6873-q5fj, -c4j6-fc7j-m34r, -36qx-fr4f-26g5, -m99w-x7hq-7vfj, -89xv-2m56-2m9x, -p9j2-gv94-2wf4, -p293-qw3h-jr36, -2xp9-vwfh-vxw4, -2464-fhr4-w9xw, -p3m5-59mp-jv5r), `postcss` (high; the copy nested inside Next; GHSA-6g55-p6wh-862q, GHSA-r28c-9q8g-f849; clears with the Next upgrade), and two moderates (`@tailwindcss/typography`, `postcss-selector-parser`).
  - Exposure while they remain: there is no middleware (the middleware-bypass advisories need one); the image optimiser is off, so its advisories cannot be reached; the host is Linux (Cloud Run), which excludes the Windows-only items. See `npm audit --omit=dev` result in the sprint hand-back.
- Overview card doors differ slightly from page doors (TD-503, TD-504); read-only exposure of counts only, no applicant data.
- No sign-in sandbox for non-admin roles (audit completeness lens).
- Earlier items unchanged: TD-487, TD-488, TD-496, TD-497, TD-499.
