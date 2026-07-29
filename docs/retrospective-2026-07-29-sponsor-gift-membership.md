# Retrospective — a sponsor who registers today belongs to a gift

**Date:** 2026-07-29
**Deliverable:** the write path that migration 0123 never had — a sponsor's membership of the
default gift is opened at registration and settled at vetting — plus a migration healing whoever
fell in the window.
**Verification:** 3823 scholarship + 1260 courses/reports pytest · six new regression tests, each
run against a deliberately disabled fix and confirmed to fail · `makemigrations --check` clean ·
migration `0136` applied to production migrate-first, ledger row recorded.

---

## The shape of the bug: a backfill with no successor

On 2026-07-25, migration `0123` gave every sponsor then alive a flagship membership copied from
their account status. It was careful work — its own docstring states the invariant it protects, and
its numbers were verified at the time.

Nothing was ever written to keep doing it.

From that moment the system had a rule ("acceptance is per gift") enforced by a one-off act. The
next person to register — 28 July, three days later — arrived belonging to no gift at all. So did
everyone who would have followed.

**This is the lesson worth keeping.** A backfill answers "what about the rows that already exist?"
It does not answer "what about the rows that arrive next", and the two questions are so adjacent
that finishing the first feels like finishing both. The failure has a delay built into it: the
sprint ships, the counts reconcile, the tests pass, and the defect begins on the next
registration — after everybody has moved on. A data migration without a matching write path is not
a completed change; it is a change with a timer on it.

The general form: **whenever a migration populates a column or a table for existing rows, name the
code path that populates it for the next one.** If you cannot, the migration is half the work. That
question takes ten seconds to ask and nothing in our process asked it.

## It was found by a missing button, which was the least of it

The owner opened two sponsors side by side and noticed one had a **+ Record a credit** button and
the other did not.

That was the smallest of the three consequences and the only one with a surface:

- **The student pool read empty.** `pool.for_sponsor` narrows to approved memberships, so a sponsor
  with none sees no students. Their last-seen said "Today" — they had almost certainly already
  logged in and found nothing.
- **The weekly digest would have been silent**, despite being switched on, because
  `sponsor_notifications` filters on the same list.
- **No credit could be recorded**, because `record_admin_credit` refuses `sponsor_not_in_programme`.

Only the third had a visible trace, and only because a control disappeared. The first two are
absences: an empty list looks exactly like an empty list, and an email that does not arrive looks
like nothing at all.

**A fence that hides things cannot report that it hid too much.** Every membership-fenced read in
this codebase is correct and every one of them fails silently in the same direction. That is the
right direction for a privacy fence — the alternative leaks — but it means the fence can never be
the thing that tells you it is misconfigured. Something outside it has to. We have nothing that
asks "is there an approved sponsor who can see zero students?", and that single query would have
caught this on the 28th.

## The status said "approved", and it was true

The account page read approved, vetted by a named person, PDPA consent recorded. All of it correct.

There are two gates — the account, and acceptance into the gift — and the screen showed one of
them. The sponsor detail page could have rendered the membership all along; the data was already on
the payload (`memberships` has carried `programme_id` since S2). Nobody drew it, because with a
single gift the two gates agree in every case anyone had seen.

**A screen that shows one of two gates is telling the truth and giving the wrong impression.** When
a second gate is introduced, the surfaces that describe the first are part of the change — not
because they are wrong, but because they have quietly stopped being complete.

## What was NOT wrong, and was nearly "fixed"

Both sponsors in the screenshots held no wallet, and that is correct. A wallet exists once money is
recorded against a sponsor; most sponsors have given nothing. Six of the ten have any credit at all.

