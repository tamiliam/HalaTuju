# Document chip standard

Status: Sprint 0 built on 2026-11-27 (branch `chip-std-s0`). It is display only, with no visible change and no verdict change.
Approved look: `docs/document-chip-mockup-approved-2026-11-26.html`.

## What Sprint 0 adds

One server module, `apps/scholarship/doc_chips.py`, builds every document's chips. It reproduces **today's** officer-drawer colours exactly.

- `chips_for(payload)` works on the serialized document dict and makes no database queries. Each chip is a dict:
  - `key`: the chip's field
  - `status`: verified / partial / not / unknown
  - `state`: green / amber / red / grey
  - `student_action`: always `none` in Sprint 0. The allowed values are none / reupload / fix_entry / add_doc / we_check.
  - `reason`: the raw check word
  - `kind`: fact / year
  - `value`: year chips only
- `pill_for(chips)` skips year chips and grey chips. It returns `unread` when no chips are left, `verified` when all are green, and `check` otherwise.
- `ApplicantDocumentSerializer` now serves `chips`, `chip_pill` and `read_at`. `read_at` is the later of `vision_run_at` and `vision_fields_run_at`, or null. The officer serializer (`sgd_conversion.AdminApplicantDocumentSerializer`) inherits all three.
- Nothing reads the served chips yet. Sprint 1 and later move the screens onto them.

### Guards

- **Parity fixture**: `apps/scholarship/tests/fixtures/doc_chip_parity.json` holds 77 synthetic cases.
  - `tests/test_doc_chips.py` checks the server against it.
  - `halatuju-web/src/lib/__tests__/doc-chip-parity.test.ts` checks today's web against the same file. That means `documentFacts` / `documentPill`, plus the drawer's `factClass` / `yearChip` / `yearClass`, which the test lifts out of `DocumentsDrawer.tsx` with a stub `t`.
  - So the two sides can only agree or both go red.
- **Display only**: `tests/test_doc_chips_import_fence.py` enforces it in three ways:
  - No engine file names `doc_chips`.
  - Only the document serializer and the dry run import it.
  - A fresh interpreter that imports every engine never loads it.

  The test's docstring explains why a static transitive walk was not used: the package `__init__` files pull in the whole app.
- **Dry run**: `apps/scholarship/eval/chip_dry_run.py` runs `run_dry(old, new)` inside one read-only transaction that is always rolled back (`offer_s4_dry_run.read_only_rollback`).
  - It counts, per document type: documents, chips, chips whose state would change, pills that would change, and student/officer differences.
  - It also checks that every application's verdict bands are identical, with the chip functions rigged to raise.
  - It outputs counts only. It is unit-tested on the test database only and is hand-run only on the owner's word. Never point it at a live database from a checkout.

### Kept on purpose: student and officer can differ on one chip

`figure_refused` is served only on the officer payload. So on a salary slip or EPF statement:

- the officer sees an amber **Amount / Contribution unusable** chip;
- the student payload shows the read figure (green when a figure was read).

`chip_dry_run` counts this as `student_differs`. A later sprint decides what the student should see.

## The standard (target, from the approved mock-up)

| State | Symbol | Meaning |
|-------|--------|---------|
| green | ✓ | Checked. It agrees. |
| amber | ! | A person must look: near match, couldn't read, missing, older date, date not shown. |
| red | ✕ | Checked. It is wrong. |
| grey | (no symbol) | Not checked yet, or nothing to compare. |
| plain | (none) | A value copied from the document, shown as the value only. Never green. |

- **Pill**:
  - **Problem**: any red chip.
  - **Check**: any amber chip and no red.
  - **Verified**: all checked chips green.
  - **Unread**: nothing checked yet.

  Today there is no Problem pill: red and amber both give `check`.
- **Chip text** is the field name only. The genuineness chip's text is **Type**.
- **Officer drawer**: one short line per amber or red chip, in fixed words (English, Malay, Tamil). Grey and green chips get no line. Names, IC numbers and addresses appear only in the opened document. AI notes that belong to no chip show as a grey speech bubble with a count.
- **Read time**: short in the drawer ("read 25 Nov, 09:12"), with the year added only when it is not this year. The opened document always shows the full date and the upload time.
- **Student screen**: under each amber or red chip, an action line saying who acts and what to do. That is the `student_action` field, which is `none` until a later sprint fills it.

## Per type: today → target

