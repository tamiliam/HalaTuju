# Clause hierarchy + upload-at-create — implementation plan

**Date:** 2026-07-19 · **Owner-approved** (design mockup signed off) · Contract module (flags OFF)

Adds a 3-level clause hierarchy to `ContractTemplate` + surfaces the existing docx importer as a
third "create version" option. One coherent change; one deploy.

## Locked design
- **3 levels**, auto-numbered from the `(order, level)` sequence — the author never types a number:
  - level 0 → `1.` `2.` (decimal) · level 1 → `1.1` `1.2` (decimal) · level 2 → `i)` `ii)` (lowercase roman).
- **Structural rule:** a clause's level may be at most `previous.level + 1` (no skipping a level); the
  first clause must be level 0. Enforced in `replace_clauses` + surfaced by the editor (disable Indent
  when it would skip).
- **Quiz stays at level 0 only.** The comprehension question is generated from the **whole subtree**
  (the clause + all following deeper-level clauses until the next same-or-shallower clause).
- **Upload a document** = the create form's third option → create blank → run the existing importer →
  land on the Clauses tab to review. The importer now returns a `level` per segment.
- Numbering is **computed server-side** so the preview + the signed PDF render identically.

## Pieces
**Backend**
1. `models.ContractClause.level` = PositiveSmallInteger (0/1/2), default 0 (+ migration `0105`).
2. `contracts.py`:
   - `clause_numbers(levels) -> [label]` (+ `_roman`); the single numbering source of truth.
   - `replace_clauses`: accept `level`, validate no-skip + first==0, force `is_quiz_candidate` False for
     level>0.
   - `_clone_content`: carry `level`.
   - `_clause_and_descendants(clause)` → quiz prompt uses the subtree text.
   - `segment_docx` / `_build_segment_prompt` / `_parse_segments`: Gemini returns `level`; parse clamps
     0-2 and normalises any skip down to prev+1.
   - `validate_for_deployment`: structural level check + quiz-only-on-L0.
3. `render_agreement_html`: computed numbering + per-level indent (replaces the flat `<ol>`).
4. serializer `_contract_clause_dict`: expose `level`.

**Frontend**
5. `lib/clauseNumbering.ts` — `clauseNumbers(levels)` mirroring the Python (paired jest test vs a fixture).
6. `admin-api.ts`: `ContractClauseData.level`; import returns `level`.
7. `ClauseEditor.tsx`: computed numbers, Indent/Outdent (← →), move up/down, quiz checkbox only on L0.
8. `contracts/page.tsx`: "Upload a document…" third create option → create + import → Clauses tab.
9. i18n `admin.contracts.*` additions (en/ms/ta, Tamil first-draft).

**Tests**: numbering (BE+FE), no-skip validation, quiz-subtree, segment level, render numbering.

*Accept:* pytest + jest + next build green; a template with `1 / 1.1 / i)` renders those labels in the
preview + PDF; quiz offered only on top-level clauses and covers the subtree; upload-at-create lands on
a reviewable clause list. Flags stay OFF.
