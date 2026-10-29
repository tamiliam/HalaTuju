# Retrospective — Student maintenance Sprint 2: the admin Scholars list and maintenance file (2026-10-29)

Roadmap: `docs/plans/2026-10-29-student-maintenance-roadmap.md` (Sprint 2). Design of record: the owner-approved
canvas (2026-10-29). Shipped as `3b27acbd` (feature) and `1debc6cc` (adversarial review fixes), pushed as `1debc6cc`.
No migration.

## What Was Built

- **API** — `GET admin/scholarship/scholars/` (the S1 maintenance predicate; `?closed=1` for closed files; filters,
  search, sort, server-side pages, summary tiles), `GET …/scholars/<id>/` (header + overview: latest result, money
  from the ledger, contract status), `GET/POST …/scholars/<id>/activity/` (timeline + manual note / call / meeting
  with a staff-only flag; a closed file is read-only, 409 `file_closed`). The cockpit payload gained `has_file`.
- **Fence** — the Applications rule, unchanged (`_b40_scope`): `see_all` reads the organisation, a reviewer only
  their assigned scholars, finance / partner 403, another organisation 404. Classified in `test_org_fence.py`;
  `scholars.py` joined the static scan.
- **Web** — `/admin/scholars` (tiles, PanelTabs filters with the not-yet-built ones disabled, search, sortable
  TableFrame, phone cards, pagination) and `/admin/scholars/[id]` (header, eight tabs, Overview cards, the
  `ScholarActivity` timeline + composer with the site Toggle). Menu row under Applications (chord G M,
  `needsProgramme`, Applications' roles and keys). Cockpit "Open scholar file" link. en / ms / ta.
- **Cost** — `card_display.catalogue_course_names` reads a page's course names in two queries; the list costs 8
  queries at 2 rows and at 5 (admitted query budget).

## What Went Well

- The fence was a REUSE, not a new rule: `_b40_scope`, `_org_scoped`, `_gift_narrowing` and the
  `test_org_fence` classification all existed, so the sprint added no reach for anybody and had one sentence to
  defend in `decisions.md`.
- The house guards caught every shortcut on the first full run: a helper name duplicated across three modules
  (`_identity`), a list page without phone cards, a menu row without an icon, the FAQ one entry past its size
  limit (TD-413). Each failed loudly and was fixed in minutes rather than found in review.
- The query budget was set from a measurement (8 and 8), so the "a row costs nothing" claim is pinned, not hoped.

## What Went Wrong

1. **IC search found nothing for an undashed IC or a prefix** (adversarial review, MED). The first cut matched the
   stored dashed NRIC as a substring and treated any short number as an application number, so `880312105555` and
   `880312` both missed. **Root cause:** the search was written fresh instead of reusing the one the Applications
   list already uses (`apps.courses.search`, digits-only on both sides) — the very bug that module's docstring
   records fixing for phones. **System change:** the Scholars search reuses that module's `_digits_expr`, `#<n>` is
   the only application-number form, and the tests search dashed, undashed and prefix ICs.
2. **A descending CGPA / activity sort would open on the students with nothing** (adversarial review, MED).
   Postgres puts NULLs FIRST on `DESC`; SQLite puts them last. The local suite (SQLite) was green and production
   (Postgres) would have shown every student without a result at the top of "highest CGPA first". **Root cause:** a
   nullable annotation was ordered by name only, and the test suite cannot see a backend-dependent default.
   **System change:** `F(...).asc/desc(nulls_last=True)` on both annotated sorts, and a test that asserts NULL-last in
   BOTH directions (meaningful on SQLite because it pins the order, not the default); lesson recorded.
3. **Smaller review findings, all fixed:** notes were writable on a closed file (closed is read-only — now 409 and
   no composer); a moved round's scholars vanished from their new gift (now the Applications cohort-reaching gift
   rule); the file's money links ignored the viewer's role and the gift (now gated by `canAccess` and carrying
   `?programme=`); "remaining" with no award read blank where the funding summary reads 0 (now
   `payments._remaining`). **Root cause, shared:** each was a rule the codebase already had in one place and the
   new screen re-derived. **System change:** the review prompt for the rest of the roadmap — "for every rule this
   screen applies, name the existing function it reuses".

## Design Decisions

- **The Applications rule fences Scholars** (decisions.md, 2026-10-29): a scholar file is a view of an
  application the reader can already open. Notes are open to every reader of a file (a record, not a decision);
  holds stay payments-gated (S1).
- **No standing is judged before Sprint 4**: `standing` is only `has_result` / `no_result_yet`; the
  Underperforming / Results overdue / Wants a mentor filters are drawn disabled.
- **No nav badge** yet: the shell's badge needs its own count endpoint.
- **No FAQ entry**: `faq.tsx` sits at its 600-line limit (TD-413); the Guide carries the Scholars sections.
- Accepted from the review (documented, no code): a `see_all` admin who is not assigned may write a note on any
  file in their organisation; a reviewer with no gift chosen still sees the Scholars row (the page asks).
- Raised: **TD-421** — an IC typed into a search URL (`?q=` on Applications, `?search=` on Scholars) reaches the
  Cloud Run request logs.

## Numbers

- Full api suite **9,976 pytest** (lead, after rebase on `fd71e8a9`); web **4,860 jest / 310 suites**; `next build`
  OK; bundle median **146.345 of 148 kB**; `/admin/scholars` 146 kB, `/admin/scholars/[id]` 145 kB first load.
- Query budget: Scholars list 8 queries at 2 rows and at 5.
- Adversarial review: SHIP-WITH-FIXES, 0 HIGH, 2 MED (both fixed), the rest fixed or accepted as documented.
- 36 files in the feature commit; two commits.