"Today" is what `doc_chips` serves now, which is what the drawer draws. Chip keys are in `code`. "Target" is the standard above, applied to each type. It is a **proposal** drawn from the mock-up: each family's sprint confirms it with the owner before any colour changes, one family per sprint. The dry run counts each family's change first.

| Doc type | Today | Target |
|----------|-------|--------|
| ic | `name`, `ic_no`, plus the genuineness chip. A wrong type (`not_*`) caps both red. | Name, IC No, Type. Unread = 2 grey chips with no symbol. |
| parent_ic | `name`, `ic_no` from `readable` only. Then one of: genuineness chip, `wrong_card` (amber), or `relationship` (patronymic member). | Name and IC No from the real name/IC match, not readability. Type. |
| results_slip | `name`, `subjects`, `results` (capped); a higher-kind result on the SPM slot gives `name` + `type` red. Year chip `examYear`. | Name, Subjects, Results, Type; the year as a plain value with its colour. |
| higher_results | `name`, `type`, `cgpa`, `results` (optional), genuineness chip, with no cap. `type` is green only on `match`. Year chip `stpmExamYear`. | Name, Type, CGPA, Results; a near-type word becomes amber, not red. |
| offer_letter | `name`, `ic_no` (unreadable = amber), `pathway`, `official`, `reportingDate`, `switched`. Year chip `intakeYear`. No separate genuineness chip: `official` carries it. | Name, IC No, Course/Pathway, Type, Reporting date; unread = grey chips (see the mock-up). |
| str | `recipient`, `ic_no`, `status`, `current` (all capped), genuineness chip. | Name, IC No, Status, Current, Type. |
| salary_slip | `name`, `ic_no` / `ic_no_mismatch` / `ic_no_unreadable`, `amount` or `amount_unusable` (officer only), `period`, genuineness chip. | Name, IC No, Type; the amount and month as plain values; couldn't read = amber. |
| epf | `name`, IC chip as for the salary slip, `contribution` or `contribution_unusable` (officer only), `balance`, `current`, genuineness chip. | Name, IC No, Contribution, Type; couldn't read = amber. |
| birth_certificate | `child`, `mother`, `father` (capped), genuineness chip; unreadable = one amber `unreadable` chip. | Child, Mother, Father, Type. |
| guardianship_letter | `guardian`, `ward`; unreadable = one amber `unreadable` chip. | Guardian, Ward. |
| semester_result | `name`, `ic_no` (green on match or partial, red otherwise, including not_found), `cgpa` (green when read, else grey). | Name, IC No, CGPA, with near match = amber and not found = amber. |
| school_leaving_cert | `school`, `name`, `ic_no`, `behaviour` (good / concern / bad). | Same fields under the standard colours. |
| income_support_doc | `evidence` (green when read, else red), `amount` (green when read). | Evidence; the amount as a plain value (never green). |
| water_bill / electricity_bill | `address`, `current` / `ageing` / `stale`, `reasonable`, `outstanding` (arrears), genuineness chip; a wrong type turns address/current/reasonable red. | Type, Name, Address, Date; the amount as a plain value. |
| photo and other types | The genuineness chip only, if there is a signal. | Type only. |

## Odd findings in today's code (copied as they are; not fixed in Sprint 0)

1. **STR Status 'unreadable' is amber, but STR Current 'unreadable' is grey.** It is the same word in two different colours on one document.
2. **Semester 'partial' is green and 'not_found' is red** (owner rule of 2026-07-05). Under the standard, a near match and a missing field are both amber.
3. **Parent IC Name and IC No come only from `readable`.** Both chips are green when the card could be read and red when it could not. Neither chip compares the name or the number.
4. **Officer higher-results Type: any word except 'match' is red.** That includes words that should mean "a person must look".
5. **The higher-results chips are never capped by a wrong-type verdict**, unlike the other types.
6. **The pill has no Problem state**: red and amber both give `check`.
7. **Salary slip / EPF Amount on the student payload ignores `figure_refused`** (see above).

## Case 1048 (Sprint 3)

The OCR "name is close" fix (`SHOW_CLOSE` / `name_close`) is **not on main**. It lives only on the branch `fix-1048-declaration`. The near-match amber chip for this case belongs to Sprint 3. Rebase on that fix, or port it, when the name chips move to the standard.

## Next step

Port the student checklist (`checklists.tsx` and `checklistsPathway.tsx`) onto the served chips. The student screen will then read the same `chips` / `chip_pill` as the officer drawer. This was not in Sprint 0.
