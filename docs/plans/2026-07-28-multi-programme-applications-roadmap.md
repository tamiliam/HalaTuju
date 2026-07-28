# Multi-programme applications — roadmap

**Drafted 2026-07-28** per `Settings/_workflows/implementation-planning.md`.

> **▶ OWNER DECISION 2026-07-28: M1 ONLY IS APPROVED.** *"M1 only for now."*
>
> **M2–M4 are NOT approved and must not be started.** They are kept below because M1 is only
> worth doing if this is where it leads, and because the owner's rulings and scenarios are
> recorded against them — not as a commitment to build them.
>
> **Why this is a sound place to stop.** M1 closes the silent-misattribution risk on its own and
> changes nothing a student sees. It is the only piece that is dangerous to leave undone: the
> others are absent features, whereas this one is a wrong answer waiting for a second programme.
> **Re-plan M2–M4 when a second programme is actually close** — the scenarios will have moved.

Follows PF-1, which stopped the platform guessing which programme an application was FOR. This
roadmap is the other half: letting a student hold applications to more than one programme, which
the owner has now asked for.

---

## The requirement, in the owner's words (2026-07-28)

> *"Each programme would have its own requirements and selection criteria. So, students should be
> free to apply to whichever they want, and the system should be able to handle them."*

**Two scenarios given, and they want different behaviour — this is the crux of the design:**

| | Scenario | Behaviour |
|---|---|---|
| **1** | *"Student goes to Inspire. In their website they provide an application link. Through that they should come to halatuju and register/login."* | **They must NOT see other programmes.** *"Which may confuse."* Single-programme tunnel, and the context has to survive **registration and login**. |
| **2** | *"Student lands in HalaTuju course selection. Clicks on student aid. Sees two scholarship programmes active. Believes she qualifies for both and applies to both, one at a time."* | **Browse, choose, and then hold two.** *"Here the picker might be useful, if she has two live applications."* |
| **3** | *"Student from Scenario 1 who has already submitted application but comes to halatuju. She clicks on the student aid menu, and see two programmes listed. She picks the one that is relevant to her and proceeds."* | **The tunnel is per-visit, not permanent.** Having arrived once through Inspire's link does not brand her account; browsing organically later, she sees everything that is open. |

**Scenario 3 is the one that shapes the surface**, and it retires a reading of scenario 1 that would
otherwise have been built. The single-programme tunnel is a property of **how she arrived this
time**, not a flag on her account — so:

- the listing must be **application-aware**: a programme she already has a live application with
  reads *"Continue your application"*, one she does not reads *"Apply"*;
- **the picker and the switcher are the same surface.** M4 had them as two things. They are one
  list, with each row in one of two states — which is simpler, and is why scenario 3 is worth
  having before M3/M4 are built rather than after.

⚠ **One ambiguity, deliberately not resolved here.** *"Picks the one that is relevant to her and
proceeds"* reads either as *continues the application she already holds* or as *applies to the
other one*. The list above serves both without choosing, which is why it is safe to defer — but
whoever builds M3/M4 should confirm rather than assume.

Read scenario 2 carefully: the picker is wanted **once she has two live applications**, not only at
the moment of choosing. It is a *switcher* as much as a chooser.

## Owner rulings taken the same day

1. **Documents belong to the APPLICATION.** If they should ever follow the student instead, the
   right design is *"the student uploads into their profile, which they may call into the
   application"* — a profile-level document library, referenced by applications. **Not this
   roadmap**; recorded so nobody invents a different sharing mechanism.
2. **A student may hold two offers**, *"if there are no restriction on the part of the organisation
   or programme. It is for them to discover."* → the platform does **not** enforce cross-programme
   exclusivity. Do not build one.
3. **Applying to B changes nothing for A** — no notification, no visibility. ⚠ **This is a fence
   requirement, not just a UX one:** organisation A must not be able to see that the student also
   applied to Inspire. Every admin surface needs checking against it.

---

## What already works, and what does not

**Already works — per-programme criteria.** The decision engine reads its thresholds off the
cohort: `cohort.income_ceiling`, `per_capita_ceiling`, `min_stpm_pngk`, the academic floor
(`shortlisting.py:90-103`). Each programme's intake carries its own. So *"each programme would have
its own requirements and selection criteria"* is largely a **data** exercise. This is the pleasant
surprise in the whole plan.

**Does not work — "which application?" is answered by POSITION, in three places.** All the same
shape as PF-1, which is why this roadmap exists at all:

| # | Where | What it does | Blast radius |
|---|---|---|---|
| 1 | `services.resolve_open_cohort()` | ~~`.first()` over open cohorts~~ | **FIXED — PF-1, 2026-07-28** |
| 2 | `views._current_application()` | `.order_by('-submitted_at').first()`; the docstring says *"latest wins"* as though it were a rule | **14 call sites** in `views.py` — document sign-upload, document list, consent, bank details, Action Centre |
| 3 | `app/scholarship/application/page.tsx:45` | `res.applications[0] ?? null` | the student's whole application screen |

