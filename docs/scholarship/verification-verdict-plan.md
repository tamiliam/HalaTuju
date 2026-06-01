# Verification Verdict, Resolution Queue & Two-Stage Profile Panel — Implementation Plan

**Status:** draft for approval (2026-06-01). Decomposes the design settled in
conversation into a right-sized sprint roadmap. Builds on the post-shortlist
vision (Phases A–D already shipped). Do **not** begin Sprint 1 until approved.

> The officer audits the AI's verdict; they do not assemble it. A phone call is
> the scarcest resource in the system — design everything to drive contacts
> toward zero.

---

## 1. The problem this solves

Today the officer opens an application and sees **scattered signals** — Vision
chips per document, a "Pre-interview flags" list, raw uploads. They must
re-assemble the picture in their head and click through eight documents to do
it. That is not economical, and it does not scale to hundreds of applicants on
volunteer manpower.

We have all the *intelligence* already (Vision OCR, doc-assist, anomaly engine,
draft→final profile). What's missing is the **synthesis layer**: a verdict the
officer reviews, a queue that resolves gaps without a phone call, and an
interview panel that turns the draft profile into the final one.

---

## 2. Design principles (settled in conversation — these are load-bearing)

1. **Four facts are the spine.** Every profile reduces to: **Identity** (name +
   NRIC), **Academic** (results + completeness), **Income / B40** (the hard
   one), **Pathway** (offer). Everything else is *evidence feeding these four*.
2. **The trust line.** The AI may **assert** facts that are checkable by
   *matching* (identity, pathway, "this slip is hers"). The AI may only
   **assemble and recommend** facts that require *judgement*. A human always
   pulls a reject lever.
   - **Income exception (settled):** the AI **may assert income green when a
     verified STR *document* is present** — i.e. an STR letter uploaded **and**
     OCR-matched to the household, not the self-declared `receives_str`
     checkbox. With no verified STR document, the AI **only recommends** from the
     weaker evidence (EPF, salary, utility-bill proxy) and a human decides.
     (Theresa: STR ticked but no letter → stays 🔴 / recommend until she uploads
     a matching STR letter.)
3. **Green is expensive; the engine under-claims.** A green tick means "nothing
   to look at here." When in doubt, drop to amber "confirm." The cost of a wrong
   green (waved through) far exceeds a wrong amber (20 seconds confirming
   something fine). This fights automation complacency.
4. **Resolve before you escalate.** The AI settles what it can from evidence it
   already holds — *before* it ever bothers a human. (Theresa's name "mismatch"
   was an OCR line-break; the patronymic was corroborated by the utility bills.
   The AI should close that itself and never raise it.)
5. **Missing ≠ failed.** A poor family often *cannot produce* a document.
   Income has three states: **Verified** / **Gap–chase docs** / **Gap–but
   explained** (a human weighs the explanation). This is the fairness valve.
6. **Address = a coherence / fraud test, not a data-quality task.** We collect
   it to confirm every document belongs to the *same person*. Minor drift (same
   house, postcode varies) → pass, accept as noise. Major divergence → high
   fraud signal, escalate (human decides).
7. **IBKR model: discrete tickets, not one lumped query.** Each unresolved issue
   is its own point, closed independently by **a document OR an explanation OR a
   one-tap confirm**. Some are system-generated, some officer-generated. The
   self-service ticket queue is the mechanism that drives **human phone calls to
   ~zero** — the call is the rare exception (non-responders / genuine judgement).
8. **One shape, every applicant.** Standardisation over exhaustiveness. A weird
   applicant gets *more amber rows*, never a *different screen*.
9. **Two-stage profile is the hinge.** Officer panel shows the **draft** profile
   (what the sponsor will read, minus PII) + the **caveats** (escalated, unre-
   solved queries). Officer resolves them (written query or call), adds findings
   + a verdict → AI generates the **final** profile.

---

## 3. What already exists (reuse, don't rebuild)

