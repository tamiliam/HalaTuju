# Retrospective — the spending page reorganised (S6), 2026-09-11

**Ask.** The owner opened `/admin/spending` and reported four things:

1. no figures as **super admin**, but fine as BrightPath's **organisation admin**;
2. one long page — split it into **Shops / Students / Unsorted**;
3. the tables want the console's **standard paging**;
4. the headings should **sort on click**.

Built in one sprint. No migration, no AI behaviour change, no deploy.

---

## 1 — The refusal was a decision, and reversing it was the interesting part

A super has no `owning_organisation`, and `_SpendingBase` refused `no_org`. That was not an
oversight: S4a wrote it down, with the reasoning *"defaulting to unfenced is how a super with no
org context sees the platform"*.

That reasoning is about a **default**, and does not carry to an explicit scope. So `ALL_ORGS`
exists, `_spending_admin` is the only place that hands it out, and — the load-bearing part — **it
is a sentinel object, not `None`**. Every accident that loses an organisation produces `None`, and
`None` still filters `owning_organisation=None`, which matches nothing. Had the platform scope
been spelled `None`, each of those accidents would have widened a tenant's page instead of
emptying it. `test_None_is_NOT_the_platform_scope_and_still_reads_nothing` is what stops the
sentinel being "simplified" away.

**What made the reversal cheap and honest:** the S4a decision had named its own revisit trigger —
*"a genuine platform-wide spending view is ever wanted"*. The trigger fired. The old reasoning was
quoted, shown not to apply, and the superseded half marked in place rather than deleted.

## 2 — The bite-checks found two real things

**A gap in the endpoint tests.** `spend_report` had six tests proving one tenant never sees
another's money, shops, students or model decisions. Widening `_spending_admin` to give *every*
caller `ALL_ORGS` failed only a test about an admin with **no** organisation. A real `org_admin`
with a real organisation would have seen every tenant's students' purchases through the live
endpoint, silently, with a green suite. The service tests were right; they answered a different
question than the change put at risk. Fixed at the door, with another tenant's shop and student
planted and asserted absent.

**A decorative test of my own.** I wrote the classic *page-first-then-sort* test — and its fixture
arrived in name order, so both the correct code and the deliberate fault produced an identical
first page. The bite-check is the only reason I know that. The fixture now arrives in the
server's own order (`-total`, then name), which is the only thing that distinguishes the two.

**And two more faults, both caught first time:** the Unsorted tab dropping its filter, and a
headline figure that followed the tab.

## 3 — Two bugs in my own comparator, caught by tests written from the harm

`sortRows` takes an `isUnknown` argument so a null date or a blank name stays at the *bottom* when
a column is flipped. I hand-rolled `[...rows].sort()` with `dir === 'asc' ? c : -c` instead, which
negates that answer along with everything else — so a shop never seen and a student with no name
recorded jumped to the top of the reversed column. Both tests failed on the first run, because
both were written from what the reader would wrongly conclude (*"this shop was seen most
recently"*) rather than from the code.

The fix was to stop reimplementing and use the shared helper. **When a shared helper takes an
argument you do not think you need, that argument is usually the bug somebody already had.**

## 4 — Extractions, done fully

`SortHeader` had been copied byte-for-byte into Reviewers and Sponsors. Rather than add a third
and fourth copy, it became `components/admin/SortHeader` and **both originals were moved onto it
in the same change** — the People-actions lesson says a partial extraction is more dangerous than
none, because it looks finished. 93 tests on those two pages still pass untouched.

`SpendingShops` exists for the same reason in advance: the shop row is drawn in two tabs, so every
rule about it (the pill, the held-back note, the correction control) lives in one file before the
second drawing was written.

## 5 — Judgement calls worth recording

- **The four figures sit above the tabs.** They describe the whole page. A headline that moved as
  you switched tab would be a headline nobody could quote — and *Not yet sorted* is precisely what
  the Unsorted tab explains, so it must still be on screen when you get there. Pinned by a test.
- **The Unsorted tab is about money, not confidence.** It pairs with *Not yet sorted*, so the list
  adds up to a number the reader can see. Shops the ceiling held back are IN, even though their
  category reads `food` — six real payments worth RM424 on production would otherwise be hidden by
  a filter written on the category alone.
- **"How we decided" sorts by how settled the answer is, not alphabetically.** The labels are
  translated; an A–Z sort would order the column differently in three languages and mean nothing
  in any of them. Descending brings the guesses to the top, which is the queue.
- **The students table gained phone cards.** Four short numeric columns would have justified an
  exemption, but it is a list of people, and the guard's own rule says those get cards.

## What is still open

- The organisation crumb still cannot drive a page's scope the way the programme crumb can
  (`programmeScope`). It did not need to here — a super sees everything — but it will the day a
  second organisation imports spending. Recorded in the decision's *Revisit if*.
- Everything from S5 stands: **TD-242** (a transient Drive read dropped a whole file silently —
  after any import, check `files read` equals the number of exports), TD-241, TD-240, TD-239,
  TD-238.

## Gates

**6419 pytest** (+7) · **2084 jest** (+29) · lint clean · production build succeeds.
