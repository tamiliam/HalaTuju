# Small-Change Consolidation Log

Tracks one-off small-lane changes between full sprints. Every ~10 pending entries triggers a
Consolidation Review (see `Settings/_workflows/small-change-lane.md` Part B).

## Pending
_(cleared at the 2026-07-23 review — counter reset; the 13 reviewed entries are listed in that review)_

- 2026-07-25 fix: cockpit rejected record shows the reviewer + QC decline trail; witness-org card settles once assigned (officer cockpit — `page.tsx`, `officerCockpit.ts` + test, en/ms/ta)
- 2026-07-26 fix: billing dark-ship narrowed to org_admin — super sees the usage screen before the 1 Aug flip (owner decision; reverses the Sprint-13a 'dark for everyone' position — `views_admin.AdminBillingUsageView`, `test_billing_usage.py` +3, decisions.md; no FE change, the screen probes the endpoint)
_(2026-07-29 — **the sponsor gift-membership fix was logged here and then PROMOTED to a sprint**, so it is not counted in this queue. I misclassified it: it carried a migration and touched money and visibility gating, which `wat_lint` flagged and I overrode. A concurrent agent reviewing the commits made the better case — the rule says money or visibility is a sprint, and there was a lesson in it the small lane has nowhere to put. Retro `retrospective-2026-07-29-sponsor-gift-membership.md`; 4 entries in `lessons.md`. The `0135` ledger-row gap found while applying `0136` is folded into that retro rather than logged separately. **Guardrail owed and not built: a `showmigrations`-vs-production comparison at sprint close** — `makemigrations --check` cannot see the production ledger, which is the one thing migrate-first gets wrong. It belongs in `sprint-close.md`, not in that sprint.)_
- 2026-07-26 fix: income document cards get the same tidy file row as every other doc — stale `MULTI_INSTANCE_UPLOADS` mirrored a backend rule retired 2026-06-05 (student Documents tab — `ScholarshipDocuments.tsx`, `scholarship.ts` + new `docFileLayout.test.ts`, en/ms/ta)
- 2026-07-30 fix: a question left open at quote time became permanently unanswerable while the thread kept demanding an answer — window widened to acceptance, label made honest (requests — `org_requests.TRANSITIONS`, `requestStatus.ts`, both request pages, `test_org_requests.py` +3, `requestStatus.test.ts` +4 & 1 superseded, en/ms/ta)

- 2026-07-30 fix: evidence closes when the quote is ACCEPTED (not merely at a terminal status), the quote moves below the deliberation, and the MARGIN is no longer sent to the organisation (requests — `org_requests.OPEN_FOR_SHAPING`/`can_attach`, 3 attachment guards in `views_admin`, `OrgRequestOrgSerializer`, `emails.send_org_request_quote_email`, `requestStatus.ts`, detail page, en/ms/ta; 3 guards updated deliberately)

- 2026-07-30 fix: paste could not fire at all (onPaste on an unfocused div), then had no visible surface to aim at — document-level listener + a real dashed drop zone on both surfaces (requests — `screenshotInput.ts`, `OrgRequestAttachments.tsx`, create form, new `OrgRequestAttachments.paste.test.tsx` rendering + dispatching, en/ms/ta)

> **⚠ THIS ONE WAS REPORTED THREE TIMES BEFORE IT WAS RIGHT**, and the three rounds are the same mistake at different depths: shipped to one of two surfaces; attached where it could never fire; firing with nothing on screen to aim at. Each check I wrote matched the PREVIOUS failure exactly and no further. **If a fourth input-affordance bug appears, the guardrail is not another test — it is that interactive UI does not ship without being rendered and used first.** The rendered-test gate and the four-command frontend gate list are now in `CLAUDE.md`; this entry exists so the next review can see whether they held.

> **⚠ LANE HONESTY: that entry is 15 files, against the lane's ~5.** It stayed in the small lane because it carries no migration, no new model and no new surface — three owner directives given in one sitting, each individually tiny. But the file count is the lane's proxy for blast radius, and I exceeded it rather than splitting or promoting. Flagging rather than quietly passing: if the next review finds more entries like this, the proxy needs to be file-count-OR-directive-count, or batched directives need their own lane.

> **Pattern watch for the next review — this is the FOURTH "the UI asserts something nothing checks" in a week**, after the hard-coded `/profile` padlock, `qc_override_reason` stored and never rendered, and `ai_draft_model` likewise. This one inverts it: the page stated a *requirement* ("Answer needed") without checking the requirement could be met. If a fifth appears, the cluster is asking for a guardrail, not another fix — candidate: a lint/test that a call-to-action label may only render where the corresponding action is offered.

