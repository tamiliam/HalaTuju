# PF-1 — a new application is routed to a cohort chosen platform-wide

**Written 2026-07-28 as a handoff brief for another agent; the owner then reassigned it to the
author** — *"On second thought, I think you should implement PF-1."* Kept in handoff form on
purpose: it was written to be executed by someone with no memory of this conversation, which is the
right shape for a brief that may be picked up after a compaction, by a different session, or by a
different agent after all.
**Priority: highest queued work on this project.** Everything else — nav N3a, theming — is behind it.

> **Verify every claim below against the code before you build.** Line numbers are as at
> `b054af04` and will drift. Where this brief and the repository disagree, the repository is right,
> and please correct the brief in the same commit.

---

## 1. The defect

`apps/scholarship/services.py:188`

```python
def resolve_open_cohort(cohort_code=''):
    if cohort_code:
        return ScholarshipCohort.objects.filter(code=cohort_code).first()
    return (
        ScholarshipCohort.objects
        .filter(is_active=True, is_open=True)
        .order_by('-year', 'code')
        .first()
    )
```

There is no organisation in that query. It answers "which round is open **on this platform**", and
the caller uses the answer to decide which round a student joins — `apps/scholarship/views.py:153`,
`ApplicationListCreateView.post`.

**Nothing in the web app ever sends `cohort_code`.** Confirmed by grep: it appears only as a *read*
field on `ScholarshipApplication` (`halatuju-web/src/lib/api.ts:1374`) and on the admin type
(`admin-api.ts:480`). No caller sets it. So **every new application takes the default branch** and
lands in whichever open cohort happens to sort first by `-year, code`.

### Why it fails silently, and why that is the serious part

`ScholarshipApplication.save()` (`apps/scholarship/models.py` ~962–984) denormalises tenancy from
the cohort:

```python
needs_org = self.owning_organisation_id is None
...
self.owning_organisation_id = cached_cohort.owning_organisation_id
```

So the cohort chosen by that unscoped query **is** the tenant the application belongs to, stamped
at creation, with no error and nothing for anyone to notice. `owning_organisation` is the security
fence (`ScholarshipCohort.owning_organisation` docstring: *"SOURCE OF TRUTH for tenancy"*). A
student who applies to organisation B is filed under organisation A: visible to A's staff, invisible
to B's, and funded from A's money.

### Blast radius — there are TWO unscoped reads, not one

| Where | What it decides | Consequence with two tenants |
|---|---|---|
| `services.py:188` `resolve_open_cohort()` → `views.py:153` | which cohort a NEW application joins | wrong tenant, permanently, silently |
| `views.py:110` `IntakeStatusView` (**public**, `AllowAny`) | whether the landing page shows "Apply" | tenant A's open round makes tenant B's landing say applications are open, and vice versa |

`IntakeStatusView` runs the same `filter(is_active=True, is_open=True).order_by('-year','code')`
inline. **Fix both or you have moved the bug.** Check for further copies before you finish:
`grep -rn "is_open=True" --include=*.py .`

### Why it is dormant today, and why that expires

Every open-cohort row today belongs to BrightPath, and `is_open` is `false`. The moment a second
organisation has an open round, the bug is live. The owner confirmed on 2026-07-28 that the
**second-tenant meeting happened and looks credible**, which is what moved this off a
~May/June 2027 park.

---

## 2. The question this cannot be built without — ASK, do not choose

**How does the system know which organisation a student is applying to?**

A student has no organisation. They arrive, sign in with Google, and apply. There is no tenant in
their session, and there is nothing in the request today that carries one.

This is a **product** question, not an implementation detail, and it must go to the owner before
any routing is written. Three candidate answers:

| | Answer | What it needs | Honest assessment |
|---|---|---|---|
| **A** | **The apply link identifies the round.** Each organisation gets its own apply URL carrying a cohort or programme code; the front end passes it as `cohort_code`, which the serializer already accepts. | one FE change, one URL scheme, no new model | Smallest change; `cohort_code` already exists end-to-end for reads. Fails if a student lands on the bare `/apply` — which needs a defined behaviour, not a default. |
| **B** | **The student chooses** from the open rounds on the apply page. | a public "open rounds" endpoint + a picker | Honest and self-explanatory. Asks a 17-year-old to know which foundation they want, which they may not. |
| **C** | **The referral link decides** (`?ref=` / `referred_by_org`). | nothing new | **Almost certainly wrong, and do not quietly adopt it.** `ScholarshipCohort.owning_organisation`'s docstring is explicit: *"`PartnerAdmin.org` / `referred_by_org` mean the REFERRING org (attribution), never ownership/access control."* A school referring a student is not the foundation funding them. |

**My recommendation to put to the owner: A, with B as the fallback for a bare `/apply`.** But it is
a recommendation, not a decision — take the answer before building the routing half.

---

## 3. What to build

**Split it. The safety half does not depend on the product answer and should ship first.**

### P1 — fail closed when the answer is ambiguous (ship this first, on its own)

