# Retrospective — Now sprint 5 part 1 (2026-10-03): TD-229, the agreement template belongs to a gift

**Scope:** build the owner's ruling of 2026-09-04 — the bursary agreement template is written PER
GIFT. One active per gift; an agreement renders from the template of the APPLICATION'S gift; a gift
with no template refuses rather than borrowing a neighbour's; BrightPath's live template back-filled
onto the flagship explicitly. Built by one agent; an adversarial reviewer reads the diff before the
lead commits. One migration (`scholarship/0163`, migrate-first, by hand). `BURSARY_AGREEMENT_ENABLED`
is OFF, so nothing signs today.

## What was built

| Item | Change | Guard |
|---|---|---|
| Model | `ContractTemplate.programme` (PROTECT, nullable) + partial unique index, one ACTIVE per gift | `TestOneActivePerGift` (DB refuses a second active) |
| Migration | 0163: AddField → RunPython back-fill (flagship by code, alias fallback, templates by organisation) → AddConstraint; Postgres DDL in the docstring | `TestTheBackfillIsLoadBearing` (calls the migration's own function) |
| Resolution | `contract_scope.py` (readers left `contracts.py`, 1,145 → 1,138) | `TestRendersFromItsOwnGift` |
| Refusal | `sign_agreement` → `no_active_template`, flag on or off; sign-invitation skips; award GET → `bursary_unavailable` | `TestAGiftWithNoTemplateRefuses`, golive_t1 skip case, `TestTheStudentAwardPageIsHonest`, web `award/page.test.tsx` |
| Admin | list/create by `?programme=` via `_gift_narrowing`; super's org follows the gift; Contracts row → Programme group; editor pins the crumb; delete blocker `has_contract_templates` | `TestTheEndpointsNarrowByGiftInsideTheFence`, web `contracts/page.test.tsx`, nav tests |

Counts: api **7,563 → 7,586** passed, 3 skipped; jest **3,287 → 3,292**, 201 suites; tsc, lint,
i18n green; `makemigrations --check` clean; bundle-budget ok (median 228 kB, 1.0 kB headroom — the
sprint-4 retro recorded 227 kB; this sprint's pages sit below the median, so the step is not
obviously this sprint's, but it was not measured on a pre-change build). Register open 130 → **131**.

## What went well

- **The bug was already in the test suite, waiting.** `test_bursary_agreement._ensure_active_template`
  put its students in a gift called `bursary-gift` and seeded the template for the organisation —
  exactly TD-229's shape. It passed for months because resolution was per organisation. Converting
  it to "seed for the students' own gift" was the fix the ruling describes, in miniature.
- **A pre-existing crash surfaced by reading the student path.** The award GET (flag on) called
  `particulars_for(app)` and `render_agreement_html(...)` without the `template` both have required
  since Contract Sprint 5 — every flag-on preview would have been a 500. No test reached it. Fixed,
  tested, bitten.

## What went less well

- **The brief's premise was half wrong:** there was no org-level partial unique index to swap; the
  rule was code-only. Read the migrations before writing "replace X with Y" into a docstring.
- **One bite came back partly silent.** Reverting the resolver to organisation-level left the
  "signed agreement is the gift's own" test green, because the second gift's template was deployed
  LAST and so was also the organisation's newest. The fixture was too kind (rule 2 of the harvested
  rules); deploying gift B first made it bite (6 red).
- **The menu move is an IA change** made to satisfy "the gift chosen in the breadcrumb" — on an
  Organisation-scope page the crumb shows no gift at all. It follows TD-241's precedent and moves
  nobody's reach, but the owner should see it.

## Left

- TD-327 — NOT NULL on `programme` once production reads 0 NULL rows.
- TD-328 (owner) — a template-less gift is paid the legacy flat schedule; before this change a second
  gift's students were paid on the flagship's template. The lead's probe P4 counts who is affected.
- Deleting a gift: built first as "any template blocks" (there is no template delete, so such a
  gift was permanent); the owner ruled the same day that UNSIGNED templates go with the gift in
  the delete transaction and only a signed one blocks. Built and bitten (2 red, 1 red).