_(Not logged here as a small change: the **Check-2 case summary** LLM feature — `verdict_narrative.py` + `AdminVerdictSummaryView` + FE lead paragraph, DARK behind `VERDICT_CASE_SUMMARY_ENABLED`. It's a feature, tracked as STR-proof S4 (dark) in CHANGELOG + halatuju.md + CLAUDE.md Next-Sprint; retro to follow after the owner live-validates the voice and flips the flag.)_
- 2026-08-01 fix: Last paid shows the date alone — the payment run reference removed from that column only (BrightPath request #5, shape one of three offered and priced; the API still sends `reference` for the link shape they may still choose) (payments — `admin/payments/page.tsx`, new `admin/payments/page.test.tsx` +3, bite-checked; no i18n, no backend change)
- 2026-08-01 fix: the billing screen opens on the MALAYSIAN month (TD-209 — the data side was already local in both places; only the default was UTC, and the three test fixtures carried the same mistake so they went red instead of catching it) (billing — `views_admin.AdminBillingUsageView`, `profile_engine._today_str`, `test_billing_usage.py` +2 & fixture, `test_usage.py` + `test_platform_cost.py` fixtures; bite-checked)

- 2026-08-01 fix: a staged analysis draft can be WITHDRAWN, and two drafts staged the same day can be told apart — staging was POST-only, so correcting a draft left the stale one in the approve list, and `approve_analysis` does not refuse a second approval (requests — `org_requests.withdraw_analysis`, `views_admin.AdminOrgRequestWithdrawAnalysisView` + route, new `formatDateTime`, detail page + `admin-api.ts`, `test_org_request_analysis.py` +9, both guards bite-checked, en/ms/ta; no schema change — `superseded_at` already existed)

> **Pattern watch — this is a NEAR-MISS of the "stored but never surfaced" cluster, at a new depth.** The four prior instances were fields stored and never rendered (the hard-coded padlock, `qc_override_reason`, `ai_draft_model`, request #3's Answer-needed). Here `created_at` **was** serialised and **was** rendered — through a date-only formatter, on a list where several rows share a day. Surfaced at the wrong GRANULARITY reads as present while answering nothing, and no "is it rendered?" check catches it. If a sixth appears, the guardrail question is no longer "is the field on screen" but "does what is on screen let the reader make the decision the screen exists for".

- 2026-08-18 fix: 25 submitted interviews re-credited to the reviewer who conducted them — pre-TD-216 the credit was stamped at draft-row CREATION, so the July triage sweep claimed every case it opened (scholarship — new `repair_interview_credit` command + `test_repair_interview_credit.py` ×12, production data pass DONE, no deploy)

> **Pattern watch — the FIX shipped, the RECORD it had already corrupted did not.** TD-216 (13 Aug) fixed the interviewer-credit rule and stopped there; five days later the owner opened a cockpit and found the old wrong name still on 29 rows. The forward fix and the backward repair are two changes and only the first is prompted by the bug report. Candidate rule for the lane: **when a fix changes how a STORED value is derived, say in the same change how many existing rows carry the old derivation and whether they are being repaired** — the repo already has the tool shape for it (`audit_pathway_ticks` computes old-and-new in one pass). This is the second instance: `award_amount`'s clear (30 Jul) also fixed the writer and left two stale rows for a human to notice.

> **Also worth the next review's attention: this is the second time in two days that a tool I use to reach the owner's surfaces had no inverse.** The engineer can stage but not retract; before this, the partner-email switch could be set but not seen (request #3). Both shipped as one-way doors and both were found by the owner using them, not by me writing them. Candidate rule for the lane: when adding an action that writes to a surface somebody else reads, name its inverse in the same change or record why there isn't one.
- 2026-08-18 fix: a closed case stops describing a future it cannot have — the empty Student profile card (a "(draft)" that does not exist, a final version promised at a verdict now refused), the empty Check 2 box ("all student tasks are clear" where no task was ever raised), and a lock line claiming "the interview is concluded" on 44 records that never held one (officer cockpit — `officerCockpit.ts` +`showsGeneratedProfileCard`/`showsCheck2Box`/`queryingLockReason`, `page.tsx` 3 sites, `cockpitCardStages.test.ts` +11, en/ms/ta ×1 key; **follow-up to the same-day sprint that fixed the three live-control cards — same predicate family, third application**)
- 2026-08-18 fix: answering a question in a request works again — the view kept passing `index=` after TD-201 renamed it `comment_id=`, so every answer raised TypeError *before* the service and 500-ed for every org on every request for 18 days; `admin` was unpassed too, so a saved answer would have been authored by nobody (requests — `views_admin.AdminOrgRequestAnswerView`, `org_requests.answer_clarification` coercion, `admin-api.ts` dead `index` type, `test_org_requests_endpoints.py` +7 all bite-checked; BrightPath #15, triaged bug/free)

> **⚠ Pattern watch — SECOND instance in one day of "the third caller is tested nowhere", both in this module.** The analysis command's database path silently dropped the engineer's proposed triage; this dropped every answer. In both, the service had tests and the endpoint had *auth* tests, and the actual call between them had none. The existing "is it rendered?" and "does it refuse?" checks are structurally blind to it: **a gap between two well-tested halves is invisible to tests of either half.** Candidate guardrail for the next review, and it is not another test — it is a rule that **every view calling a service function must have one test that exercises it end to end with the flag on and the right role**, which could be mechanised by diffing view call-sites against endpoint-test URLs. Third instance makes it a sprint.

> **⚠ Also worth the next review: the fix corrected a claim we had already POSTED to the customer.** The analysis said the reply "attaches to the oldest rather than the one you chose"; there is no chooser in the UI and the settle rule makes the distinction unobservable. Written before the code was read that closely. Candidate rule: **an analysis that will be posted verbatim states only what has been read, and separates "I have confirmed" from "I expect".**
- 2026-08-18 fix: a student is tagged by the results we HOLD, not the exam declared at sign-up — a Form Six student read STPM with no STPM results and was ranked on a CGPA that does not exist, so she carried no merit figure and fell out of the ordering entirely (scholarship — `serializers_admin.held_qualification` + both `qualification` fields + `_application_merit_score`, new READ-ONLY `audit_held_qualification`, `test_held_qualification.py` ×11, both directions bite-checked; production: 1 live record moves; BrightPath #14)

> **⚠ Pattern watch — THIRD instance of `exam_type` answering two questions at once**, after request #11's "No profile found" and the dashboard fault behind it. Each was patched where it showed; this one was settled at the source for the admin surface only, because the other five readers (`shortlisting`, `pool`, `income_engine`, `vision`, the student payload) are each correct to read the declared value for their own purpose. **A fourth instance is not another point fix — it is a rename**: the field should say which question it answers, and the surfaces that want the other one should have their own accessor. Candidate for the next review.

## Reviews

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