| Asset | File | Role in this plan |
|---|---|---|
| Vision OCR + matchers | `apps/scholarship/vision.py` | Identity/address inputs; **extend** for grades (Sprint 2) |
| Doc-assist (Gemini fields) | `vision.py` / `_call_gemini_json` | Extracted EPF/bill/offer fields → verdict evidence |
| Anomaly engine (10 rules) | `apps/scholarship/anomaly_engine.py` | Feeds the verdict's "unresolved" list |
| Interview gap-spotter | `apps/scholarship/gap_engine.py` | Merges into the resolution/agenda queue |
| Draft→final profile | `apps/scholarship/profile_engine.py` (`generate_*`, `refine_*`, `_call_gemini_text`) | The two-stage profile (Phase D done) |
| Interview capture | `InterviewSession` model + admin card | Officer findings (Phase C done) |
| Cikgu-Gopal coach + caching | `apps/scholarship/help_engine.py` | Tone + per-application cache pattern for tickets |
| Request-more-docs | `info_request_note` + `AdminRequestInfoView` | Generalised into officer-raised tickets |
| Officer page | `halatuju-web/.../admin/scholarship/[id]/page.tsx` | Base for the verdict scorecard + panel |

The genuinely **new** build is: the **verdict rollup engine**, the **grade OCR**,
the **ResolutionItem ticket model + queue**, the **student Action Centre**, and
the **panel integration** that shows draft+caveats and wires to final.

---

## 4. Sprint roadmap (5 sprints)

