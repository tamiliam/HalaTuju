# Retrospective — TD-204: the engineer joins the thread (2026-07-31)

## What Was Built

The engineer's analysis became a first-class record: written by Claude through a command, structured
(an estimate plus the files actually read), approved by the owner before it reaches the requester,
and now required before a quote can be sent.

`OrgRequestAnalysis` is deliberately **the working paper behind one comment**, not a second thread.
The prose still travels as an `OrgRequestComment`; the row holds the evidence and the approval
lifecycle a comment cannot carry. Migration `0140`, applied migrate-first and verified.

The division of labour the owner settled: **Gemini classifies and asks; Claude reads the codebase
and estimates; the owner triages and quotes; the requester decides.**

## What Went Well

- **The design review earned its keep.** A Plan agent challenged two of my own choices before any
  code existed: `estimated_hours` had no stated audience (which would have rebuilt the two-numbers
  problem TD-202 removed), and I had no staleness anchor at all — an approved analysis survived a
  `modify()` and would have priced a description that no longer existed. Both are now decisions with
  reasons attached rather than defects found in production.
- **Counting the callers before trusting the guard.** The `award_amount` lesson says an invariant
  asserted at a caller has as many holes as there are other callers. Before writing the gate I
  grepped: `status = 'quoted'` is written once, reached by two functions, called by two views. That
  took a minute and converted an assumption into a fact.
- **Measuring the blast radius instead of estimating it.** For request #4 the fix touches how
  applications are scored, which sounds sweeping. Querying production turned it into a number:
  53 households on the STR route, 10 without an STR letter, **exactly one** with salary evidence
  for the check to fall through to. That single number is the difference between a nervous change
  and a confident one.
- **The bite-checks found the belt-and-braces working.** Adding `cited_files` to the org serializer
  failed three tests — the exact-key snapshot AND both value-leak assertions. The snapshot catches a
  new key; the value tests would catch a path smuggled inside an existing string. Neither alone is
  enough.
- **Two real requests, not a fixture.** The workflow ran end to end on live records the same day,
  and both live-review defects below were found that way rather than by review.

## What Went Wrong

**1. The triage form defaulted to the more expensive classification, and I did not look at it.**
- *Symptom:* the owner triaged request #4, saw the AI had read it as a bug, saw my analysis agree —
  and the form still offered "Feature request / Sprint".
- *Root cause:* `triageKind`/`triageLane` were hard-coded at `'feature'`/`'sprint'` and nothing read
  `ai_draft_kind`. Pre-existing, but this sprint made it *visible* by putting a second opinion on
  the same screen. I built a prefill for the quote hours from the analysis and did not ask what
  **else** on that screen had a default that disagreed with the data beside it.
- *Why it matters more than a UI nit:* a bug is FREE and a feature is PRICED. Accepting the default
  silently converts one into the other.
- *System change:* seeded from the AI draft behind a touched-ref, bite-checked. The transferable
  habit: **when you put two opinions on one screen, check every control that already had a default —
  a default is an opinion too, and it was written before the other one existed.**

**2. I placed the analysis panel below the triage form.**
- *Symptom:* the owner was asked to classify a request before reading the thing that tells them the
  classification.
- *Root cause:* I reasoned "the analysis is what the quote stands on, so put it above the quote" and
  never checked what else sits between. Triage does.
- *System change:* moved above triage. Habit: **place a new panel by walking the whole surface in
  order, not by naming the one block it must precede.**

**3. I guessed at a production connection string twice before checking.**
- *Symptom:* the command could not reach production; the direct Supabase host is IPv6-only. I tried
  the pooler with a guessed region prefix, failed, tried another, failed.
- *Root cause:* I had the means to check (`list_projects` returns the region) and reached for a
  plausible string instead. Classic guess-vs-verify, and the third attempt only worked because I
  finally looked.
- *System change:* recorded in lessons. The tell is precise — **any hostname you assemble from a
  pattern is a guess; ask the thing that knows.**

**4. A shell heredoc broke on quoting, again.**
- *Symptom:* a multi-line test append silently wrote nothing; the shell reported an unmatched quote.
- *Root cause:* this project already has a standing note about heredocs eating string literals, and
  I used one anyway for content full of apostrophes and regex escapes.
- *System change:* none needed — the existing rule is right, I just did not apply it. Used the Edit
  tool instead, which is what the rule says.

## Design Decisions

Logged in `docs/decisions.md`: the separate table over comment columns; hours and cited files as
owner-only; the gate at both quote twins rather than in the shared helper; supersede on `modify`
only.

## Numbers

| | |
|---|---|
| pytest | **5258** (+47) |
| jest | **1249** (+15) |
| `next lint` | 0 errors |
| i18n | 4360 × 3 |
| Files touched | 19 (budget 40) |
| Migration | `0140` — applied migrate-first, RLS + policy verified, advisor clean |
| Guards bite-checked | 5, each confirmed to fail then restored |
| Live analyses | 2 — request #2 (6.5h, approved) and #4 (4.0h, approved, triaged bug/sprint) |
| Deploys | 2 (the feature; then the two live-review fixes) |

## Carried

- **Request #4's fix is not built.** #106 is shortlisted with a red income card that should be
  green. Analysis approved, triaged bug/sprint, 4.0h estimated.
- **Requests #5–#8** are four more bugs sitting at `submitted`, untriaged.
- **Two tooling follow-ups, deliberately deferred** until the workflow has been used enough to rank
  them honestly: a badge that surfaces a request awaiting analysis (nothing summons the engineer
  today), and moving the command off direct database access onto the API with a short-lived token
  (it currently requires pulling live DB credentials onto a laptop — done twice this sprint,
  deleted twice, which is a manual mitigation and those fail eventually). ~2h each.
- **Tamil first drafts** for the whole `admin.requests.owner.analysis*` block and
  `detail.author.engineer`.
- **`clarifications`** is still populated on requests 2 and 3 from TD-201; nothing reads it.