It would have been easy — and wrong — to read "no wallet" as the fault and go looking for why the
wallet was missing. The owner's own framing settled it and is worth preserving as the rule:
**seeing students has never depended on holding credit, and must not.** The balance is consulted at
exactly one point, [sponsorship.py:446](../halatuju_api/apps/scholarship/sponsorship.py#L446), the
moment a sponsor funds someone. A sponsor with an empty wallet browses the full pool and meets a
wall only when they click to give.

Two facts that look alike — "no wallet" and "no membership" — one benign and one severe. The
diagnostic move that separated them was querying production rather than reasoning from the
screenshots: the membership counts (nine sponsors with one, one with zero) named the culprit in a
single row.

## The classification call, which I got wrong

I ran this through the small-change lane. `wat_lint` warned that a change carrying a migration and
touching money and visibility gating should be a sprint, and I proceeded anyway, arguing that a bug
fix restoring intended behaviour adds no surface and that ceremony would add paperwork rather than
safety.

A concurrent agent reviewing the commits made the better argument: the rule says money or visibility
is a sprint and "when unsure, it's a sprint", so the lint was right by the letter — and more
usefully, there was a lesson in this one that the small lane has nowhere to put. That is this
document. The pattern above will recur, and a one-line entry in a consolidation queue would not have
carried it.

**The rails I kept were the right ones and were not the point.** Full suite, bite-tested guards,
CHANGELOG, owner-gated deploy — all present, and none of them would have written down why this
happened. I was measuring the lane by its safety checks and the lane's other job is to decide what
gets remembered.

## The ledger gap found on the way

Migration `0136` depends on `0135`, so applying it meant reading the production ledger in order —
which showed `0134`, then nothing, then `0136`.

`0135_application_catalogue` had its tables created on production, RLS enabled, one `service_role`
policy each, 19 catalogue rows seeded. Its own retrospective states all of that and it is all true.
The single missing step was the `django_migrations` row. Recorded now, back-stamped to the commit
time (2026-07-28 15:50), which the concurrent agent independently confirmed matches that sprint's
build to the minute.

Harmless in effect — Django keys on `(app, name)` and the schema was correct throughout — but it
would have surfaced as a `CREATE TABLE` against existing tables the next time anyone ran `migrate`.

**`makemigrations --check` cannot see this.** It confirms the migration files match the models; it
knows nothing about what production has recorded. Every sprint here closes on that check, and it is
structurally blind to the one thing migrate-first can get wrong: doing the DDL and forgetting the
bookkeeping. A `showmigrations`-versus-production comparison at close would catch it. Proposed, not
built — it belongs in the sprint-close workflow rather than in this sprint.

## What proves the fix

Six regression tests, and the number that matters is not six.

Each was run against `sync_account_membership` disabled and confirmed to fail; all six did, and the
twelve pre-existing membership tests stayed green throughout — which is what shows the new tests
exercise the new path rather than the fence that was already working. The rule from Layer 0 sprint
3a applies here directly: a green suite proves nothing about a branch no test takes.

The one that carries the deliverable is
`test_approval_settles_the_membership_and_opens_the_pool`. It registers a sponsor through the real
endpoint, asserts the pool is empty before vetting (the account gate doing its job), approves them
through the real admin endpoint, and asserts they see the student. It never touches
`SponsorProgrammeMembership` directly, so it would still fail if the mechanism were replaced and the
outcome broken.

One test exists only to pin what must NOT happen: suspending an account does not revoke a second
gift's membership. Acceptance into another organisation's gift is that organisation's decision, and
a platform-level account action must never quietly undo it. Nothing today can reach that state —
there is one gift — which is exactly why it is written down now, while the reason is legible.

## Production, after

All ten sponsors hold a membership mirroring their account status: eight approved, one rejected, one
suspended-free. Gan Tee Jin (id 10) went from no row to `approved` — which his account already
entitled him to — so the `0123` invariant holds through this change too: **nobody gained sight of
anyone their account did not already permit.**

---

## Lessons

Recorded in `docs/lessons.md`:

1. A backfill migration without the matching write path is a bug with a delay on it.
2. A silent fence cannot report that it over-fenced — something outside it has to ask.
3. `makemigrations --check` is blind to the production ledger.
4. Two adjacent facts, one benign and one severe, are separated by querying production, not by
   reasoning from the screen.
