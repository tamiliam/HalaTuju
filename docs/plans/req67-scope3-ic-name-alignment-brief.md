# Request #67 scope 3 — one name: align to the IC, lock it, and the 559 short read

Owner-approved 14 Nov 2026 ("go"). Bug fix under #67, no charge. Identity change: Opus builds, Opus adversarial review, owner phone check before live.
Executor: Opus agent. Worktree: `scratchpad/wt-req67b`, branch `req67-ic-name` (on origin/main cdb6d54be + one local docs commit).

## Verified facts (prod, read-only, 14 Nov)
- The student signs the truthfulness declaration at `/apply` (no uploads there). At submit, `services/intake.py` (~L160-172) promotes `declaration_name` to `profile.name`. So the two names start equal.
- After submit the student can still edit `name` on `/profile` (`apps/courses/serializers.py` profile serializer, `name` writable; `views/profile.py` `put`). The apply-form sync (`services/profile_sync.py`, `'name'` in the synced fields) also writes it. Nothing compares it with the signature or the IC afterwards.
- 8 of 795 signed applications have `profile.name` ≠ signature (case/space-normalised); all 8 edited after signing; 7 of the 8 are IC-locked (`nric_verified`). The lock covers the number, not the name.
- App 177: signature (5 words) == IC read exactly; `profile.name` (3 words, edited 6 Nov) ⊂ IC → page shows "partly matches". The header (`serializers_admin/names._full_name`) shows the signature, the IC check (`verdict_identity`, `identity.compare`, `anomaly_engine`) uses `profile.name`.
- App 559 (ic docs 5538/5539, both `capture=deterministic`, no second opinion): card name is 4 + 3 words on two lines; the layout read refuses (line gap 3.09 lh) so the old 4-word read stands. `profile.name` == signature (7 words). `name_match` → `partial`, so `_should_gemini_ic` (vision/ic.py L19) never escalates, and even if it did, `_merge_ic_reads` (L39) only takes Gemini's name when the deterministic read is a `mismatch`.
- The IC lock: `vision/ic.py::_lock_nric_if_confirmed` (end of `run_vision_for_document`) → `identity.compare` / `identity.locks_now`; stored one-way in `StudentProfile.nric_verified`. Refusal payload pattern: `profile_claim.NRIC_LOCKED` (403, code `nric_locked`). `/profile` GET serves `nric_locked`, `ic_flags`, `ic_card_name`; payload key order is pinned by tests.

## Owner-settled decisions
| # | Decision |
|---|---|
| D1 | The IC name becomes the one name. The signature (`declaration_name`) is NEVER rewritten — it is a verbatim legal record. |
| D2 | Align only when safe: card NRIC == `profile.nric` exactly; the read is clean (no `vision_error`; not stale-kept; no pending/failed second opinion — see `read_errors` / `ic_second_opinion_deferred`); the IC name `name_match == 'match'` against `profile.name` OR against the signature of any of this profile's applications. Then set `profile.name` to the IC name (save() upper-cases) and log the old value. No match → change nothing. |
| D3 | Lock the name with the existing stored lock — no new column, no migration. When `profile.nric_verified` is true, a STUDENT write that changes the name (profile PUT, apply-form sync, the submit-time signature promotion) is accepted only if the new name `name_match == 'match'` the latest live IC read; otherwise the profile PUT is refused 403 with code `name_locked` (mirror `NRIC_LOCKED`; message: name is verified against the IC, contact support to change it), and the sync/promotion silently keep the stored name. Unchanged names always pass. Admin/staff edit paths are untouched. |
| D4 | 559 fix: escalate to the AI second reader when the IC read's name is a strict SUBSET of the typed name (fewer canonical tokens, `partial`) — student `ic` cards only. In `_merge_ic_reads`, take the AI name when it is `match` against a reference name and the deterministic read is not `match`. A confident deterministic `match` is still never overridden. Parent cards keep today's behaviour. |
| D5 | One-off pass: a management command (dry-run by default, `--apply` to write) that runs the D2 alignment for each profile's latest live student IC. Output: counts and application ids only — never names or NRICs. |
| D6 | Ordering inside `run_vision_for_document`: align (D2) BEFORE `_lock_nric_if_confirmed`, both in the same never-raise try. |

## Phases
1. **API rule.** A single home for the name rule in `apps/scholarship/identity.py` (e.g. `align_name_to_ic(doc)` and `name_change_allowed(profile, new_name)`), called from `vision/ic.py` (align) and from every student write path (lock). Log the change: a `StudentActivity` row (internal, no PII in `body` beyond what existing activity rows already hold — check how they record a name change; prefer `meta` with old/new) and a logger line with ids only.
2. **559.** `_should_gemini_ic` + `_merge_ic_reads` per D4. Keep `IC_GEMINI_FALLBACK_ENABLED`.
3. **Web.** `/profile` (and the apply form's name field if it reads the same profile value): when the name is locked, show it read-only with the same padlock and wording pattern the NRIC uses; serve a `name_locked` key on the `/profile` payload (update the key-order pins). EN/MS/TA strings, British English. Handle the 403 `name_locked` code.
4. **Command** per D5, with tests.
5. **Tests.** Regression tests for: 177's shape (short profile name, signature == IC → aligned, then match + locked); 559's shape (4-of-7 read → second opinion asked → 7-word AI read taken); no-align when NRIC differs, read errored, or neither name matches; signature never changed; locked PUT refused unless it equals the IC; sync/promotion keep the locked name; parent cards unaffected; the lock still one-way. Targeted tests while building; the full api suite once at the end (`python /Users/elanjelian/Python/Settings/_tools/test_queue.py -- <cmd>` if it works on this machine; otherwise run it directly), plus the web tests that touch `/profile`.
6. **Docs.** CHANGELOG entry; a short decisions.md paragraph after the existing #67 "Re-read after release" paragraph.

## Commit
One or two commits, explicit paths only (never `git add -A`), message prefix `fix: request #67 (scope 3) - ...`, ending with:
```
Phone-check: open application 177 - the IC check shows "matches" and the name has a tick
Services: both
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```
(drop `Services: both` to `api` if the web is untouched). Do NOT push, do NOT take a TD number, do NOT touch production. Do not edit CLAUDE.md or settings.

## Risks
- Overwriting a correct typed name with a misread: guarded by exact NRIC + exact `match` to a typed name + clean read.
- Locking a student out of a genuine correction: they can always set the name to the IC's; anything else goes via support (admin path unchanged).
- More AI reads (D4): only student ICs whose read is shorter than the typed name; small.
- Payload key-order pins and the web `/profile` tests will need updating.
