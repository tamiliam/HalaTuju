# Retrospective — the IC lock becomes a real rule, and correctable until it is

**Date:** 2026-07-29 → 30
**Deliverable:** a student may correct their own IC number until the uploaded MyKad confirms it;
after that it locks, one-way, with a super-only release for orphaned claims. Whenever the card
disagrees with what was typed, the profile now says so.
**Verification:** 5071 backend pytest · 1176 jest · i18n parity 4321 ×3 · every guard bite-checked
· **no migration.** Backend deployed (`halatuju-api-00905-hxf`); web **not deployed** — awaiting
the owner's review of the copy.

---

## The bug, which was not the one anyone was looking for

It started as "student #106 has her IC wrong". One digit: she typed birthplace code `11` where her
card reads `14`. Her card was genuine, read perfectly, and her name matched exactly.

She could not fix it. Neither could anyone else. Tracing every write path found exactly one
function in the codebase that changes an IC number — the claim endpoint — reachable from two
screens, both closed to her: the apply form redirects a returning applicant away, and the sign-in
prompt fires only for someone with no IC at all. Her profile page showed the number masked and
disabled.

Then the owner asked the question that turned the sprint around: *why is it locked at all?* She was
`shortlisted`, unassigned, unverified.

**It wasn't locked.** The padlock was hard-coded:

```jsx
<input value={nric ? maskIc(nric) : '—'} disabled … />
<svg …padlock… />
```

`disabled` was a bare attribute. The icon had no condition. Neither consulted `nric_verified` —
the word does not appear in that block. **Every student saw a padlock, always.** On production
that was 85 of 143 applicants, and an account with no application at all.

So the thing to fix was not "let her edit it". It was that the screen had been asserting a state
it never checked, for as long as the field had existed.

## Which is also why the coach read as nonsense

Cikgu Gopal tells a student with a mismatched IC to re-upload a cleaner photo and, if that fails,
that *"the IC number they typed when registering may have a small typo they can correct on their
Profile page."*

For #106 both halves were wrong. Her photo was fine, so re-uploading would have achieved nothing
however many times she tried. And the Profile page showed her a padlock and a greyed-out box.
**We were telling her to do two things, one useless and one impossible** — and the copy was
well-intentioned and specific, which is what made it convincing.

A dead end written in encouraging prose is worse than no advice, because the student assumes the
fault is theirs.

## Three errors I made, and what each one teaches

### "35 students will lock on deploy" — the real answer was zero

The lock is taken at the end of an IC *read*. Deploying doesn't read anything, so it locks nobody,
and most of those 35 would never touch their IC again.

Worse than the wrong number: without a sweep, *who is locked* would have depended on who happened
to upload something recently. Same evidence, different answer, unexplainable to a student. Fixed
with `backfill_nric_locks` before the push — no API calls, no re-extraction, re-applying
`identity.locks_now` to the reads already stored.

**When a rule fires on an EVENT, shipping it changes nothing about the rows that already exist.**
Ask what happens to them before quoting a number.

### "She's blocked from submitting" — she wasn't

I read her income route (STR) and her documents (no STR proof) and concluded `str_missing` would
gate her. The owner corrected me from the screen: *"STR fell through but her income held."*

`income_established` treats a complete salary cluster as settling income regardless of route, so
her father's IC and payslip carried it. I had reconstructed the gate from CLAUDE.md rather than
reading it, on a codebase whose whole design is that gates live in one named predicate.

**Querying the database then applying a remembered rule is not verification.** It has the texture
of rigour and none of the substance.

### "The flag is a recipe for freezing someone's identity" — it isn't

Asked to walk the brother-uploads-his-sibling's-card case, the honest trace came out differently.
The fraud is self-defeating: the student's own results slip then fails the academic gate, so they
cannot submit at all. And the path already exists today — this design doesn't open it, it only
moves *when* the lock shuts and removes a human who was, in practice, reading the machine's own
comparison back to itself.

The real harm was one I had missed entirely: **the abandoned account keeps a live claim on a real
person's IC number**, and the true owner can never register. That is what the break-glass is for,
and the endpoint is documented around that case rather than the one I first described.

**A vivid risk crowds out the real one.** Walking the scenario concretely, when asked, produced a
better answer than my confident summary of it.

### A fourth: "#27 and #118 show our OCR blaming students" — it doesn't

