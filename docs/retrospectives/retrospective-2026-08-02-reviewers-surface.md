# Retrospective — Request #10, the reviewers surface (2026-08-02)

Two sprints and a live-review round, in one day. Commits `04489c4e`..`1f4f8d6a`; two deploys.

## What was built

BrightPath runs on thirteen unpaid volunteer reviewers who had, between them, decided 66
applications — and the console had no page about any of them. Staff invited and revoked; nothing
showed who they were, what they carried, how long a case sat with them, or what became of it.

- **Organisation → Reviewers** — a table and a detail page. Credentials, caseload, turnaround, and
  every decision of theirs that was reopened, each carrying the reason recorded at the time.
- **Pause** — a reviewer steps back from new cases on their own profile; an org_admin can do it for
  someone who has gone quiet; the same control brings them back.
- **Five reviewer emails** — assigned, QC returned, QC rejected, verdict due soon, verdict overdue —
  moved out of hard-coded prose into editable templates with real switches.

Deferred by owner ruling: the programme column and per-programme assignment. With one programme the
column could only ever say one thing.

## What went well

- **The artifact gate did its job twice.** Both the original surface and the compact redesign were
  approved as rendered pages, populated with real production figures, before any page code existed.
  The second one took one round trip and changed the layout materially.
- **Bite-checking caught nothing, which is the point.** Five new guards were each broken
  deliberately and the named test failed every time. That is cheap and it is the only evidence a
  guard is load-bearing rather than decorative.
- **Querying production before writing the display was decisive, repeatedly.** Every significant
  design decision here — the median, the null turnaround, the four outcome bands, the phone prefix —
  came from reading real rows, not from reasoning about the schema.

## What went wrong

### 1. I excluded cases a reviewer had genuinely reviewed

**What happened.** The outcome bar dropped any case whose verdict somebody else recorded, and
printed a footnote saying so. The owner asked why Balan's record said 7 when he could count 8.

**Why.** I reasoned from the field (`verdict_decided_by`) to the meaning ("whose work is this?")
without checking whether the two agreed. They did not: on application #13 Balan was assigned,
**interviewed the student and submitted his findings**, and only the final click was the owner's.
I had encoded "who pressed the button" as "who did the work" — and worse, I had written a confident
docstring defending it, which made the mistake look considered.

**Fix.** The record now covers every decided case assigned to them, with `rejected_after_review` as
its own band so an overturned recommendation is never shown as a decline. The general rule, added to
`lessons.md`: **when a column stands in for a human activity, find the row where the two come apart
before building a rule on it** — here, one join to `interview_sessions` would have shown it.

### 2. The bar did not add up, and nothing said so

**What happened.** Two decided cases sat at *awaiting QC* and appeared in neither band, so
Yuvarajan's page read Completed 6 above a bar totalling 5.

**Why.** I wrote the bands as two interesting cases (progressed, declined) rather than as a
partition of a set. Nothing in the code or the tests asserted the parts summed to the whole.

**Fix.** Four bands that partition the decided cases, plus
`test_the_bands_account_for_every_decided_case` — a new status that escapes all four now fails a
test instead of silently shrinking the bar.

### 3. A structural token would have reached a volunteer's inbox

**What happened.** `qc_comments` is rendered as a block, and a caller that omitted it left the
literal string `{qc_comments}` in the body.

**Why.** Blocks were filled only when the caller supplied data, which was fine while every block was
a table the caller obviously had. A prose block that is legitimately empty broke that assumption.

**Fix.** `render()` now fills every structural token the kind declares, supplied or not. Found by
the pre-existing "no placeholder survives" test — which only caught it because that test walks
**every** kind with a deliberately thin context rather than testing the happy path of each.

### 4. I put a pre-push step in the handoff that cannot run before the push

**What happened.** The brief listed `seed_partner_email_templates` as a step before deploying. It
runs on the deployed service and seeds what the *running* code knows about, so seeding first would
have silently skipped all five new kinds and reported success.

**Why.** I wrote the order from the shape of the work (data before code, as with migrations) instead
of from where each step executes. Migrations run against the database and so must precede the
deploy; a management command runs inside the image and so must follow it.

**Fix.** Corrected in the brief, and the warning now sits at the cron registry line somebody reads
before firing it — not only in a document. **Lesson:** *migrate-first* is about the database; a
seed command is code, and code ships with the deploy.

### 5. A raw i18n key was live for a day

**What happened.** `admin.sources.emails.note.student_assigned` rendered as that literal dotted
string, in all three languages, from 1 August.

**Why.** `t()` returns the key on a miss, and the template editor rendered it unconditionally. The
fifth member of the "the UI asserts what nothing checks" cluster.

**Fix.** The copy is written, and the editor now renders nothing rather than a key — so the next
missing note is invisible rather than embarrassing.

## Design decisions

Recorded in `docs/decisions.md`: pause as `paused_at` rather than `is_active`; the fallback keyed on
a missing template row rather than the platform flag; the outcome bands as a partition; the partial
PII widening; and the deferral of the programme column.

## Numbers

- `pytest` **5427+** · `jest` **1367** · `tsc` clean · `next lint` **0 errors** · i18n **4462 × 3**
- Two migrations, both applied migrate-first with their ledger rows. Production reconciled:
  `courses` 1–68, `scholarship` 1–143, contiguous, no gaps.
- Two deploys. Five guards bite-checked.
- Quoted 15h including 2h for programme assignment; deferred by the owner, so **~13h**.
