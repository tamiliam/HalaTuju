# Small-Change Consolidation Log

Tracks one-off small-lane changes between full sprints. Every ~10 pending entries triggers a
Consolidation Review (see `Settings/_workflows/small-change-lane.md` Part B).

## Pending

_(cleared at the 2026-08-19 review — counter reset; the 14 reviewed entries are listed in that review)_
- 2026-08-19 fix: partner and sponsor mail bills the organisation, not the platform — the other 62 of the 125, on the owner's ruling that sponsoring is org work (the nav registry had said so all along); neither attributed to the obvious object, both refuse when the owner is not single (billing — `usage.sole_organisation_id`, `partner_notify._owning_org_id`, `sponsor_notify._sponsor_org_id` + the legacy alert path, `test_usage_attribution.py` +10)

## Reviews

### 2026-08-19 — Consolidation review (14 small changes, 25 Jul → 18 Aug)

**Reflect.** Fourteen entries over three and a half weeks, and they are not evenly spread. **Five
are the Requests module** (three on 30 Jul, one on 1 Aug, one on 18 Aug); **three are billing**
(the dark-ship narrowing, the Malaysian-month default, the six senders billing the platform); the
remaining six are one-offs across the officer cockpit, the student Documents tab, payments and the
interview-credit repair. Two entries in the window were correctly refused by the lane and closed as
sprints instead (the sponsor gift-membership, and the exam-type overload — the second caught by
`wat_lint` before the close rather than by a reviewer after it, which is the linter doing its job).

Most were genuine fixes. Three were symptoms: the interview-credit repair (the rule had been fixed
five days earlier and the corrupted rows left behind), the billing attribution (four senders wrapped
in July, the next eight born wrong), and the Requests answer 500 (a rename completed in the service
and the endpoint and not between them).

**Cohere — three clusters, and one of them is now a sprint.**

**1. The Requests module (5 entries) — NOT promoted, and the reason is the interesting finding.**
Five patches to one surface in three weeks reads like a redesign asking to be a sprint. It is not.
The three on 30 Jul were a UI-affordance failure reported three times before it was right, and the
guardrail that answered it — the rendered-test gate plus the four-command frontend gate list, both
landed in `CLAUDE.md` — **held**: no further UI-affordance bug has appeared in this module since.
What appeared instead was a *backend* seam failure (the 18 Aug answer 500). **The guardrail worked
and the failure moved next door.** That is worth recording as a success rather than promoting the
module wholesale, and it points the next guardrail at the seam rather than the surface.

**2. "The fix was complete for the cases that existed when it was written" — now FOUR instances,
and the class regenerates.** The interview credit corrected the rule and left 25 rows carrying the
old one; `award_amount`'s clear fixed the writer and left two stale rows; the billing attribution
wrapped the four senders then firing and left the next eight to be born wrong; and — not previously
counted, because it closed as a sprint — **the SPM exam-year anchor (BrightPath #12) was complete
for the certificates that existed and broke on a differently-cropped scan.** The first two are about
rows already written; the last two are about cases not yet written, which is worse, because nothing
stops them arriving. Guardrail below.

**3. "The UI asserts what nothing checks" — five instances plus a near-miss, and it has stopped
being the same bug.** The hard-coded padlock, `qc_override_reason`, `ai_draft_model` and request
#3's "Answer needed" were all *field stored, never rendered*. The near-miss (a staged draft's
`created_at` rendered date-only on a list where several rows share a day) was *rendered at the wrong
granularity*. The class has drifted from "is it on screen" to "does what is on screen let the reader
decide". That is no longer mechanisable as one check, and a sixth point fix would not converge.
**Deliberately NOT given a guardrail this round** — it is recorded as a live watch, and the next
instance should be read for which of the two it is before anything is built.

**Promoted:**
- **TD-218 — `exam_type` answers two questions and six surfaces read it.** Now the FIFTH instance
  (#11's "No profile found", the dashboard behind it, #14's admin tag, #14's apply step, and the
  `results_exam_type` work itself). The standing note said a fifth is a rename, not a fix. It is a
  sprint and it is now written down as one.