I cited those two applications repeatedly — here, in the CHANGELOG, and as the justification for
the flag copy hedging on which side is wrong — as cases where our reader mangled a name and would
have accused the student. Asked to look at them, the cockpit showed both as **Verified · Exact**
with Name and IC No green, and running the real matcher confirms it:

    #27  card 'KALIANA KUMAR SANJANA'    typed 'KALIANAKUMAR SANJANA'   -> match
    #118 card 'KRISHNAN THACHAYAHNIA/P'  typed 'KRISHNAN THACHAYAHNI'   -> match

`name_match` has a glued-token path for exactly the OCR space-split in #27, and strips a trailing
`A/P` for #118. **Both were artefacts of my own SQL approximation** — I stripped parentage markers
only between spaces and had no glued comparison at all — and I then repeated the two app numbers
as though they were findings.

What survives: the *principle* that a reader which mangles names should not accuse the student.
What does not: any evidence that ours does. Production's flagged bucket is one test account. The
copy hedge is therefore an a-priori choice, and it should be recorded as one rather than dressed
in two cases that dissolve on inspection.

**An approximation used to FIND something must not become the evidence FOR it.** The SQL was the
right tool for locating candidates and the wrong tool for characterising them; the real predicate
was one call away the whole time, in a codebase whose entire design is that the rule has one home.

## The design, and the three places it is easy to get wrong

`apps/scholarship/identity.py` is the one home, because "is this settled?" has to be answered by
the padlock, the write path and the lock-taking at once — and the standing lesson from the income
gate is that three copies drift.

1. **An unscored card is NOT genuine.** Every other consumer fails open on an absent verdict
   (`income_engine` treats `''` as passing), which is right for a soft signal an officer can
   overrule. A one-way lock earns the opposite default. Same shape as Layer 0's "an empty
   catalogue means NOT CONFIGURED".
2. **The name may differ by whole parts, never by spelling.** There is a tolerant matcher next
   door, built for income documents, that folds w↔v and doubled letters. Reaching for it is the
   natural reading of "minor differences are not a blocker" and is exactly what must not happen.
3. **The number is exact.** `nric_close` exists only to word the nudge as "differs by one digit".

**The lock is stored, never re-derived** — a lock recomputed each read would vanish the moment the
student deleted the card that earned it.

### The flag that nearly went in wrong

The profile page had only `identity_verified` in scope — which is `nric_verified` **OR** the card
matches. So `disabled={identityVerified}`, the obvious one-liner, would have locked students with
no genuineness check and unlocked them again on deleting the document.

What makes it nasty: **for #106 the wrong flag gives the right answer.** Her card disagrees, so
`identity_verified` is false either way. Testing the motivating case would have passed. It would
only have bitten students who typed correctly — the ones nobody looks at.

## What the guards had to prove

Every guard was bite-checked — disabled, watched to fail, restored:

| Guard broken | Caught by |
|---|---|
| Unscored card counts as genuine | the rule test **and** the stored-lock test |
| A one-digit slip widens the lock | both |
| A different name counts as the same person | misspelling + different-person |
| `disabled` back to a bare attribute | the padlock static guard |

The last one is a source guard rather than a render test on purpose. The defect was never a wrong
value flowing through a component; it was a constant where a condition belonged, and it survived
every review for months. A render test proves today's wiring; the guard proves nobody goes back.

## Numbers

Of 143 students: **58 locked, 85 open** at close — unchanged, because the sweep has not run. After
it does: 93 locked, 50 open (39 have no IC on file, 10 need a Re-run first, 1 is a test account).

I quoted "36 to backfill" and then "95 to lock" along the way. Both were per-application counts;
per *student* the answers are 10 and 35. Two of my three numeric claims this sprint needed
correcting, which is the sprint's real signature.

## Process: the concurrency hazard actually fired

A concurrent agent working on themes ran `git add -A` and swept my entire unfinished frontend into
its own docs commit — then pushed it. Nothing was lost, and the web build was cancelled before it
deployed, but main briefly held untested UI that the next web build would have shipped.

I staged explicit paths all session, per the standing rule. **That protected their work from me
and did nothing to protect mine from them.** The defence against being swept up is not careful
staging; it is committing frequently, so the uncommitted window stays small.

---

## Lessons

Recorded in `docs/lessons.md`:

1. A control disabled by a constant rather than a condition is a lie the UI tells, and review
   does not catch it.
2. Two flags that nearly mean the same thing will be confused — and the broader one is the one in
   scope.
3. A lock derived from evidence can be undone by deleting the evidence.
4. Shipping an event-triggered rule changes nothing for existing rows.
5. Explicit staging protects others from you, not you from them.
