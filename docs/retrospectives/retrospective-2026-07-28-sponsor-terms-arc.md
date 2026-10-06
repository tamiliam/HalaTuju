# Retrospective — the sponsor terms arc, T1 → T3 (2026-07-28)

**Scope:** five shipping units in one day — T1 the words, T2 the editable versioned document, T2.1
the Contract-Templates shape plus Word import, T2.2 the WYSIWYG checkpoint editor and quiz
rehearsal, T3 the sponsor-facing wizard and gate. Roadmap:
`.claude/plans/snazzy-whistling-biscuit.md` (deleted at this close — all three sprints shipped).

**Commits:** `5df0eb14` · `dfb7f5db` · `39072692` · `a55451e1` · `6f89736e` · `c784225e`.
**Migration `0134`** applied migrate-first, RLS verified. **Ships dark** behind
`SPONSOR_TERMS_ENABLED`.

---

## What Was Built

A sponsor could be registered, vetted, approved, and take a place in a programme having agreed to
**one PDPA checkbox** — a permission they grant us, imposing no duty on them. There was nothing to
cite in a suspension, and one shipped feature (AutoSponsor) had been cleared against "the existing
donation terms" that did not exist.

Now: thirteen sections and six comprehension checkpoints, versioned and immutable once published;
an admin surface to author them with AI-drafted questions and Word import; and a sponsor-facing
wizard that reads, quizzes, and takes a **typed name** as the signature — pinned to the exact
version accepted.

## What Went Well

- **The best-practice check paid for the whole arc, before a line of code.** Fifteen minutes on
  donor-advised-fund practice turned "write down what we already do" into "one thing we already do
  is described wrongly": a donor *recommends*, the charity *retains final authority*, and that is
  what makes a contribution a completed gift rather than the donor's money held on their behalf. It
  is also the only basis on which the existing two-year reallocation and AutoSponsor's automatic
  allocation are coherent. Five strings changed; the legal footing changed with them.
- **The audit before the rewrite.** T1 budgeted a portal-wide copy pass. Grepping for the MEANING
  found that most sponsor copy already said the right thing — `donationsNote` already read *"It
  becomes the charity's — it can't be withdrawn, only redirected"* — and five strings carried the
  whole problem. A sprint-sized job became a surgical one, and the owner's constraint (*"we don't
  want to scare them away"*) survived intact.
- **Two i18n guards added in T2 immediately found a live bug.** Nine `sponsorAuth.*` keys were
  referenced by the sponsor reset-password and login pages and existed in **no locale** — a sponsor
  resetting their password was reading the literal string `sponsorAuth.resetVerifying`. That is L109
  recurring, and it survived because `check-i18n.js` proves the three locales AGREE while saying
  nothing about whether a referenced key exists.
- **Deliberate non-inheritance.** The contract module is 1,140 service lines; this is ~490. Sections
  are flat, which alone removed the level tree, `MAX_QUIZ_LEVEL`, ancestor/descendant resolution,
  indent/outdent and a paired TS numbering mirror. `segment_docx` was reused for its parsing and
  explicitly not for its counterparty tokeniser — with a test asserting an imported parties recital
  comes back with no `{{` in it.

## What Went Wrong

**1. I shipped a type error and reported the gates as green.** `dfb7f5db` failed its web build:
`SponsorTermsCard`'s `t` prop was typed `Record<string, string | number>` while the app's `t` takes
`Record<string, string>`. My local `next build` had passed.
*Why:* the build ran against a **warm `.next` cache** after a dozen edits; CI builds cold. An
incremental build does not necessarily re-typecheck a file whose dependency graph it believes is
unchanged.
*System change:* **`npx tsc --noEmit`, grepped for the files you touched, BEFORE the build** —
seconds, cold by construction. Recorded in `lessons.md`. It has since caught two more errors that a
warm build sailed past (a stale prop, a fixture missing a new field), so the fix is working.

**2. I told the owner "the web deployed; the api did not" — exactly backwards.** The api had
succeeded and the web had failed.
*Why:* I inferred which build was which from the order they appeared in `gcloud builds list`, rather
than reading `substitutions._SERVICE_NAME`. The consequence was a worse-than-accurate account of
production during an incident of my own making.
*System change:* when two builds fire for one commit, **read the service name off each build**; the
list order carries no meaning. One `--format` flag.

**3. I moved the quiz away from its clause, and the owner had to move it back.** T2.1 lifted the
checkpoint onto its own tab; the owner's response was *"I like the concept of having the quiz just
after the clause"* — where T2 had put it.
*Why:* they had asked for a Quiz TAB in the four-tab spec, and I read that as "the quiz is edited on
the Quiz tab" rather than asking what the tab was for. A tab in a layout spec is not a statement
about where authoring happens.
*System change:* the resolution was better than either version — write inline, and let the Quiz tab
**take** the quiz. When a spec and an earlier working design conflict, the question is what each
surface is FOR, not which instruction is more recent.

**4. Writing the 409 test exposed a bug that would have stranded a sponsor.** `load()` cleared the
error state, so the "these terms were updated while you were reading" message was wiped a
millisecond after being set — a sponsor would have been bounced to the top of the document with no
explanation at all.
*Why:* clear-on-fetch felt tidy. It is wrong: an error explains an ACTION, and a fetch is not an
action the user took.
*System change:* clear error state when a new action starts, never in a loader.

## Design Decisions

Logged in `docs/decisions.md`: **a sponsor nominates, the programme awards**; **sections are FLAT,
not a hierarchy**; **the typed name is the signature and a variant spelling is recorded rather than
refused**; and (this close) **publishing and gating are separate decisions**.

## Numbers

| | |
|---|---|
| Shipping units | 5 (T1, T2, T2.1, T2.2, T3) |
| Migration | `0134` — 3 tables, RLS, applied migrate-first |
| pytest | **5048** (3788 scholarship + 1260 courses/reports) |
| jest | **1136** / 75 suites |
| New backend tests | 83 |
| Deploys | 6, of which **1 was a failure of mine** |
| Live bugs found by new guards | 2 (nine missing i18n keys; a tenant name in a message value) |
| Debt closed | **TD-191** closed, **TD-186** narrowed to the PDPA consent alone |

## What T4 Inherits

**S4's mandatory reject/suspend reason can now cite §13**, and the `suspended` email can safely gain
the `{reason}` token it deliberately ships without — that was blocked on terms existing.

Still owed: the **owner's go-live sequence** (publish → grandfather dry-run → apply → flip the
flag), **no human has taken the wizard in a browser** (the T3 twin of TD-184), and ms/ta for the 24
new `sponsorPortal.terms.*` leaves are machine drafts (TD-183).
