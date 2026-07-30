# Vircle e-Wallet ID validation — incident brief + sprint roadmap

**Date:** 2026-07-30 · **Status:** ✅ **SPRINT SHIPPED (code complete, not pushed)** — commit
`21d48037`, retro `docs/retrospective-2026-07-30-vircle-id-band.md`. §4b (the first-time-wallet flag)
remains **HELD, not scheduled**. · **Migrations:** none

---

## 1. The incident

On 2026-07-29 the Vircle team reported that two bursary recipients had, in the words of
their message, *"provided their DuitNow transfer account numbers instead of their Vircle
e-Wallet IDs"*. Vircle caught both before payment, so **the July money reached the right
accounts** — no ledger remediation was needed.

Investigating the two reported cases surfaced **a third student nobody had reported**
(app 75), found by the shape of the stored value rather than by any alert.

| App | Student | Stored (wrong) | Corrected to |
|-----|---------|----------------|--------------|
| 36 | Thavasri A/P Kumarasamy | `8000400171003` | `8000400176805` |
| 27 | Sanjana A/P Kalianakumar | `8000400171009` | `8000400177350` |
| 75 | Pravin A/L Kannan | `8000400171001` | `8000400176929` |

All three were corrected in production on 2026-07-30 via guarded `UPDATE` (old value in the
`WHERE` clause). Post-correction state verified: 46 wallets on file, 0 in the suspect band,
0 failing the format rule, 0 duplicates.

### Why nothing caught it

`payments.valid_vircle_id` accepts any 13 digits beginning `800040017`. All three wrong
values satisfied that. The check was structurally blind to this error.

## 2. The mechanism (this is the load-bearing part)

The Vircle app's **Top Up** screen shows a *DuitNow Transfer Acc No.* of **18** digits,
whose **first 13 digits are the student's e-Wallet ID**:

```
800040017680501003     ← DuitNow Acc No. (18 digits, with a copy button beside it)
8000400176805          ← first 13 = the e-Wallet ID we actually want
             01003     ← trailing 5 = sub-account index
```

The Action Centre asks for the **last 4 digits**, prefixing `800040017`. A student reading
the DuitNow field types its final four — `1003` — producing `8000400171003`. That is
exactly the value that was stored. Sanjana (`1009`) and Pravin (`1001`) match the same
shape, all three ending `100x` from sub-accounts `0100x`.

**So this was never "the student supplied a rival identifier".** It was an 18-digit number
truncated to its last four. The defence therefore belongs at the point of entry.

Two false leads were pursued and discarded before the screenshot arrived; recorded here so
they are not revisited:

- *"DuitNow numbers occupy the same numeric space and will eventually collide with the
  wallet band."* **Wrong** — they are 18 digits and derived from the wallet ID. They never
  occupy the 13-digit space at all.
- *"The `…1710xx` cluster is a distinct DuitNow number family."* **Wrong** — it was
  truncation debris. It located app 75 correctly, but for the wrong reason.

## 3. The fix (owner's proposal, evidence-tested)

Constrain the **fourth digit from the right** — the first of the four the student types — to
`5-9`:

```
^800040017[5-9][0-9]{3}$
```

| Rule | Genuine wallets | Truncated DuitNow |
|------|-----------------|-------------------|
| Current `^800040017[0-9]{4}$` | 46/46 pass | 3/3 pass ❌ |
| **Proposed `^800040017[5-9][0-9]{3}$`** | **46/46 pass** | **0/3 pass ✅** |

Every genuine wallet has `5`, `6` or `7` in that position; every truncation artefact had
`1`. `8` and `9` are admitted for forward headroom.

**Why this beats the alternatives considered:**

- **No guide change** — the "3 Things" slide deck and the 4-digit field stay exactly as they
  are (owner constraint, 2026-07-30).
- **No extra keystroke** — owner principle: *"we want the student to type as little as
  possible because it may create an error during entry."*
- Rejected: widening to 5 typed digits with position 9 constrained to `{7,8,9}`. Tested —
  behaves **identically to the current rule** on all 49 known values, because position 9 is
  `7` for wallets *and* DuitNow numbers alike.
- Rejected: `{7,8,9}` on the fourth-from-right. Would reject **39 of 46** genuine students.
- Rejected: accepting the full 18-digit number and deriving the wallet ID from its first 13.
  More typing (against the principle), and the structural assumption rests on a **single**
  observed sample — a silent wrong-derivation would move money.
