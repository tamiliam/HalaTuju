# Retrospective — STR route no longer blocks the household salary picture (2026-07-16)

Owner live-review off #117: a retired father, no Check-2 follow-up about his pension. Investigation
found the STR route was silencing the income-completeness asks for the STR-recipient parent.

## The finding

`income_engine._parent_has_income_evidence` had an STR branch: on the STR route, the STR-recipient
parent (`income_earner`) with a live STR doc counted as "income-evidenced". That is right for the
means test (the STR is dispositive), but it also fed the three Check-2 completeness asks — so a
retired STR-earner never got the pension ask (#117), an informal STR-earner never got the ask-first
clarify, and a formal STR-earner was never asked for their salary slip. The STR proves the household
is B40; it says nothing about that parent's own pay/pension. Net effect: an incomplete household
salary picture in the sponsor profile.

**Not the stage gate, not the clarify cap.** Live data disproved the first hypotheses: a sync on
2026-07-14, while #117 was still `profile_complete`, raised two *new* queries yet skipped the pension
one — proving the blocker was the STR-evidence mask, not the stage or the 3-clarify cap.

## What was built

Owner rule (2026-07-16): the STR route must not stop the system getting the **complete salary
picture of the household** — inquire about a pensioned/working father or mother, STR earner or not.
Explicitly NOT about moving anyone out of STR.

- **`_member_income_documented(app, member)`** — the STR-ignoring evidence check (salary slip / EPF /
  IC-number chain). `_parent_has_income_evidence` keeps the STR branch (means-test "status known")
  and delegates its documented part to the new helper — so the two notions are now separate:
  "economic status known" (STR-aware, drives the household-size tick) vs "income document on file"
  (STR-ignoring, drives the completeness asks).
- The three STR-earner asks open, cleanly partitioned: **pension** (`pension_members`, the #117 fix),
  **informal** (`informal_income_members` → ask-first clarify, no payslip dead-end), **formal**
  (`str_earner_income_document_gap` → salary-slip request wired into `_gap_sets`).

## What went well

- **Separating "status known" from "document on file" protected the concurrent agent's shipped
  household-size verified tick.** The tick reads `household_status_gaps → member_income_status`, which
  stays STR-aware — untouched. Only the soft asks (pension/informal/formal, none of which the tick
  reads) opened up. A test guards this decoupling.
- **Verdict + submission gate verified independent before touching code.** `income_doc_blockers`
  doesn't call these functions; `verdict_engine` doesn't either. So the change cannot hard-block an
  STR family or flip the income band — the exact risk on the STR route (the #45/#63 "STR present →
  salary docs supportive" principle) is structurally out of reach.
- **The informal partition preserved the #130 anti-dead-end.** An informal STR-earner gets the
  ask-first clarify, never a payslip demand.

## What to watch

- **#117 won't auto-fire.** It is already `interviewing`; the machine only auto-asks during
  `profile_complete`. The pension is best raised at interview (an officer still can). The fix helps
  future Completed-stage apps + any of the ~6 retired / ~19 earning STR-earner cases that re-enter
  Completed.
- **Siblings deferred** (owner "parents now, siblings later"): honouring "only siblings who stay and
  eat in the house" needs a roster residency flag — a separate change (field + migration + UI).

## Numbers

- 3 files (income_engine, check2_queries, test_pension); +6 pytest; 2581 scholarship pytest; golden
  masters intact. NO migration, NO FE change, NO new i18n (reuses existing item codes + copy).
