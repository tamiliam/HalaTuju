# Request #67 scope 3b — alignment never copies the card's spacing over a correct name

Owner-approved 15 Nov 2026 ("Fix first"). Bug fix under #67, no charge. Identity change: Opus builds, Opus adversarial review, owner phone check after live.
Executor: Opus agent. Worktree: `scratchpad/wt-req67d`, branch `req67-align-tidy` (on origin/main 084def54d, which is live 36c6982dc + a docs commit).

## Verified facts (prod, read-only, 15 Nov, after scope 3 went live at 16:00)
- The D5 dry run (`align_profile_names_to_ic`, no `--apply`) printed: 422 checked, 6 to align (177, 606, 118, 190, 306, 602), already 386, no_name_match 28, nric_differs 2. Nothing written. No `name_aligned_to_ic` activity rows exist yet (none of the live read paths has fired one).
- 177 and 606 are the real cases: the profile name has fewer words; the signature equals the card read exactly.
- 118, 190, 306, 602: the profile name has the SAME LETTERS as the card and differs only in marker spacing:
  - 118: typed `XXXXXXXXXXX X/X YYYYYYYY` (correct), card read `XXXXXXXXXXXXX/X YYYYYYYY` — the reader GLUED the A/L onto the word before.
  - 190, 602: typed `... X @ Y`, card `... X @Y` / `... X@Y`; 306: typed `X@Y`, card `X @Y`.
- Why: `name_alignment` (apps/scholarship/identity.py ~L308) accepts via `_same_words` → `same_word_sequence`, which compares `tidy_name` forms (glued markers split, `@` standalone). Its ALREADY test is `_same_text` (case, spaces and slash spacing only), so a marker-spacing-only difference falls through to ALIGNED, and `align_name_to_ic` writes the RAW `vision_name`. `StudentProfile.save` (apps/courses/models … `tidy_parentage_marker`) only collapses spaces inside `A/ P`; it does not split a glued `KUMARA/L` or tidy `@`. So 118's correct name would become the glued misread — and `profile.name` feeds the payments CSV to Vircle.
- The same `align_name_to_ic` runs live on every IC read (`vision/ic.py` ~L279, before the lock) and on staged-upload promotion (`upload_read.py` ~L159).
- `name_card_takeable` (~L260) offers "Use the name on my IC" whenever `not _same_text(card, profile.name)` — so it too offers the glued/spaced card text for a spacing-only difference.

## Owner-settled decisions
| # | Decision |
|---|---|
| E1 | A name whose WORDS already equal the card's (`same_word_sequence(card, profile.name)`) is ALREADY aligned. Nothing is written. The student's own spacing stands. |
| E2 | When an alignment does write (the words differ, and the card's words equal the profile's or a signature's), it stores the card name TIDIED: `tidy_name(card)` upper-cased (marker split off as its own word, `@` standalone, single spaces) — never the card's raw spacing. Keep `save()` as is; the stored value must be a fixed point of `save()`. |
| E3 | `name_card_takeable` is False when the card's words equal the stored name's (E1's test). Its other gates are unchanged. `name_change_allowed` is unchanged (the student may still type any `same_letters` variant). |
| E4 | No other behaviour changes: the D2 safety gates (latest live student card, clean read, exact NRIC, `_same_words` against profile or a signature), the lock, admin paths, parent cards. |
| E5 | No migration, no web change (the bundle budget must not move). VERDICT_ENGINE_VERSION: no bump expected — `name_match` and the IC verdict give the same answer for a spacing-only difference; confirm this in the code and say so in the commit body (if you find a verdict input that does move, bump to the next number after '2026-11-14.4' instead). |

## Phases
1. `identity.py`: E1 in `name_alignment` (before the signature loop, so ALREADY wins), E2 in `align_name_to_ic` (one small helper, e.g. `card_display_name(card)`, used by both the write and the activity `meta.new`), E3 in `name_card_takeable`. Update docstrings, including the module docstring and the outcome comments.
2. Tests in `apps/scholarship/tests/test_req67_ic_name_alignment.py` (made-up names only):
   - 118's shape (typed correct `… A/L …`, card glued `…A/L …`) → ALREADY, no write, no activity row, button not offered;
   - the three `@` shapes → ALREADY, no write, not offered;
   - 177's shape → ALIGNED, stored = tidy card, signature untouched;
   - a 177-shape whose card is ALSO glued (short profile, signature correct, card `…A/L`) → ALIGNED and stored with `A/L` as its own word;
   - stored value is unchanged by a second `save()`;
   - the command's dry run counts the E1 cases as `already`;
   - the live read path (`run_vision_for_document`) and the upload-promotion path both follow E1/E2.
   Targeted tests while building; then the full api suite once: `python3 /Users/elanjelian/Python/Settings/_tools/test_queue.py -- <cmd>` (look at how `docs/` or the scope 3 commits ran it; the earlier scope 3 full run was 14316 passed).
3. Docs: CHANGELOG entry; one sentence appended to the #67 scope 3 paragraph in decisions.md.

## Commit
One commit, explicit paths only (never `git add -A`; never add `halatuju-web/node_modules`), including this brief. Message prefix `fix: request #67 (scope 3b) - ...`, ending with:
```
Phone-check: open application 177 - the IC check shows "matches" and the name has a tick
Services: api
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```
Do NOT push, do NOT take a TD number, do NOT touch production, do NOT run any Cloud Run job. Do not edit CLAUDE.md or settings. No PII in code, tests, commit or report (application/document ids are fine).

## Report back
The sha, the diff summary, targeted and full test counts, and your VERDICT_ENGINE_VERSION reasoning.
