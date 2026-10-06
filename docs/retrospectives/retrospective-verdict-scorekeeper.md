# Retrospective — The scorekeeper: measured AI-vs-human reliability (verification-assurance Sprint 3, 2026-06-12)

Sprint 3, the **last** of the verification-assurance roadmap. Surfaces the measured agreement between the
AI's per-fact suggestion and the reviewer's recorded Pass/Fail — the evidence behind "can you rely on it?".
**FE + i18n only; no migration, no backend change** (the capture + the maths were already built — TD-083).
Closes layers 1–3 of the programme. Shipped to `main`.

## What Was Built
- **`verdictReliability(m: VerdictMetrics): Reliability`** (`halatuju-web/src/lib/officerCockpit.ts`) — a tested
  pure helper that turns `override_metrics` into **agreement = 1 − override rate** per fact
  (Identity / Academic / Pathway / Income) + overall, handling the zero-decisions case. +2 unit tests.
- **`AiReliabilityCard.tsx`** (new, self-contained) — reads `getVerdictMetrics()`, renders per-fact + overall
  bars with the raw `(agree/decided)` counts. Placed at the **top of the B40 applications list** (the
  officer's choice). Honest empty-state until reviewers record verdicts; a metrics hiccup falls back to
  hidden (`catch → null`) so it can never break the list page.
- **i18n** `admin.scholarship.reliability.{title,subtitle,overall,empty}` (en/ms/ta).

## What Was Already There (the 95%)
The roadmap scoped a backend capture + metric; the spike found it pre-built (TD-083, Verification-verdict S5):
the verdict-save path already snapshots `ai_verdict_snapshot` + `officer_verdict`, `audit.override_metrics`
already computes per-fact + overall override rates, and `AdminVerdictMetricsView` + the `getVerdictMetrics()`
FE client already existed. The only missing piece was the surface. So Sprint 3 was a read-only card, not a
backend sprint.

## What Went Well
- **Reading the tech-debt register before estimating saved a sprint's worth of work.** TD-083 spelled out
  exactly what was built vs missing ("queryable, not visible"). The estimate dropped from "capture +
  compute + surface" to "surface only" before any code.
- **The page-can-never-break discipline held.** The card is the first thing the officer sees on the list;
  guarding its data fetch with `catch → null` (hide, don't error) means a metrics outage degrades to an
  absent card, not a broken applications page.
- **The whole programme landed in one day across three reviewable sprints** (IC → supporting docs → the
  scorekeeper), each a vertical slice, riskiest-first.

## What Went Wrong
- **The empty card can read as "no data / broken" rather than "nothing to score yet."** Symptom: with zero
  recorded verdicts on prod (the real state today), the card shows its empty-state — which a stakeholder
  could misread as the feature failing. Root cause: a reliability surface is only meaningful *after* reviews
  accumulate, but it ships before any exist. Fix applied: an explicit empty-state copy
  (`reliability.empty`) that says it populates once reviewers record decisions — not a blank/zeroed card.
  System change: when a feature's value depends on accumulated runtime data, ship a copy'd empty-state that
  explains the precondition, never a bare zero. (Added to lessons.)
- **TD-083 was two debts in one row; only one is paid.** The surfacing is resolved; the explicit
  `officer_verdict.overall` accept/decline/hold UI toggle was deliberately not built (the card derives
  reliability from the four per-fact decisions, so `overall` stays inferred). Recorded as a partial
  resolution in the register so the unbuilt half isn't silently lost. Lesson: when a TD row bundles two
  independent fixes, resolving one means explicitly re-scoping the remainder, not flipping the whole row.

## Design Decisions
See `docs/decisions.md` — "Reliability surfaced as four-fact agreement, not an explicit overall-stance toggle (Sprint 3)".

## Numbers
- +2 jest (`verdictReliability`); **305 jest · parity 2574×3 · next build clean.** No migration, no new backend,
  no new pytest (backend unchanged).
- No flag — the card is a read-only aggregate, safe to show always (hidden until data exists).

## Deferred / Next
- **Owner-deferred (the programme's remaining layers):** the full audit-trail VIEW, and verify-before-disbursement
  (the money-gate). Not in scope; the owner's call.
- The explicit `officer_verdict.overall` toggle (the unbuilt half of TD-083) — re-open a thin follow-up only if
  a coordinator dashboard wants an explicit overall stance.
- Tamil refine of the new `reliability.*` strings (first-draft), alongside the still-pending Tamil refine of the
  Sprint 1–2 genuineness / route-switch strings.
