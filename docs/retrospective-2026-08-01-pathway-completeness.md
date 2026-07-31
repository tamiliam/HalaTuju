# Retrospective — the confirmed pathway is complete (requests #7 + #8), 2026-08-01

**Deliverable:** two BrightPath reports about the same two student records — a chosen programme
that disagreed with the fields around it, and a chosen programme with pieces missing — closed by
two backend fixes, a scoped repair command and a production repair of exactly two rows.

**Shipped:** `fa3465c0` (the two fixes + 7 tests), `4be60e09` (the repair command + 8 tests).
No migration. One deploy. Backend only.

---

## What actually happened

### The brief was half wrong, and the database said so first

The sprint brief — written by me the previous session, carefully, with evidence — pinned #119 to a
guard in `confirm_pathway` that skips the pre-U normalisation. Before touching a line I read her
row. Her programme is stored as the canonical **"Tingkatan Enam"** at **"Kolej Tingkatan Enam Sri
Istana"**, while her offer letter reads **"KOLEJ TINGKATAN ENAM SRI ISTANA"**. Nothing but that
block produces the canonical name and the re-cased school. **The block ran.** Her stream and
college were filled correctly on 17 July and were blank again by the end of the month.

So #119 was a *wipe*, not a *skip* — a different defect, in a different file, that the planned fix
would not have touched. #32 genuinely was a skip, which is what made the wrong half credible.

The general form is worth keeping: **a stored value is a fingerprint of the branch that wrote it.**
Normalised text, a cleaned name, a canonical spelling — each proves a specific code path already
ran, and that evidence outranks any recollection, including a careful one written down yesterday.

### Two defects, one request

**A. The gate read a field the same function was about to correct.** `confirm_pathway` decided "is
this pre-university?" from `application.chosen_pathway`, skipped the whole normalisation when that
was empty, and then adopted the offer's own type forty lines later. Both girls applied
`pathway_certainty='uncertain'` and declared nothing — **the normal state of an uncertain
applicant**, not an edge case. Moving the reconciliation above the block is the entire fix.

**B. A blank profile erased what the letter established.** The two-way sync copies eight pathway
fields between profile and application. July's #117 fix diagnosed this exact clobber and guarded
**one** of them (`chosen_programme`); the offer pipeline writes three more, and the profile is
never refreshed when it does. So any /profile edit copied its blanks over the offer's reading.
#119 was wiped ten days after her confirm; #32 four minutes *before* hers, which is why her confirm
then read an empty declaration — **one root cause producing both reported symptoms.**

### The guard is emptiness, not provenance

The tidier-looking fix is to freeze the pathway fields once the programme is offer-confirmed. It is
one line and it silently drops a student correcting her own stream or school. Refusing only the
**blank** is strictly narrower: a blank carries no information, so declining to copy one cannot
lose an intention, while every real edit still lands. Every test asserts the permissive case.

Left open deliberately: a *populated but stale* profile value can still overwrite an offer-confirmed
pathway (the #43 shape). No production row is wrong from it today — **TD-210**.

### Found in passing and NOT fixed

Seven billing/usage tests were red before this sprint's first line. Reproduced on a clean tree, then
characterised rather than dismissed: `available_months()` groups usage in Malaysian time while the
endpoint defaults "this month" from `timezone.now()` — a UTC instant formatted without conversion.
For eight hours after midnight MYT on the 1st the two disagree. That is today. **TD-209**: one line,
on a money surface switched on yesterday, so it is the owner's call rather than a quiet fix.

---

## What went well

- **Reading production before coding** overturned a wrong diagnosis for the cost of four queries,
  and turned two reports into one root cause instead of two half-fixes.
- **All three guards were bite-checked** — the sync guard, the ordering, and the repair's
  "leave tertiary alone" selector — each failing exactly the test that names it, and no others.
- **The repair re-runs the real code path** rather than hand-writing the values a human thinks it
  would produce. It reads the offer already on file: no re-extraction, no Vision call.
- **The confirmation date is preserved.** She confirmed on the day she confirmed.

## What to carry forward

1. Before changing a line, ask what the CURRENT stored value proves about which branches have run.
2. When a fix is scoped to one field/caller/branch, write down the other members of that set and
   why each is safe. If you cannot, the fix is incomplete rather than minimal.
3. A guard should refuse the destructive INPUT, not freeze the destination.
4. A test failure that correlates with the calendar is usually a behaviour that does too.

## Hours

Planned **3.5h** across both requests (#7 at 3.0h — the corrected analysis; #8 at 0.5h).
Spent **2.6h**. The published 5.0h analysis on #7 was superseded by the 3.0h reading after the
blast radius was measured at two records rather than a cohort.
