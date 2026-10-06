# Retrospective — the Layer 0 catalogue (config roadmap, Sprint 2)

**Date:** 2026-07-28
**Deliverable:** a catalogue of what an application can ask for, a per-programme selection table,
and one read seam — with **zero behaviour change**.
**Verification:** 5018 pytest passing · the existing suite **unmodified** · `makemigrations --check`
clean · migration 0135 applied to production migrate-first, RLS on, one `service_role` policy each.

---

## What the sprint claims, and what proves it

The claim is "nothing changed". A new test cannot prove that — it proves the new thing works. The
evidence is the **rest of the suite passing without a single test being edited**, which is why the
literals in `services.py` were deliberately left in place: both descriptions of BrightPath's
configuration exist at once, and `test_requirements.py` asserts they agree.

Sprint 3 deletes one side. Until then this is the only moment where the comparison is possible, and
it is worth more than any amount of new coverage.

## The bug the sprint's own test caught, in the sprint's own code

`PLATFORM_REQUIRED_QUESTIONS` — the fallback for an application with no programme — omitted
`consent`, while the seeded catalogue had it as core.

The consequence, had it shipped: an application **with** a programme would be gated on consent, and
a legacy application **without** one would not. Consent is a legal requirement, not a programme
preference. It would have failed quietly, on exactly the rows nobody looks at.

I fixed it and then did the thing that actually matters — the first fix was a comment saying *"the
two describe the same thing and must not be written independently"*, while leaving them written
independently. That comment is a request; the replacement is a test asserting the fallback tuples
equal what the seeded catalogue resolves to. **A rule that depends on someone reading a comment is
not a rule.**

## A schema error caught before any row existed

`default_state` started as `default_on: bool`. Four documents today are *offered but never
blocking* — water bill, electricity bill, statement of intent, photo — and a boolean cannot say
that. A flag that cannot represent a state the system already has is a schema asserting something
false.

Caught while writing the seed, which is the first moment the model met real data. Both tables were
empty, so the correction was a drop-and-add rather than a data migration. Same family as the
`PlatformCost.amount_myr` lesson from the billing ledger — **check the values before fixing the
column's shape**.

## The rules that make "catalogue, not form builder" real

Three, each with a test rather than a docstring:

1. **A document code must name an existing `ApplicantDocument.DOC_TYPES` value.** The engine reads
   documents; it cannot comprehend one an organisation invented. One declared exception,
   `income_proof`, which is a switch over the income *route engine* rather than a document — and a
   test pins the exception list at exactly that one, so it cannot grow silently.
2. **Every label is an i18n key, never a stored string.** A label in the database is a fourth place
   translations live, invisible to `check-i18n.js`, and the way an organisation ships English to a
   Tamil-speaking student.
3. **The core floor is exactly what the owner named** — identity card, results slip, offer letter,
   income, family roster, consent. Asserted as a set, because it is a *policy* decision and a later
   sprint must not quietly widen or narrow it.

## Two judgement calls worth recording

**`Programme`, not `ScholarshipCohort`** — a deliberate departure from the "new tunables go on the
cohort" convention, owner-approved. That convention exists to stop tunables becoming module
constants; both are data, so it is not violated in spirit. What a programme asks for is the gift's
identity, not the year's, and a cohort-level home would make every intake re-tick the same list —
precisely the rot this work exists to prevent.

**The seed writes no per-programme rows.** With no explicit row, the seam falls through to the
item's default, which reproduces today's behaviour by construction. Seeding a row per programme
would say the same thing twice, and the copy could then drift — correcting a catalogue default
would silently fail to reach a programme whose seeded row still held the old value. **An
organisation's row should mean "we chose this", never "somebody ran a seed once".**

## Deliberately not done

Nothing calls the seam to make a decision. No admin screen. The income route engine is one switch
and stays one switch — decomposing it would let an organisation take the STR/salary logic apart a
document at a time, which breaks "engine logic stays programme-agnostic" and is where BrightPath
would get broken.

## Owner / deploy step for Sprint 3

Production has the two tables but **no catalogue rows**. That is harmless today — nothing reads
them, so empty is exactly as inert as seeded. **Sprint 3 must run
`python manage.py seed_application_catalogue` against production before its gates go live.** It is
idempotent and prints what it would change with `--dry-run`.
