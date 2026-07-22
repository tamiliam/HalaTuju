# Retrospective — the cockpit (and the consent form) say what is actually true — 2026-07-23

Five changes over two days, every one of them started by the owner *looking* at a screen and
finding it either lied or wasted space: a partner credited with 256 students who had never
applied; a "still owes" banner too vague to act on; four dead cards on the busiest stage; a
fully-documented student trapped by one failed document; and a consent form promising away more
than the platform does.

## What Was Built

- **Sources counts corrected** — `_source_application_counts` replaces `_source_student_counts`:
  bursary APPLICATIONS attributed by referral chip, with the house org taking the residual.
  CUMIG 256 → **13**, BrightPath 0 → **35**, reconciling to the 143 live applications. Plus phone
  format + validation reusing the apply form's helpers, and the inline edit reworked from a row of
  narrow cells into one labelled panel.
- **Blockers card** (`lib/blockers.ts` + the cockpit card) — names every outstanding item for an
  officer, driven by `consent_blockers`: the SAME gate the student's own submission enforces.
- **Five dead cards hidden at `shortlisted`** behind one tested predicate
  (`isPreSubmissionStage` / `showsPostSubmissionCards`).
- **Income gate: STR *or* salary** — `salary_income_satisfied` made evidence-based rather than
  route-declared, with an opt-in `effective_working_members(app, any_route=True)`.
- **Consent wording corrected** to what sponsors actually receive; `CONSENT_VERSION` → 2026-draft-6.

## What Went Well

- **The Blockers card needed no backend at all.** `consent_blockers` was already on the admin
  payload — declared, serialized, and never rendered. Its own docstring said it existed so the
  cockpit could answer "why can't this student submit yet?". Checking the payload before designing
  an endpoint turned a sprint into a frontend change, and guaranteed the officer and the student
  can never be told different things.
- **The income fix's blast radius was proved, not assumed.** Before widening
  `salary_income_satisfied` I enumerated its callers: two, both in the submission gate, neither in
  `verdict_engine` or `profile_engine`. That is why no verdict, band or generated profile moved and
  no `MODEL_VERSION` bump was needed — and why `effective_working_members` got an opt-in flag
  instead of a changed default, since IT is used by both engines.
- **The relaxation shipped with its own guard-rail.** A test asserts that with no complete cluster
  a failed STR still blocks, so "either route satisfies" can never become "nothing is required".
- **The owner caught both of my errors** (below). The review loop did its job.

## What Went Wrong

**I skipped five sprint closes by mis-classifying feature work as small changes.** Five changes
shipped with only a CHANGELOG entry each; no retrospective, decisions, lessons or Mission Control
update until the owner asked "have you done sprint close recently?". *Root cause:* I applied the
small-change lane by counting files, and ignored the second half of the rule — *"anything touching
money / consent / auth / PII, or adding a feature, page, or model, is a sprint"*. The Blockers card
adds a feature; the consent change touches consent outright. Both were sprints by the written rule
and I read only the file-count clause. *Fix:* classify by the rule's TRIGGERS before the diff size,
and treat "does this add a surface or touch consent/PII?" as the first question. → lessons.md.

**I called #9 a misclassification without reading the evidence.** I told the owner that two genuine
MySTR screenshots had been misread by the classifier. #9 was not one: its document is genuinely a
**SARA** page (a different programme), and the parser classified it correctly. *Root cause:* I read
a `doc_seen` value that had been TRUNCATED in a query result and characterised the document from
the visible fragment, instead of selecting the full value. *Fix:* never characterise a document
from a truncated field — re-select it in full before drawing a conclusion. → lessons.md.

**I proposed accepting bank payment receipts as STR proof; the owner refused, and was right.** My
reasoning was that a dated payment credit implies approval — you cannot be paid without being
approved. Sound as far as it goes, and it ignored the question that actually decides it: *can this
artefact be fabricated?* A MySTR portal screenshot comes from a verifiable government surface; a
"receipt" can be typed. *Root cause:* I evaluated the strength of the INFERENCE without evaluating
the forgeability of the EVIDENCE. *Fix:* for any proposal to widen what counts as proof, ask "how
would someone fake this?" before "is the deduction valid?". → lessons.md.

**The consent form overstated for months, and only surfaced because the owner read it.** It
promised sponsors receive the student's "profile and documents" / "supporting information". Neither
is true — no document is exposed on the sponsor path, and the profile is an anonymised allowlist.
*Root cause:* nothing ties the consent copy to the actual sponsor payload; the two drifted silently,
and the public FAQ described the truth while the legally operative text did not. *Fix:* the
decisions entry records that any new sponsor-visible field must be re-checked against the consent
wording — but the durable fix is a test asserting the sponsor allowlist has not grown (logged as
tech debt, TD below).

**A flaky jest run reported three failed suites with zero failed tests.** A worker crashed under
memory pressure (8 GB, with `node_modules` junctioned from the main checkout). A clean re-run gave
40/40 suites. Minor, but worth the habit: a suite-level failure with no failing test is a crash,
not a regression — re-run before diagnosing.

## Design Decisions

Six logged in `docs/decisions.md`: evidence-based income satisfaction; the Blockers card rendering
the student's own gate; the consent narrowing and why no re-consent; **STR recognition deliberately
NOT broadened** (declined, so it is not re-litigated); chip-based source counting with a residual
house org; and hide-don't-disable for stage-dead cards.

## Numbers

- **5 changes shipped**, 5 deploys, **0 rollbacks**, **0 migrations**.
- Files touched: 3 + 7 + 4 + 4 + 5 (plus CHANGELOG/docs).
- Tests: **+2** backend (income gate incl. the FK-drift guard), **+12** jest (blockers helper,
  stage predicate). Suite at close: **4280 pytest / 648 jest**, all green.
- **#116 unblocked**; **48** shortlisted applications get the decluttered cockpit; **143**
  applications now counted correctly across 10 source organisations.
- Two owner corrections accepted (#9 classification, payment receipts) — both recorded.