- Rejected (owner, 2026-07-30): asking Vircle to return the e-Wallet ID against student
  identity so the student never types it. Declined — the guide is clear and is not changing
  yet. **Do not re-propose.**

**Single-point change:** both write paths — the student Action Centre
(`views.py` `_resolve` → `payments.valid_vircle_id`) and the admin cockpit correction
(`views_admin.py` `AdminApplicationFlagsView`) — validate through the same function.
No backfill: all 46 existing IDs already satisfy the new rule.

### Known limits of the rule (accepted, not defects)

1. **Finite headroom.** Wallets span `…175129` → `…177350`: 2,221 numbers consumed across 46
   students, because the sequence advances with Vircle's whole customer base, not ours
   (~48 numbers burned per student we onboard). With 2,649 left before `…179999`,
   roll-over into `800040018xxxx` is roughly **55 students away — plausibly the next
   intake**. Hence the band belongs in settings, not in a literal.
2. **It fails safe.** When the band is exhausted a legitimate new number is *rejected* —
   loudly, with the student reporting it — never silently accepted and paid elsewhere. This
   is why the headroom limit is tolerable.
3. **It cannot catch an in-band typo.** A student reading `6805` but typing `6905` produces a
   valid-looking wrong number. No format rule reaches that; sprints 2 and 3 do.

## 4a. Lessons applied (sprint-start step 2 — read before coding)

Read `docs/lessons.md` in full and grepped `docs/decisions.md`. These are the entries that bear on
THIS scope, with what each changes:

1. **"A flag is NOT live just because the env var is set — it must be read into Django settings"**
   (2026-06-15; `CHECK2_AUTO_GENERATE` was permanently False for weeks). → `VIRCLE_ID_BAND_MIN`/
   `_MAX` **must be defined in `settings/base.py`** beside `VIRCLE_ID_PREFIX` (line 232), not merely
   read with `getattr`. Grep the settings package for the names before touching any env var.
2. **"A byte-identity snapshot only protects the functions it actually renders"** (2026-07-24). That
   lesson names **`send_vircle_activation_email` specifically as OUTSIDE the 113-email golden set** —
   an earlier refactor left `{month}` unrendered in it and the goldens stayed green. → editing this
   email has NO existing regression protection; add a targeted test asserting the rendered body
   contains the new ask AND that no `{` placeholder survives unrendered.
3. **"A route/branch-specific requirement needs route-specific copy"** (2026-06-12, the
   `income_proof_missing` case). → the band failure gets its OWN message; it must not reuse the
   generic `scholarship.actionCentre.vircle.error`, which would tell a student to "check the number"
   when the number is fine and the field was wrong.
4. **"i18n parity only proves en==ms==ta — it does NOT prove a key EXISTS"** (Sponsor R7) + **"ship a
   CLASS-covering parity guard with the first fix"**. → new keys go in all three locales and must be
   reachable by the static scanner. Watch the namespace-prop trap (2026-07-28) if any key is
   assembled at runtime.
5. **"Changing the gate breaks every complete-app test helper at once — grep for ALL of them"**
   (TD-085 S1) + **"a guard failing when you extend a table IS the guard working — teach it, never
   trim it"** (2026-07-29). → **`test_payments.py:611` builds wallet IDs as
   `vircle_id_prefix() + f'{i:04d}'`** (suffixes `0000`, `0001`…), which the new band rule REJECTS.
   `test_payment_endpoints.py:57` and `test_payment_programme.py:51` use the same `_PREFIX + suffix`
   idiom. These fixtures must be updated **deliberately**, to in-band suffixes — not by loosening the
   rule. Run the FULL suite, never new-tests-only.
6. **"A spec's worked examples must become executable tests in the SAME change"** (2026-07-08). → the
   three real production values (`…171003`, `…171009`, `…171001`) become named regression tests, and
   all 46 genuine values are asserted to pass.
7. **"Validate a parser/heuristic against REAL data before deploy"** (L86 / 2026-06-11 / 2026-07-25).
   → already satisfied: the band rule was tested against all 46 live wallets and the 3 known-bad
   values before being proposed. Record the counts in the test, not just the retro.
8. **"A test that ENUMERATES the thing it guards silently narrows"** (Finance role, 2026-07-23). → do
   not freeze a hand-copied list of 46 IDs in a fixture; assert the *rule* against representative
   in-band/out-of-band values plus the three real failures.
9. **"Never pipe `npm run build` to `grep` and read the pipeline's exit code"** (TD-059, cost two
   broken pushes). → capture to a file and read `$?` separately.
