# Retrospective — sponsor module: the three fixes + the credit interface (S1.1 + S2)

**Date:** 2026-07-28
**Commits:** `0561ac1c` (S1.1 — three fixes), `5c96b001` (S2 — the credit UI)
**Branch:** `feat/sponsor-detail` (worktree `.worktrees/sponsor-detail`)
**Migration:** none. **New route:** none.
**Plan / design of record:** `docs/plans/2026-07-27-sponsor-module-roadmap.md` ·
<https://claude.ai/code/artifact/9eec1f75-e38d-49d3-9df9-d4ad7a7b9fe3>

---

## What Was Built

### S1.1 — the three fixes off the owner's comparison

The owner opened the deployed screens next to the approved design and listed five differences.
Two dissolved on investigation (the Emails tab **is** S3; Record-a-credit **is** S2 — both
deliberately unbuilt, which the design's own sprint split had said). Three were real:

**1. Referral attribution by email.** `attribute_referral` only ever fired when someone
registered through a `/sponsor?ref=<code>` link. Most invitees don't: they read the invite and
then go to the site themselves. So on production **five of eight invitees had joined and all
eight rows read "Invited"** — a real 5/8 conversion reported as zero. New
`referrals.attribute_referral_by_email` closes the invitation on the invitee's own email at
registration; the code still wins when both signals are present, the oldest invitation wins on a
tie, and the whole thing is best-effort so bookkeeping can never cost someone their
registration. Pre-existing since Sprint 11 in June; S1's referral list is what made it visible.

New `backfill_referral_attribution` command repairs the history — report by default, `--apply`
to write, and it stamps `joined_at` with the sponsor's own registration date rather than today,
so the record stays honest about when it happened. It carries one guard the live path does not
need: the sponsor must have registered *after* the invitation, because someone who was already a
sponsor is not a conversion of that invite.

**2. Honest last-seen copy.** `last_seen_at` has only recorded since 27 July, so its null means
*no record* — but the copy read "Not since joining", which asserts that an approved sponsor has
never once come back. The mechanism was verified working first (a real visit stamped correctly at
13:39, a second was correctly throttled); only the sentence was false. Now "No sign-in recorded"
with a tooltip saying since when, in all three locales.

**3. The Students column** on `/admin/sponsors` — in the approved design, dropped from the build
without saying so. Money given says what a sponsor put in; students says what it is doing, and a
large balance with no students is the case an admin most needs to spot.

### S2 — the wallet-credit interface

The P4b endpoints had been live and org-fenced since 27 July with **nothing calling them**, which
made the sign-off chain a control on paper: the `admin` maker and `org_admin` approver it names
had no way to execute their own steps, so all RM172,000 of credits was keyed in by a developer.

- **Record** — a maker-only panel: gift, amount, bank reference (all mandatory).
- **Sign** — one button per row, labelled with the step the credit is actually waiting on, with
  the name **typed per row**. A click alone is not a signature.
- **Void** — maker or approver, unconfirmed only.
- **`creditActions`** mirrors `sponsorship.sign_admin_credit` step for step, test-pinned.

One backend change was required: `memberships` now carries `programme_id`, because the creditable
set is "gifts the sponsor was *accepted* into" and a sponsor accepted into a gift they have not
yet given to holds no wallet — which is the first-credit case exactly.

### Documentation (this close)

The role matrix and two manual chapters were wrong about role `admin` — see *What Went Wrong* #3.

---

## What Went Well

- **Verify-before-rebuild worked twice.** Two of the five reported findings were features not yet
  built, not defects. Checking the sprint split before writing code saved building S3 twice.
- **The mechanism was verified before the copy was blamed.** For last-seen I checked the actual
  stamps in production (one real visit, one correctly throttled) before concluding the code was
  right and the sentence was wrong. Reversing that order would have produced a "fix" to a working
  throttle.
- **The org-fence CI guard did its job unprompted.** My new raw `Sponsorship.objects` query
  failed the static guard until it carried an `# org-fence:` pragma. That is a guard catching an
  author who knows the rule and still didn't apply it — which is the only real test of a guard.
- **The fan-out trap was proven, not assumed.** I re-introduced the single-`annotate()` version on
  purpose and watched the money read RM60,000 before restoring it. The test that protects it now
  has two equal amounts in the fixture, which is the only shape that distinguishes the bug from
  its wrong cure.
- **S2 rode on existing coverage rather than duplicating it.** The credit endpoints already had 22
  endpoint-level tests including the full chain over the wire, so the sprint added the UI's own
  wiring tests instead of re-proving the server.

---

## What Went Wrong

**1. `finance_check_required` was derived from a record that only exists after the work it
describes is finished.**
*What happened:* the flag telling the screen whether the credit chain has a finance step was
computed from the sponsor's wallets. A wallet only exists once a credit is `confirmed`, so for a
credit that was recorded and awaiting signatures — the only state where the flag changes what is
drawn — there was no wallet and the flag said "no finance step". An org_admin would have been
shown a countersign button the service refuses.
*Root cause:* I derived a flag about work **in progress** from an artefact that appears only when
the work is **finished**, and my own test passed because its fixture confirmed a credit first. It
was latent for exactly one day and harmless only because no `finance` admin exists on production
— a dormant feature hides the bugs in the code that reads it.
*System change:* fixed via `_chain_organisations` (wallets ∪ credits ∪ approved memberships) with
four tests, one asserting the wallet list is empty while the flag is true. Lesson added to
`docs/lessons.md` in the general form: when a flag describes work in progress, never derive it
from a record that only appears when the work completes — the tell is that the flag's inputs and
the states it must distinguish have different lifetimes.

**2. A conversion metric read exactly zero and I only questioned it because the owner did.**
*What happened:* the sponsor detail page shipped showing "8 invited, 0 joined". Five of those
eight were sitting in the sponsors table under their own names. I built the surface, read the
figure, and did not challenge it.
*Root cause:* I treated the number as data about the world rather than as a claim about the
attribution path. `attribute_referral` fires only on a specific click, which makes it a minority
path by construction — a fact available by reading the function I had already read.
*System change:* lesson added — a funnel reporting a perfect 0 (or 100%) is an instrumentation
claim first; find the write that is supposed to move it and ask what fraction of real journeys
reaches that line. And when building the *screen* for an existing metric, spot-check two or three
rows against the underlying tables, because the first display of a number is also its first audit.

**3. The role matrix and manual said `admin` was read-only — and had been wrong for twelve days
before this sprint touched it.**
*What happened:* S2 made `admin` the maker of a wallet credit, so I opened its manual chapter to
update it and found it opening *"you have a read-only view… you don't act on them"*. That was
already false: the Payments module made the same role the maker of a payment run on 2026-07-16.
The role-matrix table said "View all (read-only)" while the Payments section three paragraphs
below said "CREATE / EDIT / CANCEL: `admin` + `org_admin`".
*Root cause:* the currency rule was followed for the *new section* Payments added and skipped for
the *summary table* above it — a summary row doesn't feel like documentation of the feature you
just built. Two contradicting facts then sat in one document, and the wrong one is the one a new
person reads first.
*System change:* matrix table corrected for all three admin roles, a "Wallet credits — access"
section added to mirror the Payments one, the general-admin chapter rewritten around its real
remit ("you prepare the money, someone else approves it"), a new org-admin section on the sponsor
record, and five FAQ entries. Lesson added: when a sprint adds a power to a role, re-read that
role's summary row and its chapter's **opening sentence**, not only the section being added.

**4. Copy that asserted history the data did not have.**
*What happened:* "Not since joining" against a column three hours old.
*Root cause:* I wrote the null copy from the *field's* point of view ("no value") rather than the
*reader's* ("what does an empty cell entitle me to conclude?"). No test can catch this — the
branch was taken correctly; the words were untrue.
*System change:* lesson added covering the general case of any field that will be null for every
existing row — write the empty state from the reader's position and say since when, and keep
confident phrasing for values you actually hold. Applies to any new audit column, consent stamp
or verification flag.

---

## Design Decisions

Both logged in `docs/decisions.md`:

1. **A referral is attributed by the link OR the invitee's email, link first.** The link is
   evidence of the route taken; an email match is an inference. Exactly one invitation closes,
   and oldest-wins credits whoever actually made the introduction.
2. **The credit UI mirrors the chain's role map and deliberately not its identity rules.**
   `same_signer` keys on email server-side because production has two active admins both named
   "Ve. Elanjelian"; the payload carries names only, so a client-side check would be wrong in
   both directions — it would let one person sign twice and refuse two who share a name. The
   button is offered and the server's refusal is rendered.

Two smaller calls worth recording here:

- **`students` is counted in its own aggregate query.** Two multi-valued `annotate()`s multiply
  each other, and `Sum(distinct=True)` — the reflex cure — collapses two equal credits into one,
  producing a plausible-looking wrong figure. One extra query, no fan-out.
- **The backfill guards on registration order; the live path does not.** At registration "after
  the invite" is true by construction; reading history it is not, and that asymmetry is
  documented in the command rather than smoothed over.

---

## Numbers

| | Before | After |
|---|---|---|
| scholarship pytest | 3598 | **3622** |
| courses + reports pytest | 1260 | 1260 |
| jest | 890 | **918** |
| jest suites | 60 | 61 |
| migrations | — | **none** |

- Referral conversion, corrected: **5 of 8** (was reported as 0 of 8). Backfill targets referral
  ids 1, 2, 3, 5, 7 → sponsors 4, 5, 8, 7, 9; ids 4, 6, 8 are genuinely still open.
- Students by sponsor (production): Suresh Thiru 38, Chong Lee Min 6, chong lee ai 1,
  Goban Arasu 1.
- New TD: **TD-183** (sponsor-module ms/ta first drafts, ~70 leaves), **TD-184** (the credit chain
  has never been driven end-to-end by a human). No TD rows resolved; TD-176 was already correctly
  marked resolved by P4b — the reverse-check found no stale rows.

---

## Carry

1. **Owner smoke, and it is the last real gap (TD-184):** record a credit as Poongulali
   (`admin`), sign as her, countersign as Suresh (`org_admin`), confirm `available` moves.
2. **Run `backfill_referral_attribution`** — report, read it, then `--apply`.
3. **ms/ta review** of the `admin.sponsors.*` block (TD-183), ideally in the same sitting as the
   partner-comms drafts (TD-180).
4. **Manual screenshots** for the two new sections (no placeholder files added; both ship
   text-only rather than pointing at a PNG that does not exist).
5. **Next: S3** — eleven editable sponsor emails + the badge pair, two-gate dark launch.