### Sprint 1 — Verification Verdict engine + officer scorecard (read-only) ✅ DONE (2026-06-01)
- **Shipped:** `verdict_engine.py` (pure `build_verdict` → four facts × {status, evidence, unresolved}),
  `AdminApplicationDetailSerializer.verdict`, the admin scorecard card, `AdminVerdictFact`/`AdminVerdictItem`
  types, i18n `admin.scholarship.verdict.*` × en/ms/ta (parity 1701). 23 new tests; full scholarship suite 433
  green; `next build` clean. No migration. On branch `feature/verification-verdict-s1` (not yet committed/pushed —
  push triggers deploy, so held for the user's go-ahead). The polished card + documents-box redesign is S5.
- **Lessons applied (from `docs/lessons.md`):** (#55) the verdict engine is a
  pure function — its test fixtures must set **every** attribute it reads, or
  omitted attrs silently read `None` and the verdict is wrong; (#49) access
  optional reverse OneToOne (`funding_need`/`sponsor_profile`) via
  `try/except DoesNotExist`; engine stays **deterministic** (no Gemini) and is
  unit-tested as a pure builder (#82); (#54) `AdminApplicationDetailSerializer`
  — enumerate consumers before adding the field; (#83/#40) serialise pytest vs
  `next build`, run `next build` after the scorecard TSX. **Scorecard render
  reuses the existing admin card pattern** (Pre-interview-flags / Verify-&-accept
  cards) — the full panel redesign + Stitch pass is S5; S1 is a functional card,
  not a novel layout.
- **Goal:** A four-fact RAG verdict, computed before the officer arrives, shown
  as one scorecard above the existing flags.
- **Scope:** new `apps/scholarship/verdict_engine.py` (pure Python rollup over
  existing signals → `{fact, status, evidence[], unresolved[]}`; under-claim
  bias; auto-resolution rules: multi-line-name truncation, patronymic
  corroboration, address coherence classifier minor/major); serializer field on
  `AdminApplicationDetailSerializer`; scorecard render on the admin page.
- **Acceptance:** Theresa renders **Identity ✅** (name auto-resolved, no flag
  raised), **Pathway ✅**, **Academic 🟡**, **Income 🔴**, each with the correct
  evidence + unresolved lists. Zero AI cost (deterministic). Tests per fact +
  the auto-resolution rules.
- **Complexity:** Medium. No migration.

### Sprint 2 — Grade OCR + academic verification ✅ DONE (2026-06-02)
- **Shipped:** `vision.py` results-slip schema → `results: [{subject, grade}]` + grade prompt hint;
  `academic_engine.py` (`_SUBJECT_BM` mirror of subjects.ts; `read_slip` supporting new + legacy shapes;
  `compare_academics` = completeness + accuracy by normalised name); `_verdict_academic` rewritten → `verified`
  when complete+accurate+name-ok, else `review` with specific gaps; widened `vision_fields.fields` FE type + a
  renderer tweak; i18n +3 item codes (parity 1704). **No migration** (grades live in `vision_fields`). 12 new
  tests; scholarship suite 445 green; `next build` clean. Real-data check: completeness fires on Theresa's existing
  slip (8/10) with no re-OCR; accuracy pinpoints per-subject disagreements. **Billable real-slip OCR smoke** is a
  user-run follow-up (docs re-extract on re-upload / admin re-run).
- **Goal:** Read the actual grades off the results slip and check them — the
  prerequisite that doesn't exist today (current OCR reads subjects + name only).
- **Scope:** extend results-slip doc-assist to extract `{subject → grade}`;
  `academic_engine` for **completeness** (slip subjects vs entered) +
  **accuracy** (typed grade vs OCR'd grade, per subject: agree/disagree); wire
  into the Academic fact (Sprint 1). Likely an additive field on
  `ApplicantDocument` for the extracted grades.
- **Acceptance:** Theresa shows "**8 of 10 entered — missing Moral + Kesusasteraan
  Tamil**"; per-subject agreement once grades are read (agree → green, the one
  disagreeing cell → amber). Real-document tested (S15 lesson: heuristics need
  real docs, not just synthetic fixtures).
- **Complexity:** Medium-High. Additive migration (migrate-first via MCP).

### Sprint 3 — Resolution ticket model + auto-generation (backend) ✅ DONE (2026-06-02)
- **Shipped:** `ResolutionItem` model (migration `0036`, RLS) + `resolution.py` (`CODE_TO_TICKET`, idempotent
  race-safe `sync_resolution_items` with auto-resolve + no-re-nag, `resolve_item`, `add_officer_item`); student
  endpoints (list + resolve) + officer endpoints (add + waive/resolve); sync wired into doc upload/delete; admin
  serializer exposes the live open queue. The 3 excluded codes (`ic_service_down`, `grades_unverified`,
  `str_present_unverified`) confirmed with the user. 9 tests; scholarship suite **454** green. Real-data: Theresa →
  2 tickets (STR upload + add 2 subjects). **Backend only** (S4 = student UI). Migration on branch; **prod
  migrate-first at deploy** (new-model contenttypes workaround + RLS, TD-058).
- **Goal:** Turn the verdict's gaps into discrete, independently-resolvable
  tickets (IBKR model).
- **Scope:** new `ResolutionItem` model `{application, fact, code, prompt,
  kind: doc|explanation|confirm, status: open|resolved|waived, source:
  system|officer, resolution_doc/_text, timestamps, resolved_by}` (new table,
  RLS deny-by-default); generator from `verdict.unresolved[]` (idempotent, dedup,
  re-runs on upload like `help_engine`); each ticket closeable by **doc OR
  explanation OR confirm-tap**; officer-raised manual tickets (generalise
  `info_request_note`); re-run verdict on resolution and auto-close satisfied
  tickets (e.g. a postcode confirm clears the utility-bill addr flags).
- **Acceptance:** Theresa auto-generates: STR letter (doc), mother's IC (doc),
  2 missing subjects (confirm/update), postcode confirm (confirm). The name
  ticket is **not** generated (auto-resolved in S1).
- **Complexity:** Medium-High. New-model migration (contenttypes workaround,
  migrate-first via MCP).

### Sprint 4 — Student Action Centre (frontend) + resolution flows
- **Goal:** Student self-service queue — the thing that makes the phone call
  unnecessary.
- **Scope:** an "Action Centre / Things to resolve" surface on `/application`:
  discrete tickets, each with **upload-or-explain-or-confirm**, Cikgu-Gopal
  tone; async; on resolve → backend re-check (S3) → ticket clears + verdict
  updates. **Stitch prototype first** (UI rule).
- **Acceptance:** Theresa logs in, sees 4 tickets, clears them; queue empties;
  verdict flips Income/Academic forward. Pure-logic helpers node-tested.
- **Complexity:** Medium. No migration.

### Sprint 5 — Officer interview panel: draft profile + caveats + verdict → final
- **Goal:** The panel becomes the hinge: review the draft, clear the caveats,
  record a verdict, generate the final profile.
- **Scope:** panel view extending `admin/scholarship/[id]`: (a) the **draft
  sponsor profile** (PII-stripped preview = the sponsor's view), (b) **caveats**
  = the escalated unresolved tickets, (c) officer tools — pose written query (→
  student ticket), log call outcome, add findings (`InterviewSession`, exists),
  record verdict, (d) verdict → trigger **final profile** (`profile_engine`
  refine, Phase D, exists); (e) **audit/override capture** — store AI verdict vs
  officer decision + reason; expose an override-rate metric (how good is the AI);
  (f) **documents box redesign** — the current raw flat list is messy; rebuild it
  as a neat, professional evidence drawer (grouped, consistent chips, the
  extracted fields legible) as part of the panel's Stitch design. Designed once,
  with the panel — not patched piecemeal earlier.
- **Acceptance:** officer opens Theresa, sees draft + remaining caveats, resolves
  them, records a verdict, the final profile generates; the override is logged.
  **Stitch prototype first.**
- **Complexity:** Medium (mostly wiring existing Phase C/D pieces + audit).
  Additive audit fields (migration).

---

## 5. Sequence & rationale

Dependency-ordered, risk front-loaded:

```
S1 verdict engine ─┬─► S2 grades feed Academic
                   ├─► S3 tickets consume verdict.unresolved
                   │        └─► S4 student clears tickets
                   └────────────► S5 panel reads verdict + draft → final
```

- **S1 first** — the verdict is the spine everything else hangs off, and it's
  free/deterministic so it de-risks the model cheaply.
- **S2 early** — the grade-OCR is the riskiest unknown (extraction reliability);
  surface it before building UI on top.
- **S3 → S4 → S5** — backend tickets, then the student side, then the officer
  side that ties the loop to the two-stage profile.

**5 sprints, divided so:** each ships something testable (S1 a visible scorecard;
S2 a working grade check; S3 a queryable ticket queue; S4 a usable student
surface; S5 the closed loop). Could merge S3+S4 if you want fewer handoffs, but
it's tight (~30 files) — recommend keeping them split.

---

## 6. Cost, safety, conventions

- **Cost:** the rollup is **free** (deterministic). AI only for: grade OCR (per
  upload, cached per document-set) and draft/final profile (exists, cached,
  admin-triggered). Reuse the `vision._call_gemini_json` / `profile_engine.
  _call_gemini_text` seams; **mock in CI — never a live model call in tests.**
- **Migrations:** S2 (grades field), S3 (`ResolutionItem` table), S5 (audit
  fields) — all additive, **migrate-first via Supabase MCP** (deploy does not
  run migrate); new tables get **RLS deny-by-default**; the sponsor serializer
  stays an **allowlist**.
- **UI:** **Stitch-first** for S4 and S5 before coding templates.
- **British English; i18n parity en/ms/ta** (Tamil first-draft, queued for
  refine — especially any student-facing ticket copy).
- **Standardisation preserved:** identical four-fact verdict shape for every
  applicant.

---

## 7. Decisions (settled 2026-06-01)

1. **Income's green** — ✅ **AI asserts green only on a verified STR document;
   else it recommends and a human decides.** (See principle 2.)
2. **Address dial** — ✅ **Accept-as-noise; a ticket is raised only on *major*
   divergence** (a coherence/fraud signal). A drifting postcode gets no ticket.
3. **Fifth fact** — ✅ **No.** Stay at four facts (Identity / Academic / Income /
   Pathway); guardian consent and intent/fit stay **folded into** their rows.
4. **Sprint shape** — ✅ **Keep S3 (ticket backend) and S4 (student UI) split.**

---

## 8. Parked — fresh sprints (out of scope here)

Flagged 2026-06-01; triaged out of the verdict plan to keep the sprints clean.

1. **Documents box neatness** — *folded into Sprint 5* (not parked); the officer
   panel's Stitch redesign rebuilds the raw flat document list into a neat,
   professional evidence drawer.
2. **Referee-from-student (fresh sprint).** Today the referee is admin-only
   (coordinator records it at accept); the student never provides one. This is a
   **new intake field**, not a verification-synthesis change — it maps to none of
   the four facts, so it stays out of this plan. Small and independent. *May*
   later reuse the S4 Action-Centre pattern as a "please add a referee" ticket,
   but it stands alone. Scope it as its own short sprint after this roadmap.
```