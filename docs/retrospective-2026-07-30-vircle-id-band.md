# Retrospective — the eWallet-ID band (a DuitNow number can no longer be saved as an eWallet ID)

**Date:** 2026-07-30 · **Commit:** `21d48037` · **Branch:** `feat/vircle-id-validation`
(worktree `.worktrees/vircle-id`) · **Migration:** none
**Brief:** `docs/plans/2026-07-30-vircle-wallet-id-validation-roadmap.md`

---

## What Was Built

Vircle reported two bursary recipients whose stored eWallet ID was actually their **DuitNow
Transfer account number**. Investigating the two surfaced **a third nobody had reported** — app 75
(PRAVIN) — found by the numeric shape of the stored value rather than by any alert. All three were
corrected on production the same day. **July's RM400 had already reached the right accounts**
(Vircle caught the mismatch by hand at the payment-run stage), so no ledger remediation was needed.

The mechanism, which is the whole sprint:

```
800040017680501003     ← DuitNow Transfer Acc No. (18 digits, with a copy button beside it)
8000400176805          ← first 13 = the eWallet ID we actually want
             01003     ← trailing 5 = sub-account index
```

The Action Centre asks for the **last 4 digits** and prefixes `800040017`. A student reading the
**Top Up** screen instead of the **Settings** page types `1003` and produces a perfectly well-formed
13-digit id. This was never "the student supplied a rival identifier" — it is an 18-digit number
truncated, which is why the defence belongs at **entry** and not in a downstream cross-check.

Shipped:

- **The issued band.** `valid_vircle_id` requires the first TYPED digit to sit in
  `VIRCLE_ID_BAND_MIN`–`MAX` (5–9, defined in `settings/base.py`). Every genuine wallet on
  production is 5–7; all three wrong ones were `1`. One function, so the Action Centre and the admin
  cockpit cannot drift. `vircle_id_band()` reads the bounds; `vircle_id_error()` classifies a failure
  as `'duitnow'` or `'format'`.
- **A roll-over warning** when an accepted id sits at the top of the band.
- **`AUDIT vircle_id_set`** (old value, new value, actor) on the cockpit correction path.
- **Student copy that names the field, not the number** — `errorDuitnow` (en/ms/ta) plus the
  assembled 13 digits echoed back as one continuous run with a compare-digit-for-digit note.