- **TD-219 — nothing tests the seam between a view and the service it calls.** Two instances in one
  day on 18 Aug (the analysis command's dropped triage; every answer 500-ing for 18 days), both with
  a well-tested service, auth-tested endpoint, and nothing exercising the call between them. A gap
  between two well-tested halves is invisible to tests of either half. The mechanisable form —
  diffing view call-sites against endpoint-test URLs — is a sprint, not a checklist line.

**Anticipate — the guardrail landed this round.** Cluster 2 is the one that regenerates, so it is
the one that got prevention rather than another fix. Two rails added to `small-change-lane.md` Part
A, where every future small change has to read them:

- **A fix that changes how a STORED value is derived must state how many existing rows carry the old
  derivation, and whether they are being repaired.** The repo already has the tool shape for it —
  `audit_pathway_ticks` computes the old and the new answer in one pass over real data.
- **A fix whose correctness depends on every FUTURE caller remembering something is a convention,
  not a fix.** Name in the change how the omission is made impossible or loud, or say why it cannot
  be. This is the half that regenerates, and it is the one the 18 Aug billing entry named and
  deliberately did not build.

**Lane honesty carried forward.** One entry in this window was 15 files against the lane's ~5 cap
(the 30 Jul evidence/margin/quote change — three owner directives in one sitting, each individually
tiny). It carried no migration, model or new surface, so it stayed. That is now the second window in
which the file-count proxy has been exceeded by batched directives rather than by scope. **If it
happens again, the proxy needs to become file-count-OR-directive-count** — flagged, not yet changed,
because two instances is thin evidence for a rule change.


### 2026-07-23 — Consolidation review (13 small changes, 1 Jul → 23 Jul)

**Reflect.** The 13 entries fall into four groups: the **STR-proof verdict/copy stream** (4 ×
2026-07-01: means-test refinement to MODEL_VERSION 1.2.1, Lulus chip, prescriptive Check-2 copy,
the raw-ICU rendering fix); the **Administration-panel world split** (2 × 2026-07-15: per-panel
lists, staff-table split); the **tenancy fix-forward annotations** (3 × 2026-07-23, from the
compliance check-up — deliberate rule-1 exemptions recorded in place, not fixes); and four
genuine one-offs (pathway-switch promotion engine fix +9 tests; verdict-item i18n gap + class
guard; witness-card stage-gating +11 tests; cancelled-runs hide-toggle, which records the design
decision that `payments.cancel` deliberately has no delete).

**Cohere.**
- **PROMOTED: the STR-proof cluster** → `docs/retrospective-2026-07-23-str-proof-cluster.md`,
  the consolidated retro the 2026-07-01 entry called for. Honest finding recorded there: the
  1.2.1 means-test refinement rode the small lane but bumped a verification model and touched
  money-adjacent verdicts — by the lane's own boundary that was sprint-grade work. The retro is
  the repayment; the boundary reminder stands: **a MODEL_VERSION bump is never a small change.**
- The Administration-panel pair needed no promotion: coherence was restored by the per-panel
  design + `lib/adminStaff.ts` helpers with regression tests (the guardrail landed with the fix).
  Any further panel polish batches with the next real admin work (deploy cap rule).
- The three tenancy annotations are not drift — they are the 2026-07-22 audit's fix-forwards,
  and their real home (extraction to cohort fields) remains Phase-2 S5–S9.

**Anticipate.**
- **Recurring class (×2): a backend enum value reaches the officer UI without its i18n key**
  (2026-07-01 raw ICU render; 2026-07-23 missing `pathway_type_switch`). The guardrail landed
  with the second fix — `test_verdict_item_i18n.py` covers the WHOLE verdict-item class, so the
  next new verdict item fails CI until its en/ms/ta keys exist. Generalised into
  `docs/lessons.md`: when backend enum values feed frontend i18n keys, ship a class-covering
  parity guard with the first fix, not a per-value patch.
- No other class recurred; 4 of the 13 entries carried their own regression tests — the lane
  working as designed.

**Close-out.** Pending cleared (13 → 0; counter reset). Promoted: 1 consolidated retro.
Guardrails: verdict-item i18n class guard (landed with the 2026-07-23 fix, credited here) +
the lessons.md line. Boundary reminder recorded: MODEL_VERSION bumps and money/consent-adjacent
verdict changes take the sprint lane.

### 2026-06-16 — Live-review round (9 small changes)
**Reflect.** The 9 changes touched three surfaces: the **AI profile generator** (5: distil-all-inputs,
interest-quiz, statement-of-intent, grades-grouping/ethnicity, prompt-versioning), **web i18n hygiene**
(3: TD-118, TD-120, cockpit copy tweaks), and **reviewer access** (2: hide assignee filter, set-password page).
Most were genuine fixes; the profile ones were additive improvements, not symptom-patching.

**Cohere — clusters promoted:**
- **Profile completeness & safety (5).** Not five fixes — one coherent body of work: "make the AI profile use ALL
  the data the student gave us (typed fields, quiz, statement-of-intent), summarised well, and without leaking PII or
  ethnicity." Recognised as a mini-feature; the prompt is now **versioned** so it can evolve safely. Captured in
  `decisions.md` (prompt versioning; grades-by-group; generalise-ethnicity).
- **i18n drift after redesigns (3).** Recurring class: cockpit redesigns leave orphaned `admin.scholarship` keys.
- **Reviewer onboarding (2).** Non-Google invitees couldn't onboard; the set-password page closes the systemic gap.

**Anticipate — guardrails (recurring fix → prevention):**
- i18n orphans → **guardrail test added** (`messages/__tests__/admin-scholarship-i18n.test.ts`, dynamic-aware) — the
  class can no longer silently regrow. ✅
- Stale AI drafts after a prompt change (the #18 trap) → **PROMPT_VERSION + version-aware backfill added** — staleness
  is now detectable by version, and re-running the backfill only refreshes stale drafts. ✅
- **Candidate (not built):** schedule the version-aware backfill (or trigger it on a `PROMPT_VERSION` bump) so drafts
  self-heal without a manual cron call. Logged for a future pass.

**Close out.** Pending cleared (counter reset). Guardrails landed in the same round. Folded into the 2026-06-16
sprint-close (retrospective `docs/retrospective-2026-06-16-livereview-round.md`).

### 2026-06-29 — Consolidation review (15 small changes)
Covers the 14 `## Pending` entries (2026-06-16 → 2026-06-29) plus one reviewer-FAQ-docs entry that had been
misfiled under this section.

**Reflect.** The 15 changes touched five areas:
- **Document extraction & income computation (5)** — SPM 2-column slip under-read; handwritten salary-voucher
  `ringgit|sen` mis-read; salary-route earner Optional/undeclared (#90); `document_unreadable_blockers` list-vs-app
  bug; IC/parent_ic silent-OCR self-heal. All genuine fixes — but all the *same shape*: a document reads wrong and a
  B40 decision turns on the bad read.
- **Reviewer features (4)** — Guide + FAQ pages; language fluency (migration 0059); advance-notice email (migration
  0060); a follow-up FAQ-content update. These were **features with migrations**, not small changes.
- **Check-2 / Action-Centre student visibility (2)** — reviewer-raised requests now notify the student; system
  "couldn't read your doc" requests surfaced to the form-locked student.
- **Interview/status flow (2)** — fold the two interview-question buttons into one; advance `profile_complete →
  interviewing` when slots are proposed.
- **Copy + display casing (2)** — "Sponsor profile (draft)" → "Student profile (draft)"; ALL-CAPS offer programme
  name leaking to the sponsor pool (#107).

**Cohere — clusters promoted:**
- **Document-extraction & income robustness (5) → [TD-151].** The dominant cluster, and the one that keeps
  regenerating: five isolated point-fixes that are really one hardening pass (a scrubbed extraction-regression
  corpus + an income read-sanity gate + a generalised silent-OCR self-heal). Promoted to `technical-debt.md`
  TD-151 as a 1-sprint pass, not an N+1th point fix.
- **Reviewer features rode the small lane (4) → process drift.** Per `small-change-lane.md` step 1, a feature or a
  migration is a **sprint**, not a small change — these four (two with migrations) should have been one
  "reviewer-onboarding & comms" sprint. Shipped fine, but the boundary slipped four times; this is the recurring
  *process* class, addressed by the guardrail below.

**Anticipate — guardrail landed this round:**
- **`wat_lint` now flags a misclassified small-lane entry** — any `## Pending` line containing `feat:` or
  `migration` is reported as "should have been a SPRINT" (`small-change-lane.md` step 1). Converts the recurring
  feature-rode-the-lane drift from a thing-we-notice-in-hindsight into a mechanical catch at the next lint.
- **Display-value leak via a non-canonical write path** (the #107 casing leak) was already converted to prevention
  in the same hotfix (idempotent `title_case_programme` guard + a `docs/lessons.md` rule to grep every writer of a
  normalised field). No further action.

**Close out.** Pending cleared (counter reset). Guardrail (`wat_lint` misclassification check) and the casing guard
landed in-cycle; the extraction cluster is parked as TD-151 for a dedicated sprint.