10. **"`next build` OOMs on the 8 GB box after a full pytest run; kill stray `node.exe` first"**
    (2026-07-02 / 2026-06-29 / 2026-06-10). → serialise pytest and the web build; treat
    "✓ Compiled successfully" then a worker crash as environmental. (This machine is the 8 GB box.)
11. **"Never run two Claude instances against the same working tree — give each a `git worktree`"**
    (v2.20.0) + **"branch off `origin/main`, never the worktree's local `main`"** (Post-award S4). →
    **mandatory here**: this repo currently holds another session's uncommitted org-requests work and
    an unpushed commit. Work in a fresh worktree off `origin/main`; stage explicit paths, never
    `git add -A`.
12. **decisions.md 2026-07-24 — "eWallet activation is ADVISORY on payment runs, not a gate."** →
    constrains the held first-time-wallet flag: it must be a **warning + acknowledgement**, never a
    hard block. A hard gate would re-litigate a settled decision.
13. **decisions.md 2026-07-21 — activation is tracked only in the sheet's manual column because
    "nothing reports activation back"; `Revisit if:` Vircle exposes a readable status.** → that
    trigger has NOT fired, and the owner has separately declined the process change. The
    confirm-against-Vircle gate stays out of scope on both grounds.
14. **"A blanket `catch {}` hides the cause — preserve the API's field-level 400"** (2026-06-07). →
    the new rejection must reach the student as its own message, not collapse into the generic
    save error.

## 4. Sprint — ONE sprint (revised from three)

The echo-back folded into S1 (the digits were already on screen in two boxes, so it is a
copy-and-layout fix, not a sprint). The pre-sign gate is **held**, not scheduled — see §4b.

**No migration.** Estimated ~14 files; the lessons note that a web sprint here costs "its feature
files plus about a third again in copy", so budget ~18. Well inside the 40-file cap.

### Scope

| Area | Files |
|---|---|
| Band rule + settings | `payments.py`, `settings/base.py` |
| Student rejection copy + echo | `views.py`, Action Centre component, `en/ms/ta.json` |
| Admin rejection copy + audit line | `views_admin.py`, admin i18n |
| Vircle email + CSV column | `emails.py`, `vircle.py` |
| Tests | `test_payments.py`, `test_payment_endpoints.py`, `test_payment_programme.py`, `test_vircle.py` |

### Acceptance criteria

- The three known truncations are refused at **both** write paths (student + cockpit).
- All 46 production wallet IDs still validate; band bounds honoured **from settings**.
- Disabling the band check makes the new tests fail (prove the guard bites).
- `AUDIT vircle_id_set` emitted on a cockpit correction, carrying old, new, actor.
- Activation email renders the new ask with **no unrendered `{` placeholder**.
- Full pytest suite green (not new-tests-only); i18n parity en/ms/ta; `tsc` clean.

### 4b. Held, not scheduled

**First-time-wallet flag** — flag any student being paid at a number that has never successfully
received a payment, as a warning the maker acknowledges before signing. Advisory by decision (§4a.12).
Decide after the one-off Vircle sweep returns: if all 46 are confirmed, its marginal value drops.

## 4c. Superseded — the original 3-sprint split

Sequenced by value-per-risk, not by size. Sprint 1 is the actual fix for the reported
incident and is cheap; sprint 3 is the riskiest because it touches the signed money path,
and its marginal value *drops* once entry is guarded — so it goes last and is deliberately
re-evaluated rather than assumed.

**No sprint carries a migration.** Nothing here is a schema change.

### Sprint 1 — The guard and the trail *(complexity: low)*

**Goal:** a truncated DuitNow number can no longer be stored, and every wallet-ID change
leaves a record of who made it.

**Scope**
- `payments.py` — `valid_vircle_id` band check; band bounds read from settings.
- `settings/base.py` — `VIRCLE_ID_BAND_MIN` / `_MAX` (default `5`/`9`) beside the existing
  `VIRCLE_ID_PREFIX`, so roll-over is an env-var flip and **not a deploy**.
- `views_admin.py` — `AUDIT vircle_id_set` line (old value, new value, actor). Today the
  cockpit correction writes **no** audit line at all, unlike `reporting_date_set`; three
  production wallet numbers were changed on 2026-07-30 with no system record of it.
