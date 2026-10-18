# Retrospective — sources and referral partners, Sprint A: two independent columns on the student (2026-10-18)

Decision: `docs/decisions.md` 2026-10-09 ("The student record has two independent columns: source and
referral partner"). Roadmap: `docs/plans/2026-10-09-sources-and-referrals-roadmap.md`. Cutover:
`docs/scholarship/two-columns-cutover-sql.md` (courses `0078_two_referral_columns`, migrate-first).
Commits `bfa547d9` (the sprint and its review fixes) and `4570eb8f` (the back-edge fix after the
rebase) — live 2026-10-18, api revision `halatuju-api-01119-l65`. Written late (at Sprint B's start),
from the CHANGELOG, the roadmap, the decision and the lead's cutover reading.

## What Was Built

- **Two INDEPENDENT columns on the student.** `StudentProfile.source` (new) = what the bursary "Who
  referred you?" form named, NULL for a fixed choice; `StudentProfile.referred_by_org` (kept) = the
  REFERRAL PARTNER whose `?ref=` link brought her. Neither writer touches the other
  (`apps/courses/referral_links.py`).
- **Referral partners marked.** `PartnerOrganisation.is_referral_partner` (`db_default=False`, so the
  image already serving could still insert a source), backfilled from the `partner`-role logins.
- **The writers.** The bursary submit writes the source only; `?ref=` writes the referral partner only,
  first touch, active referral-partner rows only; `PUT /profile/` ignores the code. The legacy chip
  keeps two writers and can no longer be overwritten by a sign-in once she has applied.
- **The witness readers** (`_resolve_witness_org`, the witness authority check, the cockpit pill) read
  "source, else referral partner" — unchanged for every student whose answer named a source.
- **No web change**: the server made the per-sign-in resend harmless, as it had to for bundles
  already in browsers.

## What Went Well

- **The live bug is gone.** A student who picks CUMIG on the bursary form no longer lands on CUMIG's
  course-selector list, where two `partner` logins see NRIC, phone, address and household income.
- **The cutover matched its owner-approved shape.** Lead's production reading at the cutover: `cumig`
  marked (the only row, 2 logins); **122** profiles got a source; **109** links to non-partner rows
  went to the backup table `referral_link_backup_20261009` and were cleared; **CUMIG's list stayed at
  254**, including the 13 bursary applicants who picked CUMIG (owner: "Filled"). The figures grew
  from the 2026-10-09 reading (S = 108, N = 95) because applications kept arriving in the nine days
  between build and cutover — re-reading the pre-checks immediately before applying (lessons.md
  2026-10-09) is exactly what made that a non-event.
- **The adversarial review found no blockers** and its should-fixes landed before the push: the
  deploy-window guard (an ASSERTED pre-check that no open gift offers `cumig`), the stricter
  `referral_partners()`, the `?ref` code shape, and an end-to-end witness-authority test.
- **Every guard was bite-checked** — each of the six key rules broken on purpose turned its test red.

## What Went Wrong

1. **The full suite went red after rebasing onto the staff-lifecycle commit.** Symptom: on the rebased
   tree `test_code_standards.py` failed — the `courses → scholarship` import count read 18 against a
   budget of 17. Root cause: Sprint A had added one lazy `courses → scholarship` import
   (`referral_links` reading `gift_sources.FIXED_CODES` and `partner_comms.HOUSE_ORG_CODE`) when the
   budget stood at 20; the staff-lifecycle sprint, landing first, tightened the budget to 17 by
   collapsing its own imports into one door. Each change was green alone; together they were one over.
   Fix (`4570eb8f`): `referral_links.RESERVED_CODES` became a PINNED COPY of the four codes, with a test
   asserting it still equals both originals — the back-edge did not grow. System change: a budget that
   a parallel session can tighten is re-measured AFTER the rebase, on the merged tree, before the push
   (the gate's own command line), never assumed from the pre-rebase run. Recorded in `docs/lessons.md`
   by this retro's sprint.
2. **The retrospective itself was written nine days late**, at the next sprint's start. Root cause: the
   sprint was built and reviewed on 2026-10-09 but went live only on 2026-10-18, and the close step
   (retro) waited for "live" and was then forgotten. System change: the retro is written at BUILD
   close with a "not yet live" line, and the live step only appends the cutover figures.

## Design Decisions

- **A boolean marker, not a `kind`:** one row (`cumig`) is a source AND a referral partner, and a tenant
  is already derived (`tenants()`); a single-valued kind could not say "both".
- **`referred_by_org` kept its name** as the referral-partner column: a rename costs a live-table
  column rename and every reader, for no behaviour.
- **Ignore, not refuse, a client `referral_source` on `PUT /profile/`**: a stale bundle would lose its
  whole save to a 400.
- **"Filled" (owner):** the 13 CUMIG pickers keep both columns = CUMIG, knowing the partner logins keep
  seeing them; new picks stop reaching the list.

## Numbers

| | Before | After |
|---|---|---|
| pytest (`-n auto`) | 8260 passed / 3 skipped (base `fda0d7ed`) | 8289 / 3 (review fixes); 8347 / 3 on `main` at `4570eb8f` (with staff lifecycle) |
| jest | 4221 / 259 suites | 4221 / 259 (no web change); 4245 / 261 on `main` (staff lifecycle) |
| Migration | courses 0077 | courses 0078 (migrate-first, ledger row recorded) |
| Production cutover | — | 1 referral partner marked; 122 sources set; 109 links backed up and cleared; CUMIG list 254 (13 "Filled") |
| `courses → scholarship` imports | 17 (after the staff lifecycle sprint) | 17 (the pinned copy; 18 before `4570eb8f`) |
| Adversarial review | | 0 blockers; should-fixes all fixed before the push |
