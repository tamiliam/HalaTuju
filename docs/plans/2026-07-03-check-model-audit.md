# Check 1 / Check 2 Verification-Model Audit — 2026-07-03

Scope: the document-verification and verdict model — Check 1 (Cikgu Gopal, warm student
coach), Check 2 (firm fiscal steward: verdict facts, auto-queries, doc requests), and the
handoff to Check 3 (the human interview). Four code audits (per-document coverage, verdict
evenness, query lifecycle, persona) + a live-prod comparison of human-raised vs model-raised
items for students in `profile_complete`/`interviewing`. Assessment only — nothing changed.

## Overall evaluation

The ARCHITECTURE is sound and mostly even: the two personas hold at the engine level, the
band model (Certain/Probable/Unsure/Can't-verify) is coherent and documented, cross-engine
agreement is clean after code-health S4, and Gopal's firewall is structurally intact. The
weaknesses are concentrated at four seams: (1) two document types are dead verification
limbs; (2) the query LIFECYCLE leaks (post-lock raises, wrong-doc auto-resolves, the
3-clarify cap, agenda evaporation); (3) the salary-vs-STR route seam carries three different
strictness levels for identical household economics; (4) the model asks fewer — and
narrower — questions than the human reviewers actually need, so officers hand-raise the
same boxes over and over with inconsistent copy.

## A. Integrity gaps (fix first — these break the "all boxes ticked" guarantee)

1. **`guardianship_letter` is never processed.** Full Gemini schema exists (vision.py) but
   the type is absent from `SUPPORTING_NAME_CHECK_TYPES` (views.py:566-571) → no OCR, no
   extraction, cockpit Re-run refuses (reextract.py), chips permanently grey,
   `student_guardianship_check` always empty, guardian relationship can never machine-
   confirm (verdict_engine.py:335), the cluster coach can never speak about it, and ANY
   file (even a selfie) resolves an officer's guardianship-letter request. A guardian-earner
   case is parked at amber forever with no asker and no coach.
2. **`income_support_doc` has zero processing** — the only doc Check 2 explicitly REQUESTS
   (`declared_income_evidence_missing`, check2_queries.py:77) that produces no verification
   signal at all: mere presence clears `declared_income_gaps`. A blank image "proves" a
   declared informal income.
3. **A non-official offer resolves an "upload your official offer" request.**
   `doc_match_verdict`'s offer branch checks name/IC only (resolution.py:270-277), never
   `offer_official_status`; `offer_not_official` is hidden from students
   (STUDENT_DOC_REQUEST_CODES). Officer sees red; student is told "done".
4. **Income proofs greenlight on failed reads; a stale re-upload silences the stale-slip
   ask forever.** salary_slip/epf/birth_certificate have no pending/unreadable branch in
   `doc_match_verdict` (resolution.py:291-303) — a Gemini error → empty fields → 'ok' →
   request resolved unverified. And any clean salary slip resolves EVERY open salary_slip
   request across sources/members (resolution.py:355-365, member never stored on Check-2
   items); `income_doc_stale` once resolved is never re-raised (check2_queries "never
   re-asked") though the gap persists.
5. **QC has no verdict floor.** `AdminRecordVerdictView` accepts overall-accept with a
   failed fact; QC-Accept is a pure status flip + publish (views_admin.py:1237-1244) —
   a red income fact can reach `recommended` and sponsor publication. Documented as
   advisory-model + human gate; the ABSENCE of a "no recommend with a gap fact" floor is
   decided nowhere.

## B. Lifecycle flaws (Check 2's process, not its coverage)

6. **Queries can be raised — and the student EMAILED — after the answering window locks.**
   Sync gates only on `profile_completed_at`, never `querying_locked`
   (check2_queries.py:120, resolution.py:132); `QUERY_SLA_ACTIVE_STATUSES` includes
   `interviewed` (services.py:400). The resolve endpoint then 400s `querying_closed`. Doc
   uploads remain possible post-lock but clarifies are not — inconsistent and
   student-hostile. Locked-in answered items also freeze in the officer queue (accept/waive
   refused).
7. **`MAX_CLARIFY=3` is a lifetime cap counting every status** (incl. waived) — three soft
   queries (device/transport/utility) can permanently crowd out `father_status_unknown`,
   the top-priority income-story question, with no flag that a capped-out gap exists.
   Reporting date — a sponsor-profile input of equal standing — sits in the capped pool
   while income proofs are uncapped: uneven.
8. **SLA is anchored to submission, not to the item** (services.py:412-426): an item raised
   after day 5 is born lapsed — notified but reminder-less, and the reviewer may proceed
   immediately.
9. **Open queries evaporate at Check 3.** The interview agenda = anomalies + AI gaps only;
   open/carried resolution items are never folded in (views_admin `_interview_agenda`), and
   `proceeding_with_open_queries` is a flag, not a task. Verdict ambers that say "confirm
   at interview" (`income_unverified_needs_interview`, `income_above_b40_line`,
   `academic_grade_uncertain`, `ic_service_down`) have no agenda seeding either — they
   reach Check 3 only if the officer re-reads the tiles or the optional gap-spotter runs.

## C. Verdict evenness (the route seam + band leaks)

10. **Three strictness levels for the same household economics** across the route seam:
    over-the-line = RED via STR fall-through (gap) but AMBER on the salary route
    (recommend) — the two spec docs also contradict each other here (bands doc §🟡 vs
    str-proof-spec §8); thin headroom = GREEN on the confirmed salary route (documented
    exception, decisions 2026-07-03) but AMBER via fall-through; `str_recipient_mismatch`
    bands BLUE (review + incidental greens) where spec §8 says AMBER.
11. **`SOFT_EVIDENCE` denylist rotted** (officerCockpit.ts:33-38): Phase-2B/2C soft codes
    (`unemployment_epf_corroborated`, `household_size_confirm`) can qualify a tile for
    blue — "blue needs a green" violated by evidence its own comments call soft.
12. **Wrong-person severity is uneven and partly undocumented:** slip → RED + block
    (documented); IC → BLUE (documented, NRIC anchors); offer → AMBER, no block, and the
    bands doc mislabels it under "can't read". No rationale recorded.
13. **Genuineness caps skew by household shape:** STR + BC (mother-earner) cappable;
    salary-route payslips and guardian letters have no genuineness protection at all — a
    suspect payslip can still drive green. Mechanism documented; fairness consequence not.
14. **Doc-rot:** verdict_engine.py:33-36 docstring INVERTS the review/recommend colour map
    vs the canonical doc + cockpit; `_verdict_pathway` docstring says "no offer is fine"
    (it gaps); bands doc "income is the only fact using all four bands" contradicts its own
    matrix; check2_queries docstring points at a nonexistent i18n namespace.

## D. Check-1 dead ends & persona edges

15. **Action-Centre re-upload mismatches can be silent:** a held 'mismatch' on cluster docs
    (wrong-person slip/EPF, mismatching BC) mounts the doc-anchored coach, which defers to
    the CLUSTER coach that only exists on the (post-submit unreachable) Documents tab →
    red task, no explanation (help_engine.py:426-451, DocumentHelpCoach null render).
16. **S4 #13 unification missed two consumers:** `help_engine.verdict_for_document` still
    hardcodes `('stale','rejected')` (help_engine.py:432) and the FE `shouldShowCoach`
    mirrors it (documentHelp.ts:96-98) — a `wrong_type`/`unreadable` STR re-upload gets no
    doc-anchored coach (partially masked by the `str_not_current` item copy).
17. **Persona:** both voices hold at engine level. Breaks: the Action-Centre Gopal greeting
    cheerleads (violates his own lean-tone rule); three student strings say "the earner"
    (officer jargon); Tamil "சிக்கு கோபால்" reads as "Trouble Gopal" (சிக்கு = tangle)
    — persona-critical first-draft; one grammar slip in the top-traffic STR coach string;
    the Action Centre's neutral third register works but is documented nowhere.

## E. Human vs model (live prod, Complete + Interviewing cohorts)

Volume: officers hand-raised ~60 items vs ~47 model (check2) + ~15 system — the humans
still out-ask the model. Recurring HUMAN-ONLY themes (candidates to become templated,
trilingual model queries/doc types):
- **Form-5 school-leaving certificate** (requested via doc_type='other' on ≥5 apps) — no
  slot, no auto-raise.
- **Current CGPA / latest semester results slip** for continuing STPM/college students
  (≥3 apps) — the model has no pre-award current-performance box at all (SemesterResult is
  post-award only).
- **Deceased-parent details** (when/what work) — roster records 'deceased' but nothing asks.
- **Informal-work elaboration** ("Grab driver — own account or employer? average monthly
  wages?") — the declared-income wizard captures a number; the story detail is human-only.
- **EPF statements for EMPLOYED parents** as standard corroboration (model treats EPF as
  optional; `unemployment_epf_missing` covers the unemployed only).
- **Utility bills requested when absent** (model only reacts to uploaded bills).
- **Household roster under-count** ("6 members, 5 listed") — 2C's `household_size_confirm`
  covers the over-count direction only.
- **Other-scholarships status follow-up**; **high-utility-expense justification**
  (`utility_reasonable` is officer-only today).
Officer prompts also show copy drift (typos "2016", "dirver"; three different phrasings of
the same EPF request) — exactly what templating fixes. Officers are additionally pulling
Check-3 material (STPM coping confidence, motivation probes) into written Check-2 queries —
either the division of labour needs re-stating, or a "reviewer question bank" belongs in
the model. Note: at least one human query ("enter all 10 SPM subjects") was compensating
for the 64-subject drift bug fixed in code-health S1.

## Suggested priorities (not started — owner to sequence)

- **P1 integrity:** #1 wire guardianship_letter into the pipeline; #2 give
  income_support_doc a read + verdict; #3 offer-official check on resolve; #4
  member/recency-aware upload resolution + re-raisable stale ask; #16 finish the S4
  red-states unification (help_engine + documentHelp.ts).
- **P2 lifecycle:** #6 gate sync/notify on querying_locked (+ drop `interviewed` from SLA
  statuses); #7 rethink the clarify cap (per-open cap, don't count waived, flag capped-out
  gaps); #9 fold open queries + "needs interview" ambers into the interview agenda.
