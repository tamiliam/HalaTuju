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
- **Dependency advisories (TD-506).** `npm audit --omit=dev`: 1 critical (Next.js 14.2.0, many advisories; fix is a major bump), 5 high (incl. nanoid, picomatch: `npm audit fix`). `pip-audit`: Pillow 11.3.0 and pypdf 5.9.0 (pypdf is pinned on purpose for the STPM certificate reader; upgrading needs the eval corpus re-run). Needs the owner's ruling on an upgrade sprint; the workflow blocks a release on a critical advisory.
- Overview card doors differ slightly from page doors (TD-503, TD-504); read-only exposure of counts only, no applicant data.
- No sign-in sandbox for non-admin roles (audit completeness lens).
- Earlier items unchanged: TD-487, TD-488, TD-496, TD-497, TD-499.