**The database already permits two applications.** The unique constraint is
`(cohort, profile)` — two cohorts is two rows, allowed today. Nothing structural prevents it; it
simply has never happened, because one cohort has ever existed.

**So the failure is live the day a second programme opens:** a student uploads their IC for
programme B and it attaches to whichever application they submitted most recently. Silently. Same
for consent, bank details and every Action Centre task.

⚠ **This is why the picker cannot come first.** A picker on top of "latest wins" would *invite*
students into the one thing the system mishandles. Today a stray student meets an honest refusal;
afterwards they would get a quietly broken application. **The router before the viewer** — the same
sequencing argument that put PF-1 ahead of N3a.

---

## Sprints

Four, sequenced by hard dependency first and risk second. **M1 is both.**

### M1 — "which application" stops being positional  ·  complexity: HIGH

**Goal.** No endpoint or screen ever infers which application a request is about. Where it cannot
be determined, it refuses — the PF-1 discipline, one layer up.

**Scope.** `views._current_application()` and its 14 call sites; `ApplicationReadSerializer`
consumers; `app/scholarship/application/page.tsx`; a shared resolver mirroring
`resolve_open_cohort`'s shape (explicit id wins → single live application → refuse).

**Acceptance.**
- A test creating two live applications proves each affected endpoint mis-attributes **today**, and
  refuses or resolves correctly after.
- **With ONE live application, behaviour is byte-identical** — proven by the existing suite passing
  unmodified, not by new tests.
- No screen shows "your application" without being able to say which.

**Risk.** This touches live student paths for real applicants mid-funnel. It is the reason this
sprint is alone and first.

### M2 — a student can hold two applications, end to end  ·  complexity: MEDIUM

**Goal.** Two live applications behave as two independent cases: their own documents, consent,
verdict, interview and outcome.

**Scope.** Consent per application; award/offer per application (two offers permitted — owner
ruling 2); the Action Centre scoped to a named application; `_FUNDED_STATES` / post-award flows.
**Plus the fence audit for ruling 3** — no admin surface may reveal a student's applications to
another organisation.

**Acceptance.** A student applies to two programmes, uploads to each, and reaches two independent
outcomes. An org_admin at A sees no trace of B. A test pins the fence.

### M3 — the two entry contexts  ·  complexity: MEDIUM

**Goal.** Scenario 1 and scenario 2 both behave as described.

**Scope.** `?p=<programme>` becomes a **tunnel**: while it is in force, no other programme is shown
anywhere in the flow — and it must **survive registration and login** (it currently lives in
`sessionStorage`; the OAuth round trip needs proving, not assuming). Without it, `/scholarship`
lists the open programmes (scenario 2's "student aid" surface).

**Acceptance.** Arriving via Inspire's link and registering shows Inspire only, start to finish.
Arriving organically lists what is open. A test covers the login round trip.

### M4 — the picker and the switcher  ·  complexity: LOW–MEDIUM

**Goal.** The stray student is served, and a student holding two applications can move between them.

**Scope.** The picker at a bare `/apply` with more than one round open (**TD-189**); an application
switcher wherever "your application" is shown; honest copy for a link naming a **closed** programme.

**Acceptance.** A bare `/apply` with two open rounds offers a choice rather than a refusal. A
student with two live applications can switch, and always knows which they are looking at.

**Open design question for M4** (raised, not decided): a student follows A's link but A has closed
while B is open. Offer B, or stop at "A is closed"? My recommendation is to stop, with an explicit
opt-in link to what else is open — never an automatic redirect, which would nudge a student toward
a foundation they did not come for.

---

## Sequencing rationale

M1 is a hard dependency for everything and carries all the risk. M2 makes two applications real but
invisible. M3 and M4 are the surfaces, and they are last on purpose — **the visible half is the half
that invites the behaviour, so it must not arrive before the machinery is sound.**

M4 could merge into M3, and would be tight but defensible if fewer handoffs are wanted.

**Prerequisite for testing all four:** a second `Programme` + open cohort in fixtures. Cheap, and
M1's tests need it anyway.

## What this roadmap does NOT cover

- **Profile-level document library** (owner ruling 1's alternative design). Its own thing, if wanted.
- **Cross-programme exclusivity rules.** Owner ruling 2: the platform permits; organisations decide.
- **Moving rule tunables from cohort to programme.** Already flagged in the `Programme` docstring as
  behaviour-sensitive and deliberately deferred. Per-cohort thresholds already give per-programme
  criteria.
- **Sprint E (erasure) and the DPA.** Still hard-blocking any real second-tenant applicant data, and
  neither is engineering.