- **P3 evenness/docs:** #10 reconcile the route seam in ONE spec table; #11 refresh
  SOFT_EVIDENCE; #5 decide (and document) whether QC gets a verdict floor; #12-#14 doc
  fixes.
- **P4 model growth (from prod data):** promote the human-only themes to Check-2
  queries/doc slots — leaving certificate, current-CGPA slip, deceased-parent detail,
  informal-work elaboration, EPF-for-employed, absent-bill requests, roster under-count,
  other-scholarships follow-up, high-utility clarify. Decide who owns the motivation box
  (today: nobody).
- **P5 persona polish:** Gopal greeting, "earner" jargon, the two Tamil fixes (owner),
  document the third register.


## F. Follow-up investigations (owner questions, 2026-07-03)

### F1. Does Gopal work in the Action Centre? Partially — and usage is real but uninstrumented.
- **He is alive and used**: Cloud Run request logs (21 days) show 10–45 Gopal calls/day, all
  HTTP 200 — doc-coach ~111 calls, income-cluster coach ~178 calls. The cluster coach's
  traffic comes from the Documents tab (pre-submit wizard); the Action Centre never mounts it.
- **In the Action Centre specifically, three structural limits:** (a) the coach mounts ONLY
  in the same session, immediately after an upload attempt whose scan held the task open
  (`coachDoc` React state, ActionCentre.tsx:139) — a page reload loses it: red task, no coach;
  (b) for CLUSTER docs (wrong-person salary slip/EPF, mismatching BC) `verdict_for_document`
  defers to the cluster coach, which doesn't exist there → coach renders null (the audit's
  dead-end #15); (c) the static Gopal greeting is the persona-breaking cheerleader line.
