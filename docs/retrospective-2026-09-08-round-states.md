# Retrospective — an intake round has four states, and one of them is final

**Date:** 2026-09-08
**Branch:** `feat/round-states` (worktree `.worktrees/round-states`, off `origin/main` at `2af14eda`)
**Migration:** `scholarship/0151` — additive, two nullable columns. **MIGRATE-FIRST.**
**Scope:** api + web.

---

## It began with a question I had answered wrongly

The owner asked when the 2026 intake closed: *"I think it was 7/7/2026 midnight, and it was auto
closed."*

I said nothing auto-closes, from a grep of one field's writers. They pushed back — they remembered a
cron job. So I checked properly:

| Checked | Found |
|---|---|
| Every Python writer of `is_open` | **2** — the admin screen, and a local seed command |
| All 26 Cloud Scheduler jobs | none close anything |
| Every Cloud Run job | 1, unrelated |
| All 47 registered cron tasks | none touch it |
| Commits 28 Jun – 10 Jul | nothing about closing |
| Cloud Logging | **past retention — answers nothing either way** |

The conclusion survived, but it now rests on evidence rather than a reflex. And the second half
matters as much: a log that is past retention is **silence**, not absence. Those are different claims
and I said which one I had.

## The reconciliation was a behaviour nobody had written down

The owner's chronology: emails went out with the landing-page link; that link went dead on 1 July;
students already part-way through were given until the 7th.

On the code that looked impossible — the landing page and `/apply` read the **same single switch**,
so they cannot close on different days. But they were both right, because of a comment on the apply
endpoint:

> *"a closed cohort accepts no **NEW** applications … **Existing applicants never reach this endpoint
> again** (they continue via their own application)."*

One flip of `is_open` on 1 July. Thirty students who had already started submitted between then and
the 7th. The last landed at **21:12 MYT on 7 July**. One switch, pressed once — and a grace period
that was real, load-bearing, correct, and stated in exactly one comment.

**The lesson is the ordering.** I nearly argued the owner's memory against the code. The right move
was to ask which undocumented behaviour would make both accounts true.

---

## What shipped

### Four states, three behaviours

`views_admin.round_state` serves `draft` · `open` · `closed` · `finished`.

| State | What it does |
|---|---|
| `draft` | Never opened, nobody has applied |
| `open` | Anyone may start and submit |
| **`closed`** | **No new applications; anyone already started may still submit** ← the July grace period, now said on screen |
| `finished` | Nobody may submit. **Terminal.** |

**⚠ Do not collapse `closed` into `finished`.** A bite-check that made closing refuse a submission
failed exactly the test named for those thirty students.

The refusals sit where the behaviour does: **reopening** is refused at the endpoint (not merely
hidden in the browser — a screen that omits a control is a suggestion); a **late submission** is
refused in `services.confirm_profile`, because that is where the grace period ends, not beside the
create gate.

### The badge is the control

