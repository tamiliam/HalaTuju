# Nav/IA roadmap — the partner console shell (3 sprints)

**Owner-approved 2026-07-27.** Design of record:
<https://claude.ai/code/artifact/17d259a8-f15f-4f0a-858e-492f1cb157a6> (interactive mock-up; switch
role and sidebar model in the controls).

---

## Context

The console's navigation was a flat top bar built from a hardcoded chain of role checks in
`admin/layout.tsx` — no sub-items, no grouping, no notion of scope. Three consequences:

1. **A third of the console had no menu home.** Payments, Contracts, Sources, Sponsors, Requests and
   Billing existed only as tiles inside `/admin/administration`, and `isActive` special-cased three
   of them and forgot three, so `/admin/requests`, `/admin/sources` and `/admin/billing` highlighted
   nothing.
2. **Role logic was re-derived 17 times** across the layout and the admin pages.
3. **The Programme layer had nowhere to land.** The backend hierarchy Platform → Organisation →
   Programme → Year shipped 2026-07-26 (`scholarship.Programme`, 143/143 applications carrying it)
   and nothing in the web app read it. The menu still said "Administration" for two different levels.

Scheduled by `docs/plans/2026-07-26-programme-layer-roadmap.md:353` — *"nav/IA shell (organisation
switcher, Administration as a section with sub-navigation)"* — with risk #6: *"The nav shell ships
empty slots; each extraction sprint fills one — no second redesign."*

**Outcome:** a three-zone shell on Supabase's organisation → project model. Breadcrumb names the
scope you are in; sidebar lists what lives there, grouped by scope; top-right holds what is yours
rather than any scope's.

---

## Decisions taken (owner, 2026-07-27)

| # | Decision |
|---|---|
| 1 | **Sidebar model A — scope stack.** Every scope you can reach renders as a collapsible group, all visible at once. |
| 2 | **Three sprints** (N1 / N2 / N3), each independently shippable, each under the ~40-file cap. |
| 3 | **The bell aggregates counts the console already fetches.** No notification model, no migration. Internal messages deferred. |
| 4 | **Search ships navigation-only.** Record search needs a fenced endpoint — a later sprint. |
| 5 | **The org switcher is plain text when there is one organisation.** A real dropdown only for super on the platform deployment. |
| 6 | **`/admin/administration` becomes the Organisation overview** — same URL through N2, redirect at N3. |
| 7 | **Three role corrections:** finance loses the greyed Billing tile it would be 403'd on (gains the programme Fund slot); Admin-General loses the Contracts tile it cannot open; the referral partner's two pages get an honest "HalaTuju / Platform" heading. No capability changes — only what is shown. |

---

## The scope model

| Scope | Is | Holds |
|---|---|---|
| **Platform — "HalaTuju"** | the base everyone stands on | Overview, Students directory, Course data, Organisations, Referral partners, Billing rates |
| **Organisation — the security fence** | branding, staff, money; one org never sees another | Overview, Staff, Sponsors, Payments, Contracts, Sources, Billing & usage, Requests |
| **Programme — the gift itself** | the offering; never lapses | Overview, Applications, Reviewers, Intake years, Fund, Rules |

Grounding: `PartnerOrganisation` is the fence (`apps/courses/models.py:397`); `Programme.organisation`
narrows *inside* that wall and is explicitly **not** a second boundary
(`apps/scholarship/models.py:33`). Billing is per-organisation — there is no per-programme billing
anywhere in the codebase or roadmap.

---

## ✅ N1 — registry + predicate — SHIPPED 2026-07-27

Commit `20d683b4`, build `39732b6` SUCCESS both services. Retrospective
`docs/retrospective-2026-07-27-nav-registry-n1.md`; decisions ×3; lessons ×4.

`src/lib/navigation.ts` + `navigation.test.ts` (61 tests); `effectiveRole()` replaced 17 copies of
the role normalisation; the ternary and `isActive` deleted; the three unhighlighted routes fixed.
Zero visual change, pinned by a test encoding the pre-sprint bar. **TD-181** tracks the transitional
fields (`chrome`, `hubParent`, `LEGACY_BAR_ORDER`) that N2 deletes.

---

## ✅ N2 — the shell — SHIPPED 2026-07-28

Commit `e07f8f2e`. Retrospective `docs/retrospective-2026-07-28-nav-shell-n2.md`; decisions ×2;
lessons ×4.

`AppShell` + `Sidebar` + `Topbar` + `Menu` + `CommandPalette` + `useNavProbes` + a single-colour
`icons` set; `admin/layout.tsx` reduced to a guard (220 → 60 lines); nine reserved slots added;
**TD-181 closed** (`chrome` / `hubParent` / `LEGACY_BAR_ORDER` deleted, every page now highlights
itself); `manualRole()` delegates the super rule to `effectiveRole`. Reviewed in a browser against
the approved design before merge. 890 jest, i18n 4057 ×3, no backend, no migration, no new
dependency.

**Carried into N3:** TD-182 — admin Google sign-in fails on a local dev origin (PKCE code never
exchanged; works in production). Production auth code, so it owes its own commit and test.

## ✅ N3b — the route split — SHIPPED 2026-07-28