Make the platform-wide guess impossible rather than merely wrong.

- `resolve_open_cohort()` stops returning "the first of several". When **more than one** active+open
  cohort exists and no explicit code was given, it must **refuse** — return `None`, or raise a
  dedicated error the view turns into a clear 409. A student seeing "we could not tell which
  programme you are applying to" is a support message; being filed under the wrong foundation is a
  refund and an apology.
- The single-open-cohort case keeps working **exactly** as today. Today's behaviour must not change
  at all while one tenant has an open round — that is what makes P1 safe to ship immediately.
- `IntakeStatusView` gets the same treatment, or an explicit decision about what "open" means with
  no tenant context. Do not leave it reading the platform.
- An explicit `cohort_code` must still be validated against `is_open` — `views.py:159` already
  re-checks this and the comment explains why; keep that guard.

### P2 — the real routing (needs the §2 answer first)

Once the owner has answered, thread the organisation or programme through the apply flow and make
`resolve_open_cohort` take it as a **required** argument.

> **Make it required, with no default.** This repo has the lesson written down from
> `sponsor_balance` (Platform P2a, `docs/lessons.md`): a new scoping dimension added as
> `param=None` compiles, passes every existing test, and silently produces the pooled/wrong answer
> at every call site nobody updated. Required-and-no-default converts the same mistake into an
> immediate `TypeError` — a complete, mechanical worklist.

---

## 4. Tests that must exist

The bug's whole character is that it is **silent**, so the tests are the deliverable.

1. **Two organisations, both with an open cohort, no `cohort_code`** → the request does NOT create
   an application under an arbitrary organisation. This test must FAIL against today's code; run it
   before your fix and confirm it fails, or you have not reproduced the bug.
2. **One open cohort** → unchanged behaviour, application created, `owning_organisation` correct.
   This is the regression guard on P1's promise that nothing changes today.
3. **The tenancy stamp** — extend `apps/scholarship/tests/test_application_owning_org.py`, which
   already asserts `app.owning_organisation_id` follows the cohort.
4. **`IntakeStatusView` with two tenants open** — assert whatever the decided semantics are, rather
   than "an open cohort exists somewhere".
5. **A `cohort_code` naming another organisation's open cohort.** Decide deliberately whether that
   is allowed; today it silently is. Whichever way, pin it.

---

## 5. Rails — the ones that fail CI or production if missed

- **Any new `_AdminBase` endpoint must be classified** in `FENCED_OR_EXEMPT`
  (`apps/scholarship/tests/test_org_fence.py:194`), or `test_every_admin_endpoint_is_classified`
  fails by design. A public/`AllowAny` endpoint is not in that set — do not add one there to silence
  anything.
- **Migrations are migrate-first on this project** (see `halatuju_api/CLAUDE.md`): hand-written DDL
  applied via MCP and verified against production *before* the code that needs it deploys. A new
  table also needs RLS enabled **and** the single `Backend service role only` policy every sibling
  table has, or it lands in the Supabase advisor as `rls_enabled_no_policy`. This work may well need
  **no migration at all** — check before assuming either way.
- **Scholarship models use custom `db_table`** (`scholarship_applications`, not the Django default).
  Read `Meta.db_table` before writing any raw SQL.
- **State the scope of any test count you quote.** `pytest apps/scholarship` is ~3,6xx; the full
  suite is **4882** as at 2026-07-28. Quoting the subset as the total has already caused one
  incorrect record.
- **`resolve_open_cohort` is imported at `views.py:50`.** Check for other importers before changing
  its signature.

---

## 6. Out of scope

- Retro-fixing existing applications. Every one belongs to BrightPath and is correct. If P2 changes
  how tenancy is derived, **verify** that the existing rows still agree — do not rewrite them.
- The nav switchers (N3a), theming, and anything on the console. This sprint is the apply path.
- Do not "fix" this by making `owning_organisation` non-nullable. It is nullable for
  additive-migration safety and migration `0098` seeded it; that is deliberate.

---

## 7. Definition of done

- [ ] A test that fails on today's code and passes on the fix (see §4.1).
- [ ] Both unscoped reads addressed — `services.py:188` and `views.py:110`.
- [ ] Full suite green; state what you ran and its scope.
- [ ] `docs/technical-debt.md` — PF-1 marked resolved with the commit; `halatuju_api/CLAUDE.md`
      Next Sprint banner (currently a 🚨 for this) updated to match reality.
- [ ] Sprint close per `Settings/_workflows/sprint-close.md`.

---

## 8. Working alongside another agent

If a second agent is active on this repo, use a git worktree
(`Settings/_workflows/parallel-work-isolation.md`) or stage explicit paths — **never** `git add -A`
on a shared tree. The sponsor agent was last seen merged at `a89d04cd`; check `git worktree list`
and `git log origin/main..HEAD` before assuming you are alone.

`main` was clean at `b054af04` when this was written, everything pushed, and
`halatuju-web-00733-zpl` live.
