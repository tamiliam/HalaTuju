# Document chip standard

Status: Sprint 0 built on 2026-11-27 (branch `chip-std-s0`). Sprint 1 phase 1a (server only) built on 2026-11-28 (branch `chip-std-s1`). Both are display only, with no visible change and no verdict change.
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

- **Parity fixture**: `apps/scholarship/tests/fixtures/doc_chip_parity.json` holds 100 synthetic cases.
  - `tests/test_doc_chips.py` checks the server against it.
  - `halatuju-web/src/lib/__tests__/doc-chip-parity.test.ts` checks today's web against the same file. That means `documentFacts` / `documentPill`, plus the drawer's `factClass` / `yearChip` / `yearClass`, which the test lifts out of `DocumentsDrawer.tsx` with a stub `t`.
  - So the two sides can only agree or both go red.
  - The server follows JavaScript's idea of "empty": an empty `{}` check is still a check, an empty list is "true", and only text is trimmed. The fixture has cases for each.
  - Where today's web would crash (for example `.trim()` on a number), the server gives a quiet answer instead. Those cases are tested on the server side only, because the web half cannot run them.
- **Never breaks a read**: if working out the chips raises, the serializer logs the document id and the error type only (never a value), and serves `chips = []`, `chip_pill = 'unread'`. The same goes for `read_at`, which falls back to null. Without this, one bad value would turn a document list into an error page, and after an upload it would re-run the paid read.
- **Display only**: `tests/test_doc_chips_import_fence.py` enforces it in four ways:
  - No engine file names `doc_chips`.
  - Only the document serializer and the dry run import it. This is checked across the whole api: every app and the `halatuju` project package.
  - A fresh interpreter that imports every engine never loads it.
  - No engine reads `['chips']` / `.get('chips')` off a payload, or names `chip_pill` at all.

  "Engine" here also covers the modules next to the verdict: `resolution*`, `genuineness`, `link_display`, `higher_results`, `income_str_ownership`, and the eligibility and gift modules. The test's docstring explains why a static transitive walk was not used: the package `__init__` files pull in the whole app.
- **Dry run**: `apps/scholarship/eval/chip_dry_run.py` runs `run_dry(old, new)` inside one read-only transaction that is always rolled back (`offer_s4_dry_run.read_only_rollback`).
  - It counts, per document type: documents, chips, chips whose state would change, pills that would change, and student/officer differences.
  - It also checks that every application's verdict bands are identical. While it re-reads the bands, the chip functions are rigged to raise. The serializer calls them through the module, so the rig catches a verdict path that serializes a document too. This proves it for the data the run reads, not for code paths that data never reaches.
  - It runs one documents query per application, plus the serializers' reads, over every application. So it is hand-run only, on the owner's word, never at a busy time.
  - It outputs counts only. It is unit-tested on the test database only. Never point it at a live database from a checkout.

### Kept on purpose: student and officer can differ on one chip

`figure_refused` is served only on the officer payload. So on a salary slip or EPF statement the officer sees an amber **Amount / Contribution unusable** chip. Since Sprint 1 the student payload serves the student's own chips (below), which never had an Amount chip.

## What Sprint 1 phase 1a adds (server only)

**Audience split.** The two payloads now serve different chips under the same three keys (`chips`, `chip_pill`, `read_at`):

- the student's `ApplicantDocumentSerializer` (`chip_audience = 'student'`) serves `doc_chips_student`;
- the officer's `sgd_conversion.AdminApplicantDocumentSerializer` (`chip_audience = 'officer'`) serves `doc_chips`.

**The student module.** `apps/scholarship/doc_chips_student.py` ports the badges today's student checklists draw under an upload card (`checklists.tsx`, `checklistsPathway.tsx`, and the dispatch in `cards.tsx`), rule for rule. Its chip is the officer shape plus one key:

- `kind` is fact (a status badge) / plain (a grey "from the document" tag) / note (the amber genuineness note);
- `label` is today's badge word as its full i18n key. The student's word cannot be worked out from the colour, so it travels with the chip. `label` is **student-only**: officer chips (`doc_chips`) never carry it, so the web chip type must mark it optional (`label?: string`);
- `student_action` is `none` everywhere;
- `pill_for` is the officer rule over `fact` chips only, including `problem` for any red one. The student draws no pill today.

**Parity.** The shared fixture gains 60 synthetic `student_cases`. `tests/test_doc_chips_student.py` checks the server; `halatuju-web/src/components/ScholarshipDocuments/__tests__/student-chip-parity.test.tsx` renders today's student checklists on the same cases (with a stub `t`) and reads every badge off the screen: colour, word and row. No component was changed.

**Student vs officer today** (copied as they are; nothing fixed):

| Where | Student | Officer |
|---|---|---|
| Utility address not found | red | amber |
| IC genuineness note | shown for anything but `genuine` (so `likely_genuine` too) | per the officer rules |
| Birth certificate | no `unreadable` row | has one |
| Offer letter | a pathway mismatch is amber on programme / institution; issuer, date and address are plain tags | adds Official and Reporting date chips |
| STR stale / future | no status badge | an amber Current chip |
| Results slip not SPM / not compared | no badge (not compared drops the row) | a chip on every row |
| Year chips | none | `exam_year` / `intake_year` |
| Pill | none drawn | served and drawn |
| Unread IC | no checklist until read (`[]`) | two grey chips |

**Known gaps (for Phase 1b).** The server works from ONE document at a time, so it cannot see what a screen decides from the whole card or from another code path. Each of these must be closed (or the screen kept on its own drawing for that case) before Phase 1b moves the student screen onto the served chips:

