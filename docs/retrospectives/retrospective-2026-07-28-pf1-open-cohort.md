# Retrospective — PF-1: the platform stops guessing which programme a student applied to

**Date:** 2026-07-28 · **Commits:** `4008d362` (P1, the refusal), `f7f652ef` (P2, the apply link)
**Brief:** `docs/plans/2026-07-28-pf1-open-cohort-org-context.md`
**Migration:** none. **New dependency:** none.

---

## What Was Built

`resolve_open_cohort()` answered *"the most recent active+open cohort"* with `.first()` over an
unscoped queryset. That is a **platform-wide** question, and the caller used the answer to decide
which round a student **joins** — while `ScholarshipApplication.save()` denormalises
`owning_organisation` from it. With two organisations open, a student applying to B was filed
under A: visible to A's staff, invisible to B's, funded from A's money, **and no error anywhere**.

`.first()` over an unscoped set is not a tie-break. It is a guess about tenancy.

**P1 — the refusal.** It now raises `AmbiguousOpenCohort`. The apply path returns
`409 programme_required` and logs at ERROR. **Both** unscoped reads were closed: `IntakeStatusView`
ran its own copy of the same query, so fixing only the apply path would have moved the bug rather
than closed it.

**P2 — the routing.** Each organisation gets its own apply link, `/scholarship/apply?p=<programme>`,
the owner's answer to the question P1 deliberately left open.

**Numbers:** `pytest` **4947** (scholarship + courses + reports — full scope) · `jest` **997** / 65
suites · i18n **4149 × 3** · `next build` compiled · **9 files, no migration**. The baselines moved
because sponsor S3 merged mid-sprint; this sprint's delta is **25 backend + 6 frontend** tests.

---

## What Went Well

- **The brief was written to be executed by a stranger, and then a stranger executed it** — me, two
  hours and one context compaction later. Everything load-bearing survived because it was in the
  file rather than in the conversation: that there were TWO unscoped reads, that nothing sends
  `cohort_code`, and that `referred_by_org` is the wrong answer and why.
- **Checking the brief's claims against production found something the brief had wrong.**
  It said the bug was dormant because one organisation exists. There are **ten**, of which nine are
  referral organisations and only BrightPath owns anything. Dormancy is real but for a different
  reason, and the same query invalidated a trigger I had written into four documents an hour
  earlier (see below).
- **The reproduction came first and it failed for the right reason.** `201 != 409` — the endpoint
  creating a wrong-tenant row. A test that fails because of a missing import proves nothing; that
  one had to be checked, and it was worth the extra run.
- **Splitting the sprint let the safety half ship without waiting on a product decision.** P1 makes
  the guess impossible while leaving today's behaviour byte-identical — proven not by a new test
  but by **3,662 existing tests not moving**.

---

## What Went Wrong

**1. I wrote a trigger into four durable documents that had already fired.**
*Symptom:* the N3a parking decision said "build the switchers when more than one active
`PartnerOrganisation` exists". Production has had ten for months.
*Root cause:* I reasoned from the model — `PartnerOrganisation` is described as the tenant fence,
so more than one row reads as more than one tenant. The table actually holds **both** funders and
referrers with no flag between them, which the model's own docstrings say and I had even quoted at
the sponsor agent the same day. I inferred the data's shape from the schema instead of looking.
*System change:* corrected in the roadmap, `decisions.md`, memory and Mission Control, each keeping
the wrong version visible as a correction rather than a silent edit. The habit: **a trigger is a
claim about data — run the query before writing it down.** One `SELECT` would have caught it.

**2. A docstring edit landed outside the docstring and broke the module.**
*Symptom:* `SyntaxError: invalid character '—'`, every test in the file erroring at import.
*Root cause:* I anchored a replacement on `permission_classes = [AllowAny]` and prepended prose plus
a closing `"""`, forgetting the docstring already had one. Two closers, so the prose became code.
*System change:* caught in seconds because the tests ran immediately. The lesson is narrower than
"be careful": when adding to an existing docstring, anchor on **text inside it**, never on the code
that follows it.

**3. The worktree had no `node_modules`, and I found out at the first frontend test.**
*Symptom:* `Module ts-jest ... not found`.
*Root cause:* a git worktree shares history, not build artefacts, and I created it knowing the
sprint was "backend-only" — which stopped being true the moment the owner chose the apply-link
answer.
*System change:* a PowerShell junction to the main checkout's `node_modules` (seconds, no disk).
Worth knowing before the next worktree sprint that touches the web app.

---

## Design Decisions

Logged in `docs/decisions.md` (2026-07-28):

1. **Refuse rather than guess**, and count ambiguity across ALL open rounds rather than per
   organisation — two intakes of the *same* organisation is the identical defect.
2. **The apply link carries the PROGRAMME, not the cohort** — a cohort code is year-specific and
   would rot every intake.
3. **`programme_code` is optional**, deliberately departing from the standing "make a new scoping
   dimension required" lesson, with the reasoning written into the docstring.
4. **An unknown programme reads "closed", not 404** — the endpoint is public, and the difference
   would let anyone enumerate the platform's tenants.

---

## Numbers

| | Before | After |
|---|---|---|
| Unscoped platform-wide cohort reads | **2** | **0** |
| Applications filable under an arbitrary organisation | all of them | none |
| pytest (full scope) | 4922 | **4947** |
| jest | 991 | **997** |
| Migrations | — | **0** |

---

## Carried Forward

- **▶ TD-189 — no programme picker on a bare `/apply`.** The owner named it as the fallback; it is
  not built, because it needs a public list of every organisation's programme names and that
  disclosure has not been agreed. Triggered the moment a second programme opens.
- **▶ Owner, when tenant #2 gets an open programme:** give them
  `/scholarship/apply?p=<their programme code>`. BrightPath's is `brightpath-flagship`. Until then
  the bare link keeps working exactly as today.
- **▶ Still ahead of everything else:** **Sprint E** (erasure) is hard-blocking before any real
  second-tenant applicant data, and **no entity can sign a DPA** — BrightPath's CLBG is unregistered
  and HalaTuju is org-homeless. Neither is an engineering gate; neither is closed. **PF-1 was the
  engineering half of "are we ready for a second tenant". These are the other half.**
- **▶ Themes** are next by the owner's sequencing, across admin, sponsor and student surfaces, with
  their own planning exercise.
- **TD-182** (admin sign-in on a local origin) still unfixed; **TD-188** — four consecutive sprints
  have now closed without a browser pass.
