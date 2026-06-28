# Reviewer-query automation — roadmap

**Approved 2026-06-29.** Source: the BrightPath sponsor's "Interview Questions & expectations"
doc (`Downloads/2026 June - Interview Questions and expectations v1.docx`) + a corpus of ~60
manually-raised officer queries across the recommended + interviewing/interviewed students.

**Goal:** auto-raise the recurring, deterministic clarifications reviewers now do by hand; close
the full-household-income capture gap (apply only collects ONE earner, but the sponsor's rule is
income = the FULL household income); and make the final sponsor profile answer the sponsor's three
"need to know" buckets, so Gemini Pro has the raw material to check the boxes.

## Settled design decisions (2026-06-29)
1. **Doc-requests are uncapped; question-clarifies stay capped.** `MAX_CLARIFY=3` applies only to
   student-facing *answer-a-question* clarifies. Deterministic "upload a document" requests
   (kind=`doc`) sit OUTSIDE that cap, so adding rules doesn't spam students with questions.
2. **Need-signal principle holds (2026-06-17).** Housing photos / house-type are subjective proxies
   the owner DECLINED as need-signals. Any housing probe is an optional reviewer judgement aid only —
   never an automatic need-signal; need stays on auditable income evidence.
3. **Student-facing vs interview split by gameability.** Financial *document* gaps → student-facing
   Check 2 (hard to game). Resilience/honesty probes → interview (Check 3) only.

## The recurring patterns (from the manual-query corpus)
- Other parent's income proof missing (~9 students) — father's slip/EPF/IC, mother's slip.
- Non-earner parent status / "why one earner" (~5) — deceased / unemployed / housewife / abroad + since-when.
- Stale income document (~3) — slip dated months ago → ask current.
- Sibling in tertiary — how funded / on aid (~3).
- Utility account-holder / resend (~4) — partly already `utility_holder_unknown`.
- High utility bill → consumption/household probe (~2).
- Offer missing reporting date.
- Housing photo/type (~3) — judgement only (decision #2).
- Bursary spending priority / resilience (interview).

## Sprints

### Sprint 1 — Full-household-income capture (the #1 + #2 patterns) ✅ SHIPPED 2026-06-29
Retro `docs/retrospective-2026-06-29-reviewer-query-s1-household-income.md`. (Built below as planned.)

Detect & auto-clarify: (a) a parent with a stated occupation but NO income proof attributed → request
that parent's salary slip / EPF (kind=`doc`, uncapped); (b) a parent with no occupation AND no status
→ ask deceased/unemployed/housewife/abroad + since-when (kind=`clarify` or a structured status field).
New deterministic gap codes + `check2_queries` specs + Action-Centre rendering + i18n en/ms/ta.
Tightens B40 correctness (full household income). **Complexity: Medium-high. Highest value.**

### Sprint 2 — Stale income doc + sibling-in-tertiary funding ✅ SHIPPED 2026-06-29
(c) income doc older than ~3 months → ask current (`income_doc_stale`, doc); (d) `siblings_in_tertiary>0`
→ ask institution + funding (`sibling_tertiary_funding`, clarify). Retro
`docs/retrospective-2026-06-29-reviewer-query-s2-stale-sibling.md`.
**(e) the high-utility probe MOVED to S4** — the codebase treats high utility as an officer-only
signal, never a student query (`income_engine.utility_reasonable`); aligns with decisions #2/#3.

### Sprint 3 — Offer reporting-date: capture + persist ✅ SHIPPED 2026-06-29
Normalised `reporting_date` DateField (migration `0080`) populated by `autofill_pathway_from_offer` +
`backfill_reporting_dates` cmd; `reporting_date_unknown` clarify when an extracted offer has no date.
Retro `docs/retrospective-2026-06-29-reviewer-query-s3-reporting-date.md`.
**SPM subject-count nudge DROPPED** — not cleanly deterministic (reviewer eyeballs an odd grade count);
needs a clearer signal before automating.

### Sprint 4 — Interview (Check 3): structured guide + AI gap-spotter seeding
A reviewer guide mapped to the sponsor's three buckets (subjects-vs-results, help-seeking/tuition,
bursary-priority, resilience read; housing as optional judgement aid per decision #2); seed the Gemini
gap-spotter with the sponsor's canonical question set so it targets only unanswered gaps; capture
structured answers. **Plus the high-utility-bill probe (moved from S2)** as a reviewer-facing signal.
**Complexity: Medium-high.**

### Sprint 5 — Final-profile prompt restructure
Re-shape the draft + Pro-refine prompts to organise output around Academic resilience / Financial need /
Pathway & enrolment confidence, folding in the new clarify answers + interview guide. **Complexity: Medium.**

## Sequence rationale
Deterministic, high-precision, student-facing document gaps first (1→3 — low risk, immediate
manual-work reduction), then the AI/judgement layer (4→5). All dark/post-shortlist — near-zero live risk.
Owner gates each prod deploy (push = deploy); work in the worktree; another agent shares the repo.
