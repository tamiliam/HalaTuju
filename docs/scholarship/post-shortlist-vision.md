# Post-Shortlist Vision — Interview-Driven Profile, Four User Types

**Status:** direction-setting (2026-05-29). Captures the product model agreed
in conversation; spec/sprints to follow.

> The interview must add value, not exist for its own sake.
> Two humans rating the same student differently is the real friction.

---

## 1. North star

The B40 programme's binding constraint is **human manpower** — volunteer
admins/coordinators who interview, vet, and standardise across hundreds of
applicants. The system's job is to:

1. **Surface what to ask** so interviewers don't start from a blank page.
2. **Standardise how it's captured** so two interviewers converge on the
   same answer for the same student.
3. **Compound interview findings into the sponsor profile** so the work
   the interviewer does ends up in the artefact the sponsor reads.

Every design call below is in service of those three goals. Where they
conflict with "more features" or "more flexibility," they win.

---

## 2. Four user types

| User | Status | Scope | Permissions |
|---|---|---|---|
| **Student** | ✅ Done | Apply, complete profile, see status, post-acceptance progress | Authenticated student session, own application + profile only |
| **Admin** | ⚠️ Done, needs role categories | Verify, interview, accept, manage | `PartnerAdmin` model exists; needs `role ∈ {super, reviewer, viewer}` + `assigned_to` FK on application |
| **Sponsor** | 🚧 To do | Read sponsored students' final profiles + ongoing progress | New auth scope, new entity; many-to-many to Student via `Sponsorship` |
| **Mentor** | 🚧 To do | Post-acceptance longitudinal touchpoints with mentee | New auth scope; one-to-one or one-to-few with Student via `Mentorship` |

**Admin role categories** (planned, not built):
- **super** — today's `super_admin` flag (manage admins, create cohorts, etc.)
- **reviewer** — verify-&-accept + interview + decision; the main workhorse role
- **viewer** — read-only access for board members / donor relations / observers

---

## 3. Funnel — application lifecycle

Current:
```
submitted → shortlisted → accepted | rejected | withdrawn
```

Target:
```
submitted
    └─→ shortlisted               (programmatic decision engine, S8)
            └─→ interview_scheduled   (admin assigns a reviewer)
                    └─→ interview_done    (findings captured)
                            └─→ accepted | rejected
                                    └─→ sponsored      (sponsor matched)
                                            └─→ in_programme   (active student)
                                                    └─→ completed | withdrew
```

The admin home is **a list of students at each stage** (a kanban-style
funnel), with the reviewer's own assignments highlighted.

---

## 4. Entity map (high level)

```
Student ─── ScholarshipApplication
                │
                ├── InterviewSession                          (new)
                │       ├── assigned_to → PartnerAdmin
                │       ├── findings   → per-flag structured + free notes
                │       └── completed_at
                │
                ├── Sponsorship          (new, M:N to Sponsor)
                │       ├── sponsor     → Sponsor
                │       ├── started_at
                │       └── ended_at
                │
                └── Mentorship           (new, M:N — usually 1:1 to Mentor)
                        ├── mentor      → Mentor
                        ├── started_at
                        └── ended_at

PartnerAdmin (extend):
    role ∈ {super, reviewer, viewer}
    + assignments back-relation through InterviewSession
```

---

## 5. The three-engine gap model

The interview agenda is assembled from **three independent gap-spotters**,
each playing to its strength:

| Engine | What it spots | Cost | Trust |
|---|---|---|---|
| **Deterministic rules** | "household_income RM 2k + receives_str=false" / "household_size=1 (unusual)" / "MyKad address ≠ entered address" / "declaration_name ≠ IC OCR name (partial)" / "aspirations mention medicine but chosen_pathway = poly" | Free (Python) | High — codable, reliable, no hallucination |
| **OCR / cross-doc** | Vision-derived flags from S13: NRIC/name/address mismatches between MyKad and profile data | Effectively free (already running) | High — verifiable against the photo |
| **Gemini narrative** | Story-arc inconsistencies, things-not-asked, contextual signals: *"Student's 'plans' mention helping their mother who is ill, but `siblings_studying = true` and family_context doesn't elaborate — worth asking how they balance both"* | ~$0.001 per applicant | Medium — useful but verify-against-rule baseline |

All three feed one **unified interview agenda** for the admin. Deterministic
flags don't depend on Gemini, so Gemini's occasional hallucinations stay
contained — the rule-based baseline always works.

---

## 6. Two-stage profile

```
Submit
   │
   ▼
 [Gemini v1] ──► sponsor_profile_draft
   +
 [deterministic gaps]
   +
 [Vision gaps]
   │
   ▼
 Unified interview agenda  ──►  Interview captures structured findings
                                          │
                                          ▼
                                  [Gemini v2: draft + findings → final]
                                          │
                                          ▼
                                  sponsor_profile_final ──► Sponsor sees this
```

The sponsor sees **only the final profile.** The draft + interview findings
stay admin-side (audit trail). Both are stored — we don't overwrite the draft.

