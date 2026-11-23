# Request #78 build brief: birth-certificate and guardianship match bands, and each card leads with its reason

Approved analysis 193 (BrightPath, 8 h, bug, sprint, no charge). Scheduled by the owner on 23 Nov 2026.
Owner rulings: 23 Nov 2026 (this brief is their record until they go into `docs/decisions.md`).

The organisation's comments before approval chose no extras. They quoted the student-facing owed line
"A matching parent's or guardian's IC — it doesn't match their income documents" (`parent_ic_person_mismatch`).

## The case (case 177; never write a student's name anywhere)

- The reader dropped one letter from a 5-letter word of the student's last name on the birth certificate.
  `relationship_name_match` → `_tokens_close` needs both tokens to have at least 5 letters, so the child-name
  check failed. The certificate's child IC number matches the student's IC exactly, but no name-based
  link uses it.
- Effect 1: `member_relationship_status` → mother link = mismatch → `student_income_ic_check(parent_ic).name_status`
  = 'mismatch' → `person_red` → owed line `parent_ic_person_mismatch`, worded as if the IC did not match the
  income documents. It does match them.
- Effect 2: the Income tile reads Unsure because the STR is next year's application
  (`str_not_current`, status `future`). But `_earner_relationship` appends `birth_cert_mismatch` to `review`
  before `_str_reading` appends the STR item, and `factSubtitleItem` shows `unresolved[0]`. So the tile's
  top line is the wrong birth-certificate line, and the real reason sits lower down.

## Part A: one shared row score (name + IC number)