- `views.py` — student-facing rejection message that *names* the mistake ("that looks like
  your DuitNow transfer number") rather than a generic failure. No guide change; the message
  points at the existing guide wording.
- Roll-over watch: WARNING log when an accepted ID's band digit reaches `9`.
- Tests: the three real wrong values as regression fixtures; all 46 genuine values pass;
  band bounds honoured from settings; audit line emitted.

**Acceptance criteria**
- The three known truncations are refused at both write paths.
- All 46 production wallet IDs still validate (assert against real values, not synthetic).
- Disabling the band check makes the new tests fail (verify the guard actually bites).
- `AUDIT vircle_id_set` appears in Cloud Logging for a cockpit correction.
- i18n en/ms/ta for the new rejection message; ms/ta as first drafts.

### Sprint 2 — Echo the number back *(complexity: low–medium)*

**Goal:** the student confirms the assembled 13-digit ID before it is saved, catching
in-band typos at entry. Costs no extra typing.

**Scope**
- Action Centre: render the full assembled ID (`800040017` + the four typed digits) with a
  confirm step, phrased to match the guide's wording ("Your eWallet ID … 13-digit number").
- `views.py` — accept the confirmation; no new model field (the resolution item already
  carries the flow).
- i18n en/ms/ta; jest coverage for the assemble-and-confirm helper.

**Acceptance criteria**
- The student sees all 13 digits before saving and must actively confirm.
- Declining returns them to the entry field with what they typed preserved.
- No guide change required; no additional digits typed.

### Sprint 3 — Pre-sign wallet confirmation *(complexity: high — re-evaluate before starting)*

**Goal:** a payment run cannot be signed while any included item's wallet ID is unconfirmed
against data Vircle has actually returned.

**Why it is last and why it may shrink:** it touches the live maker→approver→complete chain
(82+ existing payments tests are the regression guard) and the frozen
`vircle_id_snapshot`. Once sprints 1 and 2 guard entry, the residual this catches is narrow.
Decide at sprint-close of 2 whether the full gate is still warranted or a report-only
variant suffices.

**Scope**
- `payments.py` — confirmation predicate + refusal on sign; the rule lives in the service,
  not the view, so a shell caller cannot bypass it.
- Distinguish "confirmed by Vircle" from `vircle_activated_at`, which is **not** trustworthy
  as a gate: on apps 36 and 75 it was stamped by joining the relay sheet on the *wrong*
  number.
- Payment-run detail surface: show which items are unconfirmed and why.
- Tests: all pre-existing payments tests must pass **unmodified** — that is the guard, not a
  claim.

**Acceptance criteria**
- A run containing an unconfirmed wallet refuses to sign, naming the items.
- Every pre-existing payments test passes without edit.
- No behaviour change for a run whose wallets are all confirmed.

## 5. Open items and risks

- **Relay sheet: NO ACTION NEEDED.** An earlier draft of this brief claimed the sheet was
  stale and needed a manual `sync_vircle_sheet`. That was wrong, and the error is recorded
  here so it is not repeated: Cloud Scheduler runs **`halatuju-vircle-sheet-sync` every 15
  minutes, ENABLED**, rewriting the sheet from the database. All three students are `awarded`
  and `VIRCLE_SETUP_STATES = {'awarded', 'active'}`, so the sheet picked up the corrected
  numbers within 15 minutes. The `vircle-activation-request` cron (48h, last 2026-07-29
  01:00) was therefore never going to send a stale number.
  **Lesson: the existence of a manual management command does not mean a human runs it —
  check Cloud Scheduler before asserting an operational gap.**
- **Pravin's activation is unconfirmed.** His `vircle_activated_at` was stamped against the
  wrong number and Vircle confirmed only Thavasri's. He has never been paid, so the next run
  is his first, and a payment to a non-activated wallet bounces. Confirm `…176929` is live.
- **No open payment run exists** (13 cancelled, 3 completed). The August run must be created
  fresh; check the three snapshots before the maker signs, since the snapshot freezes at
  creation and the CSV prefers it over the live record.
- **Concurrent work in the repo** as of 2026-07-30: unpushed commit `a1552464` plus
  uncommitted org-requests changes belonging to another session. Reconcile before Sprint 1
  branches.

## 6. Rationale for the division

Three sprints, splitting on **who is protected and at what cost**: sprint 1 is a server-side
guard with no user-visible surface (cheap, ships the incident fix); sprint 2 is a
student-facing confirmation (needs trilingual copy and its own review); sprint 3 is a
control on the signed money path (needs the payments suite as its guard, and should be
re-scoped once 1 and 2 have reduced what it must catch).

Each is independently shippable and independently useful. Sprint 1 alone closes the reported
incident.
