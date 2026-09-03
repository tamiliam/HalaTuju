# Sabah S2 — a gift programme can be created without an engineer

**2026-09-03. web + api. Migration `0148`, applied migrate-first and verified before the push.**
Built in two halves on one branch: **S2a** the engine, **S2b** the endpoints and screens.
pytest **5790** (full suite, +26); jest **1631** (+8); tsc **24** (baseline); lint **0**;
i18n 4648 → **4714 × 3**; build clean. **Five guards bite-checked.**

**LIVE:** `halatuju-web-00820-r2r` / `halatuju-api-00972-jrg`. Both triggers fired (Python changed).
Intake still `{"open":false}` — the deploy opened nothing.

---

## The point

The owner's acceptance test, verbatim: *"Suresh, as org admin you may start the new programme, and
you can do everything on your own without any work from me."*

Before this, neither a `Programme` nor a `ScholarshipCohort` could be created anywhere — no
endpoint, no screen, and `scholarship` registers no models in Django admin either. A second gift
meant an engineer writing SQL.

---

## ▶ A SETTING WITH NO "WE DO NOT USE THIS" IS A REQUIREMENT EVERYBODY HAS

Every shortlisting threshold was `NOT NULL` with a default, so every test always ran.

**BrightPath never asked for an STPM requirement.** A PNGK floor of 2.90 was applied to all nine of
its STPM applicants for an entire intake regardless. It rejected none of them — every one scored
3.41 to 4.00 — so nobody ever found out. The defect was real, live, and completely invisible, and
the next programme would have inherited it.

`None` now means the test is not applied.

## ▶ THE VALUE **IS** THE SWITCH

The obvious shape was `use_stpm_floor` + `min_stpm_pngk`. Two columns can disagree — on-but-blank,
off-but-4 — and then something has to decide which wins, silently, in whichever module was written
last. One nullable column cannot contradict itself. Ticking writes a value; unticking clears one.

**Prefer a representation in which the invalid states cannot be spelled** over one that needs a
rule to keep two fields in step.

## ▶ THE MERIT RULE COULD HAVE BEEN ONE IMPORT, AND THAT WOULD HAVE BEEN THE BUG

`serializers_admin._application_merit_score` already computes a 0–100 merit. Reusing it would have
been one line. Its own docstring forbids it: it keys on `held_qualification`, whose comment reads
**"⚠ NOT A GATE, AND MUST NOT BECOME ONE"** — widening it re-bands live applicants, and the note
names the awarded record it would have re-based.

So `shortlisting.spm_merit` keys on `exam_type`, like every other test in the engine. The
arithmetic is shared (`courses.engine`); the qualification question is not, because it is a
different question. **Two callers wanting the same number for different reasons is not duplication
to eliminate — collapsing them is how a display heuristic becomes a decision.**

Merit applies to **SPM applicants only**: an STPM applicant's comparable figure is the PNGK, and a
0–100 floor against a 0–4 CGPA would reject everyone who sat STPM.

---

## What the screens refuse, and why each refusal exists

| Refusal | Because |
|---|---|
| A new gift is created **inactive**, whatever the client sends | An active second programme changes live behaviour the instant it exists — S1's payment-run picker appears, and the configuration screen starts asking which programme |
| A new intake year is created **closed** | `is_open` defaults to TRUE on the model. A plain create-form would let real students in with the same press |
| **One open round per organisation** | `resolve_open_cohort` already RAISES on two — but that refusal reaches the STUDENT at Apply. This one reaches the ADMIN at the moment they create the ambiguity, which is where it can still be undone |
| A gift **taking applications** cannot be switched off | The apply link would stop resolving while a half-finished application still points at it |
| A cohort's organisation is **derived, never asked** | An application denormalises `owning_organisation` from its cohort; one carrying a programme and not an org files students under the wrong fence (TD-177 is exactly this, in a fixture) |

---

## ▶ THE PROJECT'S OWN GUARDS CAUGHT ME TWICE, WHICH IS THE POINT OF THEM

- **The org-fence completeness map** failed on all five new `_AdminBase` classes. Classified with
  reasons, not silenced.
- **The raw-query static guard** failed on two `ScholarshipApplication.objects` counts. Both are
  safe — the programme was pre-fenced — and now say so in an `# org-fence:` pragma. ⚠ The pragma
  must sit within **200 characters** of the query; my first one was a three-line explanation above
  it and the guard still failed, correctly, because it could not see it.
- **The role matrix** in `navigation.test.ts` is literal by design and failed on the new nav item.
  That is a permission change and it should take a deliberate edit.

## ▶ I REPORTED THE TEST COUNT FROM TWO APP DIRECTORIES, NOT THE SUITE

Every number I gave during the sprint — "5716 → 5742" — came from
`pytest apps/scholarship/tests apps/courses/tests`, the two directories I was working in. The full
suite is **5790**. The delta was right (+26); the base was a subset, so the figure understated the
project by 48 tests and would have been copied forward into the registry.

Caught by sprint-close step 10, which says in as many words: *run the full suite across ALL test
directories and record the combined total, not just one component.* **A number is only a baseline
if it was measured the same way last time** — and a scoped command is the easy way to produce two
figures that look comparable and are not.

## ▶ AND ONE I CAUGHT BEFORE THE BUILD DID

`draftToRequirements` started life exported from `page.tsx`. F7c proved three times that a page
module may carry **no export beyond its default**, and that `tsc`, `jest` and `next lint` are all
green while it is broken. Moved to `lib/intakeYears.ts` before running the build. **A lesson is
only learned when it changes what you do the first time, not what you fix the second.**

---

## For S3 and S4

- **S3 — the Rules screen** is now mostly a second view of what S2b already writes: the same six
  columns, edited on an intake that already exists. The hard half (making a requirement optional)
  is done.
- **S4 — accepting a sponsor into a gift** still blocks the RM100,000:
  `sync_account_membership` hard-codes `DEFAULT_PROGRAMME_CODE = 'brightpath-flagship'`, and
  `record_admin_credit` refuses `sponsor_not_in_programme`.
- **Not built, deliberately:** the B+ requirement is stored as a TOTAL and shown as an EXTRA. If a
  future screen ever sends what it displays, "4 plus 1" silently becomes "4 plus 1 more than 4".
  `lib/intakeYears.ts` exists to hold that conversion in one place, with the test that pins it.