The loose Open/Close link is gone (owner: *"the button seems odd sitting there, and at present it
would sit there in perpetuity"*). Four tones, **none red** — every state is a normal point in a
round's life, the gift card's own ruling. A finished round offers **no move at all** and says why.

### Finishing is terminal, so it asks

The owner's ruling. Nothing in the product clears `finished_at`. Because it cannot be undone it
takes a typed confirmation — the round's own code, the shape used for deleting a gift — and the
dialog **names how many applicants it would shut out**. On the live 2026 round that is **one**: a
student who started and never submitted. Silence there would mean pressing a button and quietly
locking a real person out.

### The record that did not exist

`finished_at` / `finished_by`, plus `AUDIT intake_year_finished` carrying the shut-out count. The
gap that started the whole conversation: the biggest switch on the screen kept no record of who
pressed it or when, so two months later the answer was the owner's memory. Same shape as TD-203.

**⚠ `updated_at` is not evidence here** — the endpoint saves with `update_fields`, which does not
touch an `auto_now` column. I tested that rather than assuming it, and it stopped me reporting that
the July close had "bypassed Django".

### Three smaller fixes from the same review

- **`color-scheme`** in both theme blocks. The stylesheet had two token ramps, a theme switch and a
  contrast sweep — and never told the browser which mode it was in, so every native control was
  drawn for a light page. The owner reported the date picker's calendar icon as almost invisible;
  one declaration per mode fixes every native control at once.
- **The date boxes cap the year** (2000–2099). Chrome's year slot takes six digits, so typing over
  an existing value produced `07/07/202026`. The server already refused it; the browser refuses it
  now, at the keystroke.
- **The out-of-window confirmation reworded** — past tense for a past date, two short lines.

---

## The trap in the middle

`ScholarshipApplication.submitted_at` is **`auto_now_add`**. It is stamped when the row is created
and is never null. The first cut of the shut-out count used `submitted_at__isnull=True` and read
zero for everybody; a test asserting 1 caught it. `shortlisted` is the not-yet-submitted status.

**A field's name is a hypothesis. `auto_now_add` is the answer.**

---

## Bite-checks

Three, each injection verified as landed first, each restored by writing the original bytes back.

| Injection | Expected | Got |
|---|---|---|
| Delete the server-side reopen refusal | the terminal test fails | **1 failed** |
| Make a merely-CLOSED round refuse a submission | the grace-period test fails | **1 failed** |
| Let a finished round's menu offer reopening | the "no move at all" test fails | **1 failed** |

The middle one is the one that matters: it is the change that would have cost thirty real students
their applications, and it now fails loudly.

## Gates

`pytest` **5984** (+14) · `jest` **1822** (+12) · `tsc` **24** (TD-221 baseline; two new errors
appeared in test fixtures missing the new served fields and were fixed, not waived) · `next lint`
**0 errors** · `check-i18n` **4884 × 3** · `next build` **exit 0** · `makemigrations --check` clean.

Every gate ran inside the worktree.

**The org-fence static guard bit once, correctly** — I put two lines of explanation between the
`# org-fence:` pragma and its query, past the guard's 200-character window. Second time; both times
a good comment in the wrong place. Explanation goes above the pragma; the pragma touches the query.

## i18n

Four keys retired (the old pill labels and the loose link), 21 added. Parity **4884 × 3**.
**ms and ta are my first drafts**, and the generator refuses rather than warns on a character outside
the Tamil block — the S-ASSIGN lesson, mechanised.

---

## At deploy, in order

1. **Apply `scholarship/0151` MIGRATE-FIRST** (two additive nullable columns) and record its
   `django_migrations` row **before** the push. Hand-write the Postgres DDL — `sqlmigrate` renders
   SQLite here.
2. Push. **api + web** (Python changed, so expect both builds).
3. No env vars, no data step, no backfill. **Nothing a student sees changes** unless a round is
   finished; the org_admin's Intake year tab does.

## Owner post-check

As the BrightPath `org_admin` (`elanjelian@me.com`):

1. **The status column is a badge you can press.** BrightPath 2026 reads **Closed** (amber), and its
   menu says: no new applications, anyone already started can still submit.
2. **"Close for good"** is offered there. Its dialog should say **one** applicant would be shut out,
   and the button stays asleep until `b40-2026` is typed. **Only press it if that is what you mean —
   there is no way back.**
3. **After finishing**, the badge reads Finished and its menu offers nothing.
4. **Dark mode** — open the Edit dialog. The calendar icon should be plainly visible now, and so
   should every dropdown arrow across the console.
5. **ms and ta are first drafts.**

**Not click-tested in a browser** — admin Google sign-in still fails on localhost (TD-182) and these
tabs have no sandbox surface.

---

## Still open

- **The gift switcher (item 3)** — next, on its own.
- **The apply link on the gift card, and an editable gift code with the old code kept as an alias**
  — the owner approved the approach; it is its own sprint, and the alias touches the live apply route.
- Archiving a gift blocks creating a payment run for it (named, not fixed).
- TD-229, TD-230, TD-231, TD-225, TD-221.
- **The Sabah owner gate stands.**
