# Retrospective — Mobile M4c: the rule-15 sweep of the remaining student pages (2026-11-02)

## What was built
- **Rule 15 on every remaining student page** (no new design — the M4b pattern): My Bursary and all eight tabs
  (Overview, Results, Funds, Contract, Letters, News, Surveys, Mentoring — `PHONE_SECTION_FLAT` for its borderless
  cards), Home (section padding 80 → 40 px on phones; figures band 2 × 2), the scholarship landing, report,
  About / Privacy / Terms / Cookies / Contact / Get started, both pathway pages (no inner scroll box on phones), all
  onboarding steps and scholarship onboarding, and both quizzes. Desktop is unchanged.
- **Quiz follow-up (owner's call):** on phones the 10 px step dots are replaced by the header's progress bar and
  "Question n of N", with a 44 px Next (disabled until answered) and Previous; desktop keeps the dots.
- **Guards:** the rule-15 card guard now catches white cards with or without a border (incl. `border-2`); a card is
  exempt only on a real control or a named choice-button style, never by size. New sandbox surfaces for Funds,
  Contract, Letters, Mentoring, STPM / higher grades, onboarding profile and both pathway pages.
- With M4c every student page uses rule 15 and the bottom tab bar.

## Numbers (measured)
- Jest 6,118 → 6,124. mobile-check 360 → 450 cells, all passing, none worse; ledger 36 routes measured, 28 green.
- Bundle: median 145.329 → 145.407 (147 line); no line raised; tightest room 1.18 kB (`/profile`).
- Deploys: 2 (M4c a7c91931; the quiz follow-up 688a1a46).

## What went well
- **The new sandbox surfaces paid for themselves again:** they found two older phone faults the sweep did not cause —
  the higher-grades qualification choices running 36 px off a 360 screen, and a 20 px "Back to Dashboard" link.

## What went wrong
- **A divided list swallowed a non-row child again** ("+ Add elective" lost its dashed box), the same class of bug
  as M4b's "Show all institutions". *Why:* `PHONE_ROWS` styles every direct child, and buttons were placed inside the
  list for convenience. *Prevention:* every `PHONE_ROWS` list was checked for non-row children; mobile-standard rule 15
  now says only rows go inside a divided list.
- **The card guard passed vacuously on My Bursary** — it needed the exact `border` token, and those cards were
  borderless; a size-based exemption would have let a tappable card through. *Why:* the guard encoded the first
  card shape it was written against. *Prevention:* it now detects the card by ground + radius, bite-checked with a
  borderless card and a `min-h-11` card.
- **TD number clash:** another session took TD-465 while this branch held it. *Prevention:* renumbered to TD-466 at
  merge; check origin/main's highest TD at commit time, not at sprint start.

## Carried forward
- M5 sponsor portal; M6 admin shell + reviewer cockpit (may split); M7 admin "can" screens + desktop-only gate; M8
  close-out with the owner's real-iPhone walkthrough.
- TD-466 (sandbox gutter; two unmeasured screens; SPM grade pickers clip "Grade"); TD-467 (quiz questions and answers
  are English in Tamil and Malay).