Commit `e38e5eac`. Retro `docs/retrospective-2026-07-28-hub-split-n3b.md`; decisions ×2; lessons ×3.
The 414-line hub became four pages plus a permanent redirect, on a shared `StaffAdmin` module;
Manual + FAQ updated in the same commit. 905 jest, i18n 4065 ×3.

**Owner tasks:** re-capture the Manual screenshots (prose correct, images stale); review the ms/ta
first drafts.

---

> ## ⚠ ESCALATION — READ BEFORE SCHEDULING ANY MORE NAVIGATION WORK (2026-07-28)
>
> The owner confirmed the **second-tenant meeting happened and looks credible**. Two things that
> were safely parked are now live risks, and BOTH outrank the rest of this roadmap:
>
> **1. PF-1 — silent cross-tenant misrouting.** `services.resolve_open_cohort()` returns the most
> recent active+open cohort **platform-wide, with no organisation context**
> (`apps/scholarship/services.py`). Today that is harmless only because `is_open=false`. The moment
> a second organisation has an open programme, a student applying is routed into the WRONG
> organisation's fence — and it fails silently, with no error, on the path that decides whose money
> pays for them. It is date-parked to ~May/June 2027 on the assumption that tenant #2 was
> hypothetical. That assumption no longer holds. **Fix it before tenant #2 has an open programme,
> not after.**
>
> **2. Sprint E (erasure) is hard-blocking** before any real applicant data from a second tenant,
> and separately **no entity can sign a DPA** — BrightPath's CLBG is unregistered and HalaTuju is
> org-homeless. Neither is an engineering gate; neither is closed.
>
> Navigation is now the least urgent thing on this list. N3a is worth doing — it is the switcher a
> second organisation needs — but it should not go ahead of PF-1.

## ▶ N3a — scopes endpoint + switchers — STILL OWED

Order was inverted deliberately (owner, 2026-07-28): N3b turned four greyed slots into working
pages, which was visible value, while the switchers show one entry until a second organisation
exists. **That calculus has changed** — the owner confirmed the second-tenant meeting happened and
looks credible, so N3a is no longer anticipatory. See the escalation note below before scheduling
it, because something outranks it.

### N3a spec — what is left of it

**Backend — one new endpoint:** `GET /api/v1/admin/scholarship/scopes/` → `AdminScopeListView(_AdminBase)`.

```json
{ "organisations": [{"id":1,"code":"brightpath","name":"BrightPath"}],
  "programmes":    [{"id":1,"code":"brightpath-flagship","name":"BrightPath Bursary","organisation_id":1}] }
```

- `super` → all active orgs + all active programmes.
- everyone else → exactly `admin.owning_organisation` (empty when NULL) + that org's active programmes.
- `partner` → `{"organisations": [], "programmes": []}`. A referral org is **never** an access scope.
- Names resolve trilingually with the en-fallback convention in `apps/scholarship/branding.py`.

**⚠ CI gate — skipping this fails the suite.** `apps/scholarship/tests/test_org_fence.py`
`FENCED_OR_EXEMPT` must gain an `'AdminScopeListView'` entry, or
`test_every_admin_endpoint_is_classified` fails. Add an isolation case to `TestOrgFenceProof` plus a
new `test_admin_scopes.py` (super sees both tenants; org_admin sees one; partner sees none; inactive
programme excluded; NULL-owning-org reviewer gets empty lists, not a 500).

**The switcher must never become an ambient auth context.** No global header, no cookie, no
middleware rewrite — that would relocate the fence into the client. For super it persists a
client-side *display* preference only. Say this in the component docstring.

**The route split that used to be specified here shipped as N3b on 2026-07-28** — four pages plus a
permanent redirect, and every other URL kept. Nothing of it is outstanding.

**Manual/FAQ currency rule still applies** (`docs/scholarship/role-matrix.md`): a change to what a
role sees updates that role's Manual chapter and FAQ entries in the same commit. N3b is the evidence
that it earns its keep — rewriting the "Administration" mentions caught a Finance sentence that had
silently become false, and the sponsor merge turned up one more ("Administration → Payments") in
prose written the same day on another branch.

---

## Verification (per sprint)

```
cd halatuju-web
npx jest --runInBand
node scripts/check-i18n.js
npx tsc --noEmit --target es2018 --downlevelIteration    # authoritative on the 8 GB box
npx next build
```

N3 additionally:

```
cd halatuju_api
pytest apps/scholarship/tests/test_org_fence.py apps/scholarship/tests/test_admin_scopes.py
pytest        # full suite — baseline 4859 as at 2026-07-27
```

**Manual check per sprint:** `npm run dev`, sign in as each of super / org_admin / admin / finance /
qc / reviewer / partner, and confirm the sidebar matches the role snapshot and the mock-up.

---

## Known friction

- **`administration/page.tsx` is 413 lines doing five jobs.** N3's split is the largest single chunk.
  The hoist comment at its top warns that naive extraction remounts inputs and steals focus — keep
  sub-components at module scope.
- **A new top-level admin route now fails the build until it has a registry entry.** Deliberate (it
  is what stops orphan #7), but it will surprise an agent who does not know. Nested dynamic routes
  need nothing.
- **`PF-2` module flags contradict prod** — migration `0098` seeded BrightPath `module_payout=False`
  while payout is live. Nothing reads the flags today, so this work must not start reading them.
