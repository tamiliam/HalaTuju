# Applicants export (Excel) — roadmap (2026-11-14)

**Status:** PLAN, awaiting the owner's go to start the sprint. Not built. See §5 Timing (narrow freeze).

**Why.** The owner made a one-off Excel of every applicant to `bpb-sabah-2026` (BrightPath) for its org admin
on 2026-11-14 (a read-only script, then deleted; the file sits in the gitignored `docs/scholarship/`). The owner
wants the same file from a button, so no one has to run a script again.

**Scope line.** One "Export (Excel)" button on the admin Applications page, at the top right, in line with the
gift name. It downloads every applicant to the gift that is open, in all statuses, with income both as DECLARED
and as worked out by the AI from the documents. Nothing about an application changes: no model, no migration,
no transition, no e-mail.

## 0. Decisions (owner)

| Question | Answer | Date |
|---|---|---|
| Who may press the button? | **Org admins only** by default. The power is a PERMISSION KEY, so it is set on the Permissions tab like every other staff power (owner, 2026-11-14: "The permission is set in the permissions tab"). Reviewers do not hold it. | 2026-11-14 |
| Which applicants? | All statuses (the one-off file did this; the owner did not narrow it). | 2026-11-14 |

## 1. What exists (read 2026-11-14)

| Thing | Where | Today |
|---|---|---|
| Permissions | `apps/courses/staff_permissions.py` (`CATALOGUE`, `PRESETS`, `LEAD_TIER`, `DEPENDS_ON`); read through `admin.has_perm(key)`; editor on the Permissions tab; golden table `apps/courses/tests/test_permission_presets.py`; roadmap `docs/plans/2026-10-19-staff-permissions-roadmap.md` | Eight keys. No export key today. |
| Gift heading | `halatuju-web/src/app/admin/scholarship/page.tsx:316` | `<h1>` with `admin.scholarship.title` ('{programmeName} Applicants'). The button goes on this row, right-aligned. |
| List endpoint | `AdminApplicationListView` (`apps/scholarship/views_admin/applications.py:42`) | JSON only; supports `?programme=<code>`. Its org fence is the one the export must reuse. |
| Other CSV | `PartnerStudentExportView` (`apps/courses/views_admin.py:480`) | Profiles CSV. Pattern for a file response; not reused for the data. |
| Gift filter | — | `Q(programme=p) \| Q(cohort__programme=p)`. |
| AI income | `apps/scholarship/income_engine/` | Not stored; worked out live. `earner_monthly_income`, `income_per_capita`, `income_headroom`; members = `[income_earner] + effective_working_members(app, any_route=True)`. `has_valid_str`. |
| Income verdict label | `build_verdict(app)` (list of facts, key `fact`) → `verdict_narrative._fact_band` | Same Certain / Probable / Unsure / Can't verify as the cockpit tile. |
| Birth state | `birth_state_from_nric` | Returns a `BirthState` object; write `.state` as text. |

## 2. The file (same as the one-off)

Sheet "Applicants": ref, name, NRIC, gender, birth state, phone, e-mail, address, postcode, city, school, SPM and
STPM grades, STPM CGPA, chosen course and institution, status, submitted date, award; DECLARED household income,
household size, STR, JKM, income route, main earner, declared amount per member; AI amount and source per member
(father, mother, guardian, brother, sister), AI household gross, AI per capita, all incomes read, AI B40 band, AI
income verdict, valid STR document; notes. Yellow header = declared, blue header = AI. Frozen at C2, auto-filter.
Sheet "Read me": what the colours and labels mean, and "personal data — org admin only".

**Never in the file:** the Bumi answer, religion (domain rule — course guide only).

## 3. The permission key

- New key **`export_applicants`** in `CATALOGUE` (Students group, after `see_all`).
- `DEPENDS_ON['export_applicants'] = ('see_all',)` — you cannot export what you cannot read.
- In `LEAD_TIER` (the org admin holds it). In NO team preset, so reviewers, QC, finance and team admins do
  not get it by default. An org admin may grant it to a team member on the Permissions tab.
- A super passes it (as every key). A referral partner never holds it.
- Golden table updated: one new column, every old row unchanged.
- Permissions tab: the new row with its label and help text in en / ms / ta.

## 4. Build (one sprint)

1. **Stitch** — the heading row with the button (desktop + phone). Owner approves the picture.
2. **API** — `GET /api/admin/scholarship/applications/export/?programme=<code>` returns `.xlsx`.
   - Logic in a new module `apps/scholarship/exports/applicants_xlsx.py` (pure: queryset in, workbook out).
   - Permission: `has_perm('export_applicants')` AND the gift is in the person's organisation (or super).
     No key → 403. Other org's gift → 404 (no leak).
   - One AI-income error marks that row's note; it never stops the file.
   - Audit log row per export: who, when, gift, row count.
   - Read only: no write on any path (a test asserts zero writes).
3. **Web** — button on the heading row; shown only when the person holds `export_applicants`; downloads with a dated name,
   `<gift-code>_applicants_<YYYY-MM-DD>.xlsx`. British English copy in en / ms / ta.
4. **Tests** — permission matrix (incl. the access-matrix test from advisor action 4), org fence, columns and order, Bumi/religion absent, error row, query budget,
   web button visibility.
5. **Adversarial review** (identity / PII rule) before the push.
6. **Release train** — a window (11:00 / 16:00 / 21:00 MYT), owner's yes, via `live`.

## 5. Timing

The narrow freeze (owner "A", 2026-11-12) holds BrightPath features to staged analyses until ~4 Dec unless the
owner marks one urgent. This export is a BrightPath feature, so it waits for ~4 Dec or the owner's "urgent".
Meanwhile the one-off script route still works (ask Claude; read-only, file in `docs/scholarship/`).

## 6. Risks

- **Speed.** The AI income runs per student. 497 rows ran fine from a laptop, but it was not timed. Time it on
  the Sabah gift in the sprint; if it is near the Cloud Run request limit, prefetch documents per gift or build
  the file in a job and e-mail a link.
- **PII in a file.** Once downloaded, we cannot pull it back. The Read me sheet says so; the audit log records it.
- **Two numbers.** Declared and AI income will differ. The colours and the Read me sheet must make that plain.