- **Performance is not discernible**: nothing records whether a served coach was AI or
  fallback, nor outcomes. (The new shared cache will now expose hourly counters
  `help_coach:*`; zero rows so far since the cache went live today.) Recommendation: log
  `source` (ai/fallback/none) + verdict per serve — one line in DocumentHelpView — and
  measure "re-upload fixed it" rates from doc-replacement sequences.

### F2. Are Check-2-requested docs slotted by a clear, ordered system? The system exists and is mostly honoured — with one systematic hole.
- The slot key is `(doc_type, household_member, request_code)` (TD-115 + request-owned
  slots): officer requests carry their own `officer_N` slot + an optional member
  (resolution.py:198-206), the server force-tags STR-route income docs to the earner
  (views.py:637-650, honouring a request's member instead), and prod data confirms the bulk
  of income docs are correctly member-tagged.
- **The hole: MODEL (check2) doc requests store NO household_member**
  (check2_queries.py:176-181 writes no params, unlike officer items) and their codes aren't
  `officer_*`, so the Action-Centre upload sends member='' + request_code=''. On the STR
  route the server rescues this (force-tag). On the SALARY route it does not: the upload
  lands BLANK-tagged → it can never count as the requested member's evidence
  (`_cluster_docs` salary route is strict-tag) → yet the ticket auto-resolves by doc_type
  and is never re-asked. Prod shows the residue: ~29 blank-tagged income docs, mostly
  salary-route slips/EPFs. This is the ordered system's one open breach — fix = write
  `household_member` into check2 DOC_SPECS items' params (FE already forwards it).
- Second-order: request-keyed officer uploads with no member picked also land blank; and
  STR-route apps with a BLANK `income_earner` (wizard unanswered) force-tag to '' — both
  produce further blanks.

### F3. Why "Mother's IC" shows as "Earner's IC" — three mechanisms; partially fixed, not for good.
- **Labelling, not storage, is the visible symptom**: the base i18n label for `parent_ic`
  IS "Earner's IC" (`admin.scholarship.docsDrawer.type.parent_ic`); the cockpit only
  upgrades it to "Mother's IC" when a member can be derived (`earnerMemberFor`,
  officerCockpit.ts:528-532): the stored tag, else (STR route) the CURRENT income_earner,
  else generic.
- Mechanisms producing the generic/misattributed label:
  1. **Legacy blanks** (pre-TD-115): STR-route blanks were backfilled 2026-06-13 (53 docs);
     salary-route blanks were deliberately left ambiguous — those still display generic.
  2. **Ongoing new blanks** via F2's hole (salary-route check2 uploads) — so the bug class
     is NOT closed; new "Earner's IC" rows are still being minted.
  3. **Route/earner switches relabel untagged docs**: an untagged card on the STR route is
     labelled with the CURRENT earner — switch earner mother→father and the same card
     re-labels, and stale cross-tags survive switches (prod shows e.g. father-tagged docs
     on mother-STR apps). S4 #17 fixed the VERDICT's card selection; the display and the
     stale tags remain.
- Also: a consent-flow parent IC (minor consent, not income) shares the same "Earner's IC"
  base label — misleading for its actual purpose.
- **Resolved for good?** No. Storage-side: upload tagging is authoritative (STR) since
  2026-06-13 and selection is member-correct since S4 — but the check2-request path still
  creates untagged salary-route docs, and blank-earner STR apps tag ''. Display-side: the
  generic fallback label guarantees the confusion resurfaces whenever a blank exists.
  Full fix = F2's params fix + a one-off backfill of the remaining ~29 blanks (attributable
  from context) + rename the base label (e.g. "Family member's IC") or always render the
  derived member.
