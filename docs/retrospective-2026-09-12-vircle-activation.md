# Retrospective — Vircle tells us when an account goes live (2026-09-12)

Branch `fix/vircle-activation-status`, worktree `.worktrees/vircle-v2a`. **api only, NO migration.**
Commits `83b2855b`, `1f2c4ecf`, `bb1f7de1`. Deployed and verified: build `c8f5b112` on `bb1f7de`,
serving **halatuju-api-01036-6kh** (the running image digest matched this commit's tag, checked
rather than assumed — other agents deploy this repo).

## What was built

Vircle's inbound webhook delivered six eWallet ids on 2026-09-11 and **no activation**. The wallet
half worked; the activation half was deaf.

- **Their activation column is spelt `QR Activated Date`** and our alias list did not accept it.
  One word short, and a date they sent would have been discarded in silence.
- **That column is empty on all 64 rows of their own export.** They never fill it. What they fill
  is **Status** — `Done` once an account is live, `Pending Vircle Activation` before. Owner ruling:
  *"Done is activation. The date you receive the confirmation is the activation date."*
- So a `Done` row stamps `vircle_activated_at` (its own date when present, else arrival), and an
  unrecognised status stamps **nothing**.
- **The relay sheet's "Activated On" column changed direction** — hand-typed until now, written
  from the database from now on.
- **The 48-hour chaser is deleted**: two commands, two cron doors, an email, a CSV, the sheet→DB
  sync and four settings. ~500 lines.

## What went well

- **The owner's export settled three open questions in one file**, and each answer was the opposite
  of a reasonable guess: the status column is not about DNQR, the QR date column is never filled,
  and the pink "Pending" screenshot was two days stale.
- **Every bite-check bit.** Relaxing the status comparison to a presence test failed exactly the
  pending test and nothing else.
- **The direction flip was proved safe before it shipped**, not after — see below.

## What went wrong

**1. I asserted the owner had typed dates into the sheet, and they had not.**
*Symptom:* I built a migration step ("harvest the six manual dates before flipping") and was one
command from running a production job for a dataset that did not exist. *Root cause:* the owner
wrote *"For the six, we have done it manually"* and I read "manually" as "typed into our sheet"
rather than "handled by hand with Vircle" — an inference, presented as a fact, about data I could
have queried. *Fix:* the database was one query away the whole time and disagreed with my reading;
**state which source a claim about DATA came from, and if the answer is "the owner's sentence", ask
before acting on it.**

**2. My own new test read `.date()` off a stored datetime.**
*Symptom:* `test_a_dated_row_keeps_its_own_date_rather_than_today` failed on its first run, expecting
1 March and getting 28 February. *Root cause:* midnight in Malaysia is the previous day in UTC —
TD-209's fourth appearance, in a test written by the person who had just read the TD-209 note.
*Fix:* the lesson is already in `lessons.md`; what this adds is that **it bites in TESTS as readily
as in code**, so the assertion carries a comment saying so.

**3. A near miss worth naming: the direction flip could have blanked real data.**
Column I already held dates for other students. Flipping the sheet to be written from the database
would have erased every one of them if the database did not already hold them. It did — the retired
cron had harvested them, verified by matching four of them cell-for-cell before the push. *Fix:*
**before turning a hand-kept column into a mirror, prove the source already holds what the mirror
shows** — one query, and it is the difference between a tidy-up and a data loss.

## Design decisions

Logged in `docs/decisions.md`: the status word as the activation signal; the column-I direction
flip; retiring the chaser with its consequence accepted rather than hidden.

## Live data corrected the same day

- **Six students** activated 11 September, stamped at the arrival time of their `Done` rows.
- **Rishvin (#114): `8000400181851` → `8000400183456`.** The old id was his **father's** account,
  keyed in by hand because he could not register with his own IC. He has since opened his own and
  had the father's suspended. BrightPath confirmed with him that all **RM600** reached him. The
  payment-run snapshots keep the old id, as the historical record must.

## Found and handed to BrightPath, not fixed here

**Four rows in Vircle's Recipients table carry another student's MYKAD** — Ambbrishbusen,
Bhavatharani, Darshan, Divashini A/P Murugan. Names and wallets are right; the IC cell is not. We
match on IC, so those rows point at the wrong student; only the never-overwrite guard stands between
that and a wallet on the wrong record. Kulaly is raising it with Vircle.

## Numbers

pytest **6524** (the retired tests went with the code they covered) · `makemigrations --check` clean
· 1 build, api only, web correctly silent · 0 error logs since deploy.
