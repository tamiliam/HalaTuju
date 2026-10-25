# Retrospective — TD-401 + TD-402, and the owner's ruling: an STR is income proof only when it matches someone's IC (2026-10-25)

Commits `014cae5b` (TD-401 + TD-402), `4f582222` (the ruling, salary route) and `76a07ee7` (the ruling,
both routes), with the lead's `ca5dc8b8` (TD-404 / TD-405 raised); rebased onto `0e0f7e44` and pushed to
main 2026-10-25. Built in the worktree `ai-outage`, with three review rounds and an owner ruling before the
push. CHANGELOG: "TD-401 + TD-402 — two holes in the submission gate". Decision: `docs/decisions.md`
2026-10-24, item 3c. Register: TD-401 and TD-402 closed; TD-403, TD-404 and TD-405 raised.

## What Was Built

- **TD-401 (identity).** A student MyKad read with a name but NO NRIC used to pass `ic_identity_blockers`
  on the name alone. It now answers `ic_unreadable` (or `ic_service_down` while a second opinion is
  deferred): identity rests on the CARD's number. The lead counted production first — zero live student
  ICs in that state. `VERDICT_ENGINE_VERSION` 2026-10-25.2.
- **TD-402 (money).** The gate's "one complete cluster is enough" early return and the consent-time route
  reconcile read `salary_income_satisfied(str_must_match=True)`: a cluster carried only by the household
  STR counts there only when a card has MATCHED the STR's recipient.
- **The owner's ruling (option A), one rule on BOTH routes, superseding F1 for the GATE.** For an STR no
  card matched, `services.blockers._unmatched_str_asks` asks: the IC of each roster member who could
  settle it (`parent_ic_missing:<member>` — the card TD-309 already offers on the Documents page, from the
  same `str_ic_slots` rule); with every card on file, the stranger rule's `str_not_household`, else a
  clearer document (`income_document_unreadable`), or "try later" (`ic_service_down`) when that read is
  ours to finish; on the salary route with no IC to ask, the member's own income. The verdict keeps F1's
  lenient reading (no band moves, no version bump).
- **Tests.** `test_td401_td402_gate_holes.py` (the reviewers' probes 1, 1b, 1c, family 3, genuine families,
  the unread and outage-deferred STR, the verdict unchanged); the TD-285 matrix gains a pinned layer
  (`_since_str_ruling`) over its frozen record; `factories.matched_str_pair` for fixtures that need a
  household's own, READ STR.

## What Went Well

- **Every fix and every branch was bitten.** Each was reverted by a fault-injection script (bytes
  restored, SHA-256 checked) and its own test went red — including the three branches of the both-routes
  rule (the STR route skipping it, the salary route never asking the roster IC, our outage blamed on the
  student).
- **The frozen record stayed frozen.** The TD-285 matrix pins what F1 moved; rather than editing it, the
  new ruling sits on top as one small, separately pinned step, so a reader can still see both rulings.
- **The UI question was answered from the code, not assumed.** Before asking the student for a
  non-working mother's IC, the builder confirmed TD-309 already serves that slot on both routes from the
  same rule — so no frontend change and no dead end.

## What Went Wrong

1. **The builder's family-3 claim was untested, and wrong.** The report on `4f582222` said family 3 "asks
   for the mother's IC". The test behind it built a DIFFERENT family — the mother working — while the
   reviewers' family 3 was the father working, the STR naming the non-working mother; for that family the
   commit asked for the FATHER's income, the wrong document. *Root cause:* the builder wrote its own
   fixture from a label ("family 3") without the reviewer's scenario in front of it, then reported the
   label, not the scenario it had tested. *System change:* a probe the reviewer names is copied into the
   test VERBATIM (who works, whose STR, whose IC is missing) and the test's docstring states that
   scenario; the report names the scenario, not the number. Family 3 is now pinned as the reviewers
   stated it, including her card clearing the gate.
2. **The rule was first scoped to one route, though the owner's ruling was "both routes".** The first
   fix closed probe 1 on the salary route only; the same family switching to the STR route (earner = the
   mother, the father's IC never uploaded, a stranger's STR) still passed with no blocker — the STR route
   checked that the STR, the earner IC and the relationship document were PRESENT, never that a card
   matched the STR. *Root cause:* the fix was scoped to the code path the probe went through, not to the
   rule; the gate has two doors into the same state (submission with an STR carrying income), and only
   one was listed. *System change:* one helper (`_unmatched_str_asks`) serves both routes; the probe is
   pinned on both (1 and 1c); lesson recorded — list the doors per RULE.
3. **Fixtures silently relied on never-read IC + STR pairs passing the gate.** Six "ready application"
   fixtures (the factory walk in `test_factories`, `test_phase_c`, `test_layer0_snapshot`,
   `test_admin_scholarship`, `test_details`, `test_consent`) built the STR route from documents nobody had
   read. They passed only because the gate counted an STR it could not judge — exactly the hole being
   closed — so for months they could not have caught it. *Root cause:* a fixture that means "a genuine
   family" was built from presence alone, and presence was what the lax gate checked. *System change:*
   `factories.matched_str_pair` builds the household's own STR and its matching card, both READ; every
   such fixture uses it; the never-read pair is now its own test, asserting "try later".

## Review (sprint-close step 4b)

No `/code-review` run, by the coordinator's instruction: three adversarial review rounds and an owner
ruling, each answered in full in the worktree —
- **Round 1 (on `014cae5b`):** nothing blocking; the salary-route per-member hole flagged by the builder
  was real — owner ruled A.
- **Round 2 (on `4f582222`):** the STR-route dodge (probe 1c); family 3 asked for the wrong document;
  TD-403 to raise (a stale STR in the household's own name passes; owner to rule). All fixed and bitten.
- **Final review (on `76a07ee7`):** nothing blocks; probes 1 / 1b / 1c / 2-7 and family 3 as expected;
  TD-309 slots confirmed on both routes; production exposure four not-yet-submitted students with an STR.
  The lead raised TD-404 (AK / romanisation name variants) and TD-405 (a parent left off the family form).

## Numbers

- API (`python -m pytest -q -n auto -p no:cacheprovider`): 8,720 → 8,732 passed / 3 skipped in the
  worktree; 8,750 / 3 skipped on the rebased tree (by the lead).
- Web (by the lead, rebased tree): 4,440 jest / 276 suites, gates green (no web change).
- No migration. `VERDICT_ENGINE_VERSION` 2026-10-25.2. Register: 133 open.
