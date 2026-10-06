# Retrospective — sponsor terms T1: the words (2026-07-28)

**Scope:** the first of three sprints on `.claude/plans/snazzy-whistling-biscuit.md`. Words and copy
only — the draft terms document, the `"you nominate, we award"` framing, the privacy notice's missing
sponsor section, and `/terms`. No models, no endpoints, no migration.

---

## What Was Built

**`docs/scholarship/sponsor-terms-draft.md`** — thirteen short sections, six marked as quiz
checkpoints, with the load-bearing sentences flagged inline and the reason given. A later editor can
change the wording freely without unknowingly changing the meaning, which is the failure mode a
legal-ish document invites.

**The framing correction.** Five strings across en/ms/ta now say a sponsor *nominates* and the
programme *awards*. Plus the privacy notice's first-ever sponsor-data section, and a `/terms` Sponsors
section that states the gift, the nomination and the absence of a tax receipt.

## What Went Well

- **The best-practice check earned its keep before a line of code.** Reading donor-advised-fund
  practice turned "write down what we already do" into "one thing we already do is described
  wrongly". A donor *recommends*; the charity *retains final authority* — and that is the only basis
  on which the existing two-year reallocation and AutoSponsor's automatic allocation are coherent.
  Fifteen minutes of research changed the deliverable.
- **The copy audit was cheaper and narrower than the plan assumed.** The plan budgeted a portal-wide
  copy pass; grepping for the *meaning* found that most sponsor copy already said the right thing —
  `statement.donationsNote` already read *"It becomes the charity's — it can't be withdrawn, only
  redirected"*. Five strings carried the whole problem. Auditing before rewriting turned a sprint-sized
  job into a surgical one.
- **Restraint was the right call on tone.** The owner's constraint was explicit: *"We want them; we
  don't want to scare them away."* Every warm sentence containing "support" was left alone. Only the
  five that assert the *mechanism* changed.

## What Went Wrong

**1. My own Tamil shipped three errors into the working tree, and I only found them because I dumped
the strings and read them.** `சேர்தது` for `சேர்த்தது` (a dropped doubled consonant),
`உறுதிச்செய்யப்பட்டது` for `உறுதிசெய்யப்பட்டது` (a consonant doubled that shouldn't be), and
`பதிவுசெய்த மாணவர்` — active voice, "the student who registered [something]" — where the passive
`பதிவுசெய்யப்பட்ட` was meant. Plus a word order that left `தமது` dangling.
*Why:* I wrote the Tamil inside a Python source file as escaped fragments, where it is unreadable, and
the terminal cannot render Tamil so the verification step I would naturally take was unavailable.
*System change:* **after writing any Tamil, dump the finished strings to a UTF-8 file and read them
back with the Read tool.** The console encoding is not a reason to skip proofreading; it is the reason
the proofreading step has to be explicit. Four corrections in five strings is a 44%-of-sentences error
rate — these remain first drafts for the owner (TD-183) and should be read as such.

**2. `npx tsc --noEmit` is not a usable gate in this repo and I nearly reported it as a failure.**
It emits errors from two test files that arrived in the concurrent merge, and there is no `typecheck`
script — the real gate is `next build`, which excludes them and exited 0.
*Why:* I assumed a standard script existed rather than reading `package.json`.
*System change:* the verification list should say **`next build`**, not `tsc --noEmit`, for this
project. Checking whether my own changed files appeared in the error list (they did not) is what kept
this from becoming a false alarm — do that before reporting any pre-existing failure as a regression.

## Design Decisions

Logged in `docs/decisions.md`: **a sponsor NOMINATES; the programme AWARDS.** Alternatives considered
and rejected: fixing the terms document alone and leaving the product copy to disagree with it (which
is how TD-166 happened), and keeping "you gift to a student" for warmth (it is the sentence that
creates the problem). Trade-off accepted: "nominate" is colder than "gift", mitigated by keeping
*"we follow your choice wherever we can"* wherever the nuance appears.

## Numbers

| | |
|---|---|
| Files touched | 7 (1 new doc, 3 locales, 2 public pages, + CHANGELOG/decisions) |
| Strings rewritten | 5 × 3 locales |
| Tamil corrections after proofreading | 4 |
| jest | **1052** / 68 suites |
| i18n parity | 4153 keys × 3, no empties |
| `next build` | exit 0 |
| Migration / endpoints / models | none |

## What T2 Inherits

The draft is the content source; T2 generates the seed fixture from it rather than hand-keying it
twice. Two i18n guard gaps stay open until T2: there is still no `admin-sponsors-i18n.test.ts`, and
`sponsorAuth` is in no guard's namespace list. `/terms` summarises the terms but cannot yet link to
the full document — that link lands in T3 when the sponsor-facing page exists.