---

## 7. Standardisation aid: structured capture from day one

**The interview form is mostly closed-ended per flag.** For each agenda item:

- Verdict: `resolved | still_unclear | new_concern_raised`
- One-line rationale (max ~140 chars)
- Optional free-text expand at the bottom of the whole form (not per flag)

**Optional rubric** (open design question — see §9): a small fixed set of
1-5 ratings the interviewer scores at the end (e.g. *clarity of plan /
demonstrated financial need / resilience signals*). Two interviewers rating
the same student on the same rubric is the classic inter-rater-reliability
fix. Without it, even structured per-flag answers can drift.

**The output schema is the standardisation.** "She seems sincere" is exactly
what we want to make impossible to enter.

---

## 8. Phased build

The order reverses from my first sketch — **interview capture lands before
Gemini gap-spotting** because the structured findings form is what unlocks
the Gemini v2 refine step.

| Phase | What | Why now / why later |
|---|---|---|
| ✅ **A. Deterministic anomaly engine** (1 sprint) — **DONE S16 (v2.8.0)** | Rule-based flag list shown on `/admin/scholarship/[id]` as "Pre-interview flags." Each flag has a static suggested question. No capture yet. | Cheap (no new Gemini calls). Validates flag usefulness before building capture infrastructure. Admin can mentally use it tomorrow. |
| ✅ **C. Admin role categories + InterviewSession + capture UI** (1-2 sprints) — **DONE Phase-C sprint (v2.15.0)** | New `role` on PartnerAdmin + `assigned_to` on Application. New `InterviewSession` model with structured `findings: JSONField`. Admin UI: list view filtered by "assigned to me" + per-application interview form. New status `interviewed` between `shortlisted` and `accepted`. | Biggest single piece. Worth building only after Phase A confirms the flags are useful. Form schema must lock the structured per-flag verdicts. |
| ✅ **B. Gemini-derived gaps** (1 sprint) — **DONE v2.17.0 (2026-05-31)** | Built as a *separate* admin-on-demand call (`gap_engine.py`, not folded into `_build_prompt`): reads the narrative → 3–6 `{code, question, why}` gaps, merged with deterministic flags into the unified findings-capture agenda keyed by `code`. | One extra call (kept separate from the sponsor-profile prompt so a gap run never re-bills the profile draft). The deterministic engine covers most of the value; gaps add the contextual story-arc questions. |
| **D. Gemini v2 refines with findings** (1 sprint) — **NEXT** | Second Gemini call: draft + structured findings → final profile. Sponsor sees v2 only. New `profile_finalised_at` field. | Adds ~$0.001/applicant. Real payoff — the interview work compounds into the sponsor artefact. |
| **E. Sponsor login + scope** (2 sprints) | New auth scope, `Sponsor` model, `Sponsorship` M:N. Sponsor sees their sponsored students' final profiles + progress. | Independent of A-D. Can run in parallel once the data model is set. |
| **F. Mentor login + scope** (1-2 sprints) | New auth scope, `Mentor` model, `Mentorship` M:N. Lightweight first — just touchpoint logging. | Lowest priority; only meaningful once students are in-programme. |

---

## 9. Open questions parked (no answer needed yet)

1. **Interviewer rubric**: do we add a small fixed-rating dimensions set
   (1-5 on N axes) alongside per-flag verdicts, for inter-rater reliability?
   Recommend yes; small (3-5 dimensions) and additive.
2. **Sponsor visibility**: does the sponsor see only the final profile, or
   also an interview-summary as evidence the profile is grounded? Default:
   final profile only; admin can choose to share an excerpt.
3. **Funnel UI shape**: kanban columns (visual) vs status-filtered list
   (cheap, lower-effort). Probably status-filtered list first; kanban later.
4. **Anomaly taxonomy seed**: 8-10 starting rules from the existing data
   model — draft when ready to spec Phase A.
5. **Mentor model timing**: build alongside or after sponsor scope? Probably
   after — mentor work only matters once students are in-programme.

---

## 10. What's already in place we'll build on

- **S11a** — admin verify-&-accept, `accepted` status, NRIC lock at verify, mentoring toggle. The capture UI for Phase C extends this page.
- **S13** — Vision OCR for MyKad. Already produces NRIC/name/address verdicts surfacing on the admin page; these become the OCR-gap input for the agenda.
- **S14** — `/profile` schema consolidation; required Address on /application. Cleaner data → cleaner deterministic rules.
- **S5c** — Gemini sponsor profile generator with language-aware prompts (`profile_engine.py`). The v1/v2 split extends this; same prompt builder, different inputs.

---

## 11. Bottom line

Build **Phase A first** (deterministic anomaly engine — 1 sprint, no new
Gemini calls). It validates whether the flags are useful with minimal
investment. Phase C (interview capture + admin roles) is the next big unlock
because the structured form is what makes Phase D (Gemini v2) work.

Sponsor + Mentor scopes are mostly independent surfaces; can run in parallel
once the core funnel is solid.