- **The 48h Vircle activation email** now asks them to CONFIRM the ID and says why ("we use this ID
  in the monthly payment instruction"), stops asserting the account is inactive, and the CSV gains a
  blank `Correct eWallet ID (if different)` column.

## What Went Well

- **The brief's lessons pass paid for itself twice.** Lesson #5 predicted that
  `test_payments.py`'s `f'{i:04d}'` fixture would break; it broke, exactly once, and was fixed to an
  in-band suffix instead of loosening the rule. Lesson #39 warned that the activation email sits
  **outside** the 113-email golden set; that email now has its own no-unrendered-placeholder test it
  would otherwise never have got.
- **The TD-number collision lesson fired.** I was about to log TD-198; it already existed in both
  trees (the concurrent agent's). Logged TD-199 instead. That check takes ten seconds and has now
  prevented a documented recurring failure.
- **Worktree isolation was not optional here.** The concurrent agent went from one unpushed commit to
  four *during* this sprint, and touched all three i18n files — the exact files this sprint needed.
- **The guard is bite-proven by a test, not by assertion.** `test_band_bounds_come_from_settings`
  widens the band and asserts a known-bad production value then passes.
- **The owner's proposed rule was the one that shipped.** My two alternatives were both worse; see
  below.

## What Went Wrong

**1. I told the owner to route the correction through the cockpit "because it's audited". It wasn't.**
- *Symptom:* advised a slower path for a benefit that did not exist, then had to correct it a turn
  later.
- *Root cause:* I inferred the audit behaviour from its sibling `reporting_date_set` (which does log)
  instead of reading `AdminApplicationFlagsView`. Proximity in a file is not shared behaviour.
- *System change:* the audit line now exists, so the advice is retroactively true. The transferable
  half is in `lessons.md`: an "it's audited" claim is a claim about a specific log line — grep for
  the line, never argue from a neighbour.

**2. I told the owner the relay sheet was stale and needed a manual `sync_vircle_sheet`, and hung a
time-sensitive action off it.** The owner pushed back; `halatuju-vircle-sheet-sync` runs every 15
minutes and had already self-healed.
- *Symptom:* a fabricated operational task, presented as urgent, with a consequence chain
  ("the 48h cron will email Vircle a stale number") that was entirely downstream of the wrong premise.
- *Root cause:* I read `sync_relay_sheet` and a *manual* management command in source and concluded a
  human must run it. I never opened Cloud Scheduler. This is the third instance of the same family in
  this project's lessons (live state asserted from static source) and the existing lessons did not
  stop it, because a management command's existence does not *feel* like a guess.
- *System change:* recorded in `lessons.md` as its own operational trigger — the existence of a
  manual command says nothing about whether a scheduler already runs it; `gcloud scheduler jobs list`
  before describing any manual step as owed.

**3. I evaluated the owner's proposed rule against the wrong artefact and told them it was inert.**
- *Symptom:* I tested whether `{7,8,9}` could separate the *stored 13-digit values* and reported
  "identical to the current rule on all 49 known values". The owner replied "it would prevent this
  though" — and was right.
- *Root cause:* I had modelled the DuitNow number as a rival **13-digit** identifier drawn from the
  same space, without evidence. One screenshot dissolved it: it is 18 digits and *contains* the
  wallet id. The right question was never "can the rule separate the two stored values" but "what
  does a student typing from the wrong field produce, and does the rule reject that".
- *System change:* in `lessons.md` — when a value reaches the database by TRUNCATION, evaluate the
  rule against what the human types, not against the stored result; and get the source artefact
  (the screen) before modelling the failure.

**4. I proposed accepting an 18-digit paste and deriving the wallet id from its first 13 digits.**
- *Symptom:* an idea that would have silently computed a payment destination.
- *Root cause:* I generalised a structure from **one** observed sample, on a money path. It also
  contradicted the owner's stated principle (minimise typing) in the same breath.
- *System change:* withdrawn in-conversation and recorded as a rejected alternative in the brief and
  in `decisions.md`, with the reason (single sample, silent failure mode) so it is not revived. The
  shipped behaviour REJECTS an 18-digit input with a message that names it.

## Design Decisions

Logged in full in `docs/decisions.md` (3 entries):

1. **The band sits on the first TYPED digit (position 10), accepting 5–9** — not a longer typed field
   with position 9 constrained (inert), and not `{7,8,9}` (would refuse 39 of 46 real students).
2. **The bounds are settings, and the rule is allowed to be bounded** because it fails safe — a
   refused legitimate number is loud and recoverable; a silently accepted wrong one moves money.
3. **A DuitNow-shaped input is NAMED and REFUSED, never derived from.**

## Numbers

| | |
|---|---|
| Files changed | 14 (+578 / −26) |
| Migrations | **0** |
| pytest | **3893** scholarship (+10) + **1260** courses/reports — golden masters intact |
| jest | **1184** / 79 suites |
| `tsc` | clean (0 errors in non-test source) |
| `makemigrations --check` | clean |
| Migration ledger vs production | scholarship **136/136**, courses **67/67**, no mid-sequence gap |
| Production data corrected | 3 applications (36, 27, 75) |

## Carry

- **ms/ta first drafts** for `walletIdEcho`, `walletIdCheck`, `errorDuitnow`.
- **Owner, in order:** the one-off sweep asking Vircle to confirm all 46 IDs on file; confirm
  Pravin's `…176929` is activated; create the August run fresh and check the three snapshots before
  the maker signs.
- **TD-199** — the band's ~55-student headroom before roll-over.
- **Held, not scheduled:** the first-time-wallet flag (advisory only, per decisions.md 2026-07-24).