A row is one person on the document compared with that person's reference:
- BC child row: certificate child name/IC vs the student's verified name/IC (as `student_bc_check` reads them today).
- BC mother row: certificate mother name/IC vs the mother's uploaded IC (`parent_ic`).
- Guardianship letter: guardian row vs the guardian's IC; ward row vs the student.
- **The father row on a BC and the father/brother/sister patronymic links stay exactly as they are**,
  outside the bands (BrightPath #23: the father row never blocks).

Definitions (owner: slips are counted, not percentages):
- Exact number: all 12 digits equal (`nric_match`).
- Close number: exactly one digit different (substitution); reuse `nric_close` if it means exactly this,
  otherwise say what it accepts and pin the owner's definition.
- Exact name: the same words, ignoring spacing, word order and the connectors A/P, A/L, BIN, BINTI (and their
  spelled variants already handled in `vision/names.py`).
- Close name: each word within one letter (two in words of 8+ letters), or one word missing or extra. This
  must accept a 5-letter word with one letter dropped (the case-177 shape) without the 5-letter floor that
  `_tokens_close` has.
- Far: anything else. Missing: blank or unread.

Row bands:

| Band | When |
|---|---|
| GREEN | both exact; or one exact and the other close |
| BLUE | both close; or exact number + far name (a name change, a bad read) |
| AMBER | close + far; exact name + far number (a name is not unique); one value missing and the other exact or close |
| RED | both far (or one far and the other missing) |
| GREY | nothing read |

**Only RED blocks** (`'mismatch'` reaches `person_red` and the owed lines). AMBER and BLUE go to the reviewer.

**Owner rulings, 23 Nov 2026 (later the same evening), which override the table above:**
- **No number on the document = name alone, as today.** When the certificate (or the reference IC) gives no IC number for a row, the name decides the row: an exact or close name is GREEN and a far name is RED, exactly as the name-only check does now. In production on 23 Nov, 11 of 246 certificates had no child number and 12 had no mother number. The "one value missing = AMBER" line now applies only when the NAME is missing and the number is present.
- **The ward row on a guardianship letter is always judged on the name alone**, because letters never print the ward's number. The guardian row uses name + IC number.

## Part B: the relationship verdict from two rows (the chip)

The link "this parent is the student's parent" combines the child row and the parent row:
- Chips have no blue: BLUE shows as AMBER.
- G+G = G.
- B+B = G only when both rows carry an exact IC number; otherwise AMBER.
- G+B, G+A, A+B, A+A = AMBER.
- RED + anything = RED.
- GREY + GREEN = GREY while waiting (the other document is not uploaded, or the read has not run), and AMBER
  once everything is in but that part could not be read.
- Both GREY = GREY ("send a clearer copy", as `relationship_doc_unreadable` does now).

GREEN → `'match'` (the relationship is confirmed: `relationship_confirmed`; the student sees the tick).
AMBER/GREY → no claim (`'pending'`-like; the officer looks; the student sees nothing worrying).
RED → `'mismatch'` (the only state that asks the student to act).

This **replaces** the 8 Sep BrightPath #19 ruling ("exact number + differing name is amber, never green")
for CLOSE names; exact number + FAR name is now BLUE, which still shows amber on a chip. The #23 ruling
("one cell alone is not green") is kept: a row with only one value read can never be GREEN.

**One home.** Today the case-page chips (`doc_checks.student_bc_check` / `student_guardianship_check`, via
`buckets._combine_relationship`) and the decision (`relationships._bc_link` → `member_relationship_status`,
used by the verdict and by `student_income_ic_check`) score separately. After this sprint both read ONE scoring
function. The IC-number chain (`chain_verified_earner`, #9) and the TD-390 deferral keep working as they do now.
The web (`checklists.tsx` `relPill`, `cockpitDocFacts.ts` `factStatus`, `IncomeWizard.tsx` student tick) renders
what the server serves; add no second copy of the rule in the browser.

## Part C: the owed line says which check failed

Split `parent_ic_person_mismatch`: a parent IC that is red only because the LINK to the student failed
(`name_status` mismatch, with the proof name/number not mismatched) gets its own code and wording, for example
"A birth certificate (or guardianship letter) that links this parent to them — the names or IC numbers on it
don't match". Keep `parent_ic_person_mismatch` for a real IC-vs-income-proof mismatch. Keep `doc_red_keys.py`
as the one home for the keys and both readers (consent gate, Action Centre) in step
(`tests/test_doc_red_keys_drift.py`). en/ms/ta for every new or changed string; ms/ta are drafts for Sol to read,
so list them in the report.

## Part D: each tile leads with the reason for its band

The rule (the owner's, following the 17 Nov Academic fix 68f08dfc2 and #804): the tile's top line is the item
that decides the band. For income: when `str_unsure` or `str_mismatch` decides the band (`_place_income_verdict`),
the STR item comes first in `unresolved`. Do it on the server (item order), not with a browser priority list, so the
grey "AI Prediction" line, the tile and any other reader agree. Check the other three facts for the same pattern
(a band set by one item while an earlier, weaker item leads). Fix any real case you find. Otherwise, say there
are none and pin the income case with a test.

## Must hold

- `VERDICT_ENGINE_VERSION` bump (facts move for the same documents). If a registered model's files change,
  `model_versions/<model>.json` + its constant too (`test_model_versions.py`, `test_model_digest.py`).
- No migration expected. If you think you need one, stop and report.
- Additive towards students: no row that passes today becomes RED. Rows may move GREEN → AMBER only where the
  owner's table says so (exact name + far number). List that effect in the report.
- No file over 600 lines; never raise a budget, floor or ledger (split first, in its own commit, moves only).
  `verdict_income_str.py` and the verdict engine are near their limits: check before adding lines.
- Tests: every band and every chip combination; the case-177 shape (dropped letter in a 5-letter word, exact
  child IC) is GREEN; exact name + far number is AMBER, not match; both far is RED; father row unchanged;
  guardianship same bands; the owed-line split; the income lead-line order.
- Comments and commit messages: British English, they/them, no student names, no real NRICs (use made-up
  numbers that pass the DOB check where needed).

## How to work

- Worktree: `/Users/elanjelian/Python/Production/HalaTuju/.worktrees/req78-bc-bands`, branch `req78-bc-bands`
  (from side/laptop 2edab4dab). Commit locally. **Never push.** Never rebase or force anything.
- API tests: `/Users/elanjelian/.venvs/halatuju-py311/bin/python -m pytest` from `halatuju_api` (targeted while
  building; the full suite once at the end through
  `caffeinate -i -m -s python3 /Users/elanjelian/Python/Settings/_tools/test_queue.py -- <command>`).
- Web: `npm ci` inside the worktree's `halatuju-web` (a real directory, never a symlink, never staged). Symlink
  `.env.local` from the main checkout only for `mobile-check`, never stage it, and remove it after. Gates:
  `npm run gates`, `npm run bundle-budget -- --gate`, and `npm run mobile-check` if any UI changed.
- Never re-extract documents. No production writes. Production reads only as `BEGIN READ ONLY` count probes;
  you should not need any.
- Stage explicit paths only (never `git add -A`). No TD numbers: write `TD-NEW-<short-name>`.
- Final commit trailers: `Phone-check: <one plain line>`, `Migration: none`, `Services: both` (or what is true),
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Subjects carry the word "sprint". Honest commit type.
- CHANGELOG entry; `docs/decisions.md` entry for the 23 Nov rulings (replacing #19 for close names; #23 kept).

## Not in this sprint

- The population check across every live application runs through the A5 replay
  (`docs/plans/2026-11-13-a5-replay-owner-steps.md`) after review, on the owner's word. Make the change
  replay-friendly (deterministic, no new I/O).
- No change to STR rules, the salary route or `application_completeness`.
