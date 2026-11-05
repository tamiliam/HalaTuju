# HalaTuju v3.1.0 - Release Notes

**Date:** 2026-11-05 · **Tag:** `v3.1.0` (local until the owner approves the push) · **Previous release:** `v3.0.0` (2026-10-06)
**Live at:** [halatuju.xyz](https://halatuju.xyz) · **Commits since v3.0.0:** 814 · **Live revisions:** api `halatuju-api-01255-zsm`, web `halatuju-web-01084-l6b` (main `3c39489b`)

Written for the owner (tamiliam) and whoever works on HalaTuju next. Every change is in [`CHANGELOG.md`](../../CHANGELOG.md) (newest first, above the "v3.0.0" heading); the reasons are in [`docs/decisions.md`](../decisions.md); the access review is in [`security-notes-v3.1.0.md`](security-notes-v3.1.0.md).

## In one paragraph

v3.0.0 was a complete bursary platform. v3.1.0 makes it kinder to the people who run it and to students on a phone. Staff now have a real **team** (several hats per person, mentors, permissions you can read), every page works on a **phone**, the system **reads offer letters exactly** instead of guessing, the **student is looked after after the award** (results, surveys, announcements, mentoring, a "My Bursary" hub), and the first screen a staff member sees is **one Overview page showing only the work waiting for them**.

## Features Delivered

### One Overview page for every staff member (Team tables T5c, 2026-11-04 and 2026-11-05)
- Everyone on the partner login lands on one **Overview** page. Top: cards for the work pending for that person (admin: ready to assign, overdue, awaiting QC, sponsors to vet; finance: payment runs, wallet credits; QC: awaiting your check; reviewer: open, due soon, overdue; mentor: mentees, not yet met, asked for help). Below: the programme cards, each person seeing only their own programmes.
- **Unassigned** means a case that can really be assigned now. Each card opens the list behind it (ready to assign, overdue, due soon, open, my cases, needs action) and the number always equals that list.
- One menu row instead of three; old links still arrive, in one hop.

### The team and permissions (T1-T5)
- A person can wear several hats; the Team page, Mentors under Team, mentor detail, Emails and Terms in three sections; permission catalogue v2 with aliases; pages open by keys; QC works on its own.

### Phones (Mobile M0-M8)
- A written Mobile Standard with guards; a shared bottom Sheet; a bottom tab bar for students; the apply, documents, award, discovery, sponsor and reviewer pages, the admin "Can" screens and the Team tables all fit a phone; every screen measured; first-load JavaScript is lighter (bundle median 228 kB to 144 kB).

### Student maintenance after the award (Sprints 1-10)
- Scholar file with Money and Contract tabs, results review and standing, the emails a funded student receives, a "My Bursary" hub, letters, announcements, surveys, development modules, mentors who log in and log meetings.

### Documents, offers and results
- Offer letters are **read exactly** (parser 2.0.0, reader 2.4.0, campus and programme-code fields, a shorter course never wins by a subset of a longer name); the genuineness rulings and chip table (S6).
- STPM exact-read and CGPA from the grades; Matric/Diploma exact-read; a third results route and higher-results upload; income-declaration and STR rules tightened (owner rulings); Bumiputera and Islamic coverage; Bumi UP_TVET programmes.
- A source sign-in arc and referral-source rework; common profile (one Profile page, My activity).

### Billing and requests
- Real invoices (back-dating, grouped lines, bug work free), tenant "we have paid", receipts, the close gate reads the last report, a paged Requests list with tabs.

## Behaviour Changes
- The sidebar has one **Overview** row; the old Overview and Administration rows redirect to it. The mentor card reads "Not yet met".
- The programme overview "Unassigned" tile counts ready-to-assign cases only.
- A reviewer opening a programme where she has no case gets "not found".
- A pre-U offer letter on a degree pick no longer reads "Pathway mismatch" (TD-473).
- An awaiting-QC case can be declined only through the QC gate (TD-481).

## Breaking Changes
- **Visitors and students: none.** No public URL removed. Two sidebar routes now redirect.
- **Admin API (internal):** `admin/scholarship/billing/invoice-settings/` was removed when billing settings moved to the screens whose scope they match (2026-10-28). New routes: `admin/scholarship/my-programmes/`, `admin/scholarship/my-pending/`, `admin/mentor/students/?programme=`.
- **Schema:** 48 new migrations (courses 0077-0091, scholarship 0170-0202). Scholarship migrations are applied BY HAND before the code (see `docs/deployment.md`); the full list: `git diff --name-only v3.0.0..v3.1.0 -- '**/migrations/*.py'`. No migration in P5b or P5c.

## Known Issues
Full register: `docs/technical-debt.md` (Open Items Index). Grouped by what unblocks them:
- **Security, needs a decision before the push (code + owner):** `npm audit --omit=dev` reports 1 critical and 5 high (Next.js 14.2.0 pinned; a fix is a major upgrade to a patched 14.x/15.x; also nanoid and picomatch, fixable by `npm audit fix`). `pip-audit` reports Pillow 11.3.0 (fix 12.x/13.0.0) and pypdf 5.9.0 (fix 6.x; pypdf is pinned on purpose because STPM certificate reading depends on its text layer). `release.md` says a critical advisory blocks the release. See TD-506.
- **Owner ruling needed:** TD-487, TD-488, TD-496, TD-497, TD-499, TD-503.
- **Code, first fix sprint:** TD-501 (a reviewer invite takes no gift; NULL means every gift). Owner ruled: first fix after this release.
- **Code, small:** TD-500, TD-502, TD-504, TD-505 (Overview cards: unfiltered links, door mismatch, query budgets).
- **Mock-up / owner's call:** TD-489 (mentor screens on a phone).
- **Paid / sitting:** offer exact-read S7 (frozen until the audit's fix sprints are done).
- **Login sandbox:** there is still no way to sign in as a reviewer, mentor, finance or QC to check a change; proposed for the audit.
- **Freeze in force:** no T5d, no offer S7 until the project audit (on this tag) and its fix sprints are done.

## Numbers
| Gate | v3.0.0 | v3.1.0 |
|---|---|---|
| api `pytest -n auto` | 8,084 passed | **12,433 passed**, 3 skipped |
| web jest | 4,146 | **6,525** |
| bundle median first load | 228.1 kB | **144.147 kB** |
| mobile-check | n/a | **775 passed** |
| migrations | to 0169 / courses 0076 | scholarship 0202 / courses 0091 |

Measured at P5c close (2026-11-05) with the deploy gates' own command lines.

## Upgrade checklist (operator)
1. Check the audit items above and the owner's ruling on them.
2. Migrations are already applied on production (applied by hand before each deploy).
3. Nothing to do for env vars beyond what each sprint recorded in `docs/deployment.md`.

Security: we updated the web app's framework to its last safe 14.2 release and switched off a built-in image tool we do not use, so the most serious known weaknesses are closed before release.