1. **Higher results.** A higher result on the SPM slot and the higher results' own checklist are drawn by lazy components outside the two files. For those the student module serves only the genuineness note.
2. **A second read IC on one card.** `cards.tsx` (`visionDoc = existing.find((d) => d.vision_run_at)`) gives `ICChecklist` only to the FIRST read IC on a card; a second read IC there gets `SupportingDocChip` + `GenuinenessNote`. The server (`doc_chips_student.chips_for`) gives every read IC the IC checklist.
3. **The no-app income fallback.** `IncomeProofCard` (used from `ScholarshipDocuments.tsx` when there is no application, rendered in `cards.tsx`) draws only `SupportingDocChip` for `str` / `salary_slip` / `epf`, never their checklists. The server serves those types' checklists.
4. **The jest dispatch is a copy.** `student-chip-parity.test.tsx` (`checks`) copies the `cards.tsx` dispatch rather than rendering `cards.tsx`, so a change to the dispatch in `cards.tsx` would not fail it. Phase 1b should render the real card, or pin the dispatch.

**Harder fence (N1, N2, N3, N7).** The import fence now covers both modules and flags a `doc_chips` / `chips_for` / `pill_for` Name or Attribute in an engine (N1), any engine import from inside the api of a module path with a part starting `serializers` (so `serializers_admin` and `serializers_org_requests` too), or of `sgd_conversion` / `upload_read` (N2, allowlist with a reason each; empty today; DRF's `rest_framework.serializers` is not flagged), the bare string `'chips'` or anything naming `chip_pill` (N3), and skips docstrings when scanning strings (N7). Only the document serializer and the dry run may name a chip module; the importer scan skips the chip files themselves by full path (`apps/scholarship/doc_chips*.py`), so a same-named file elsewhere is still scanned.

**Year chip (N5).** A year counts only when it is a str or an int (never a bool, float, dict or list). The web would draw such junk as text ("true"); the serializer only ever serves a str or an int, so the fixture is unaffected and no colour changes.

Checked (round 1 review): no served year can be a float. Every served year is a **string** today. `stpm_parse` holds the STPM year as an int inside the parser (`_cert_year`, `stpm_columns`), but stores it as `str(year)`; the served `higher_check.exam_year` then goes through `higher_results._stpm_exam_year` (a `20dd` string or `''`) or `exam_years.stored_transcript_year` (a string). `academic_check.exam_year` (`academic_engine`, a regex group or `''`), `pathway_check.intake_year` (`pathway_engine`, the same) and `wrong_slip` (`''`) are strings too. The rule is not widened to floats: JavaScript draws `2025.0` as "2025" while Python's `str(2025.0)` is "2025.0", so a float would not draw the same.

**Loud fallback (N6).** When working out the chips raises, the serializer still serves `chips = []`, `chip_pill = 'unread'`. It now logs at ERROR, once per process per exception type, with the document id and the exception type name only, and bumps `serializers.documents.CHIP_FALLBACKS['count']` on every fallback.

**Dry run.** `chip_dry_run` counts both audiences: `chips`, `state_changed`, `pill_changed` (officer, `old` / `new`), `problem_pills` and `check_to_problem` (officer documents that read Problem, and that moved from Check under a frozen pre-Problem rule) and `student_chips`, `student_state_changed`, `student_pill_changed` (student, `student_old` / `student_new`). Sprint 0's `student_differs` is gone: the audiences now differ on purpose. While it re-reads the bands, EVERY public function of both modules (`chips_for`, `pill_for`, `fact_chips`, `fact_status`, `year_chip`, `genuineness_note_key`) is rigged to raise. It also reports `chip_fallbacks`, how far `CHIP_FALLBACKS['count']` moved during the run (N6), so a clean run proves 0 fallbacks as well as 0 changes.

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

  The officer pill serves `problem` since Phase 1b (a red year chip alone is not one). The student `pill_for` follows the same rule (any red fact chip is `problem`); nothing draws it today.
- **Chip text** is the field name only. The genuineness chip's text is **Type**. (The student screen still draws today's words, for example "Matches"; moving them to the field name only waits for the student action lines in a later sprint.) Each chip also carries one hidden state word for screen readers (matches, needs a look, does not match, not checked), in English, Malay and Tamil.
- **Officer drawer**: one short line per amber or red chip, in fixed words (English, Malay, Tamil). Grey and green chips get no line. Names, IC numbers and addresses appear only in the opened document. AI notes that belong to no chip show as a grey speech bubble with a count.
- **Read time**: short in the drawer, after the file name and a '·' ("read 25 Nov, 09:12"), in the active language, with the year added only when it is not this year. The file name is still cut to 30 characters; the read time shows even when there is no file name. Nothing is shown for an old payload with no `read_at`; "not read yet" only when `read_at` is null. The opened document always shows the full date and the upload time.
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

## Closed in Sprint 1: officer words on the student payload

Sprint 0 noted that the student payload carried the officer's chip words (`wrongType`, `genuine`, `relationship`, `wrong_card`). Closed by the audience split: the student payload now serves only the student's chips, which carry exactly the words today's student screen already shows. `test_the_student_payload_carries_no_officer_chip_word` pins it.

Closed in the round 1 fixes: the officer's Re-run response (`views_admin/profiles.py`) now answers with `AdminApplicantDocumentSerializer`, so it serves officer chips (and the two officer-only fields, at no extra query). The web discards that body and refetches the case, so nothing on screen changes. Still open: the sponsor and upload-read payloads take the student audience; phase 1b should decide.

## Next step

Phase 1b: move the student screen onto the served chips (drawn from `label` / `state` / `kind`), with no visible change, then move the officer drawer onto `doc_chips`.
