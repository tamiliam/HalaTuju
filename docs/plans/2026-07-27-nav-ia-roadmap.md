# Nav/IA roadmap — the partner console shell — ✅ CLOSED 2026-07-28

> **This roadmap is closed.** Four sprints shipped and are live: **N1** registry → **N2** shell →
> **N3b** route split → **N4** the rail. Arc retrospective:
> `docs/retrospective-2026-07-28-nav-ia-arc.md`.
>
> **Everything this roadmap promised now exists.** N3a was parked and then un-parked by the
> owner on 2026-07-28 (the trigger never fired — see `decisions.md`); it shipped the same
> day. Retro `docs/retrospective-2026-07-28-nav-n3a.md`.
>
> **Do not add work to this file.** Theming and PF-1 have their own homes, named at the bottom.

**Owner-approved 2026-07-27.** Design of record:
<https://claude.ai/code/artifact/17d259a8-f15f-4f0a-858e-492f1cb157a6> (interactive mock-up; switch
role and sidebar model in the controls). The N4 rail was approved from a second mock-up:
<https://claude.ai/code/artifact/df8ab5ae-cc10-47b5-acc4-ed57e944a280>.

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

## ✅ N3a — scopes endpoint + switchers — SHIPPED 2026-07-28

> **The owner reopened this**: *"now that we have built PF-1, can we build n3a?"* — after
> noticing the built console does not match the approved design (the top bar shows
> `HalaTuju / BrightPath` as static text; the programme crumb is hardcoded
> `programmeName={undefined}` and never renders). **The trigger below never fired** —
> one organisation still owns everything. It was an owner decision, not a condition
> being met, and the record says so.

> This is the one item for which the roadmap is reopened. Everything else in this file
> stays closed.


**Not cancelled, not owed-and-drifting: parked against a condition.**

**The trigger: a second organisation exists in production with an active programme.** Until then a
switcher is a dropdown with exactly one entry — a control that teaches nobody anything and cannot
be tested against the case it exists for. Build it when there is a second thing to switch *to*.

**Why it is parked rather than built now**, given the second tenant is credible: the switcher is the
*console's* answer to multi-tenancy, and **PF-1 is the platform's**. PF-1 decides which organisation
a student's application belongs to; N3a only decides what an admin is looking at. Shipping the
viewer before the router would be furniture on an unsound floor — and PF-1 also settles how a
programme is identified in a request, which N3a's endpoint should then match rather than pre-empt.

**When it is picked up**, the spec below is still good. Two things in it are non-negotiable:
`AdminScopeListView` must be classified in `FENCED_OR_EXEMPT` (`test_org_fence.py`) or CI fails by
design, and the switcher must not become an ambient auth context — no global header, no cookie, no
middleware rewrite. For super it persists a client-side *display* preference only.

**Cheap tell that the trigger has fired — and NOT the obvious one.** Checked against production
2026-07-28: there are already **10 active `PartnerOrganisation` rows**, so "more than one
organisation" is true today and means nothing. Nine of them are **referral** organisations (schools,
NGOs — Sri Murugan Centre, Tara Foundation, …) that send students; exactly one, **BrightPath Bursary
(id 11)**, OWNS anything. The table holds both kinds and does not distinguish them by a flag.

The real tell is more than one organisation **owning** something:

```sql
SELECT count(DISTINCT owning_organisation_id) FROM scholarship_cohorts WHERE is_active;
-- 1 today
```

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
pytest        # full suite — baseline 4882 as at 2026-07-28 (post sponsor-S2 merge)
```

**Manual check per sprint:** `npm run dev`, sign in as each of super / org_admin / admin / finance /
qc / reviewer / partner, and confirm the sidebar matches the role snapshot and the mock-up.

---

## Known friction

- ~~**`administration/page.tsx` is 413 lines doing five jobs.**~~ Split in N3b; it is a 20-line
  redirect now. **The warning it carried still binds:** every component in `StaffAdmin.tsx` must stay
  at module scope, because one declared inside its parent remounts the subtree and steals focus from
  the invite inputs.
- **A new top-level admin route now fails the build until it has a registry entry.** Deliberate (it
  is what stops orphan #7), but it will surprise an agent who does not know. Nested dynamic routes
  need nothing.
- **`PF-2` module flags contradict prod** — migration `0098` seeded BrightPath `module_payout=False`
  while payout is live. Nothing reads the flags today, so this work must not start reading them.

---

# Second arc — the rail and the theme (owner, 2026-07-28)

Design of record: <https://claude.ai/code/artifact/df8ab5ae-cc10-47b5-acc4-ed57e944a280>
(interactive: hover-open rail, brand active state, "Go to" chip, System/Light/Dark, role switch).

The owner approved the preview with "looks good, proceed" and did not answer the five open
questions, so each is settled below with the recommendation that was in the preview. **Every one is
reversible in a line; none is a fence.** They are recorded here so nobody has to guess later what
was chosen versus what was overlooked.

| # | Question | Settled as | Why |
|---|---|---|---|
| 1 | Hover-open or pinned? | **Hover-open, with a pin remembered per person** | The Supabase behaviour they asked for, and the pin answers the people it annoys. |
| 2 | Everywhere, or desktop only? | **Desktop only** | The mobile drawer already works and is a different interaction. Untouched. |
| 3 | Keyboard chords? | **Yes — build them** | The preview shows the chip with a key. Shipping the chip without the key would be a label for something that does not happen. |
| 4 | Dark: console or whole app? | ~~Console only~~ **WITHDRAWN 2026-07-28** | Theming became its own planning track — see below. This was my answer, not the owner's, and it presumed dark was the requirement. |
| 5 | Theme per person or per device? | ~~Per device~~ **WITHDRAWN 2026-07-28** | Same. Whether a theme belongs to a person, a device or a tenant is an input to that exercise, not a default. |

## ✅ N4 — the icon rail — SHIPPED 2026-07-28

Retro `docs/retrospective-2026-07-28-nav-rail-n4.md`; decisions ×5; lessons ×5; TD-187 + TD-188.
**968 jest / 63 suites · i18n 4090 ×3 · build clean · 17 files · no backend, no migration.**
Built to the plan below, with two things worth knowing: the rail **overlays** (a spacer holds the
48px, so nothing reflows), and **per-group collapse was removed** — it existed to shorten a long
wide sidebar and the rail is short by construction.

The Manual pass found a sentence false since N2 — *"The links along the top are your workspace"* —
which both previous currency passes missed because it names neither "Administration" nor "sidebar".

**Original deliverable:** the sidebar collapses to a 48px icon rail that opens on hover/focus over
the content, the active row is the only brand-coloured thing in it, and pointing at a row shows
"Go to <page>" with its chord.

| File | Change |
|---|---|
| `src/lib/navigation.ts` | `NavItem.chord?: string` — one letter, the `G`-then-X key |
| `src/lib/uiPrefs.ts` | new — SSR-safe `localStorage` prefs; **N5 reuses it for the theme** |
| `src/components/admin/Sidebar.tsx` | rail states: collapsed / open / pinned; group rule; dot badge; "Go to" chip |
| `src/components/admin/AppShell.tsx` | rail slot (no reflow), pin state, the chord listener |
| `src/components/admin/Topbar.tsx` | pin toggle |
| tests ×3 | `navigation.test.ts`, new `Sidebar.test.tsx`, `AppShell.test.tsx` |
| `src/messages/{en,ms,ta}.json` | `admin.shell.goTo`, `pinNav`, `unpinNav`, `navHint` |
| Manual + FAQ | the currency rule: chapters that describe the menu |

**Lessons carried in (sprint-start step 2) — these are the ones with teeth here:**

- *"A prefix rule needs an exception for the root of its namespace" (N1).* The analogue for chords
  is **collision**: two routes claiming `G T` is the same class of bug. A test asserts chords are
  unique, upper-case, and never on a placeholder — a slot with no page cannot own a key.
- *"Make a new scoping parameter REQUIRED rather than default" (P2a).* Inverted deliberately here:
  `chord` is **optional**, because most routes will never have one and a required field would force
  a fake. The guard is the uniqueness test, not the type.
- *"Never run the suite while someone is looking at a dev server" (N2).* No jest while a review
  server is up. If a review is wanted, the artifact above already renders the work.
- *"Build the preview at the FIRST blocker" (N3b).* **TD-182 still breaks admin Google sign-in on
  localhost.** It is not fixed and this sprint does not fix it. The preview is the review surface;
  do not send the owner at `/admin/login` again.
- *"Asserting a bulk edit matched says nothing about whether it reads correctly" (N3b).* Manual copy
  about the sidebar gets read back line by line, and grepped for what it MEANS ("in the menu",
  "on the left") as well as for the words being changed.
- *"A quoted test count is not a measured one" (N1).* Baseline is **933 jest / 4882 pytest**,
  measured on the merged tree at N3b close. Re-measure at close; do not add.

**Not in scope:** the switchers (N3a), any backend, the mobile drawer, and any page that is not
the shell.

## ⛔ Theming is NOT part of this roadmap — owner, 2026-07-28

I had drafted a two-sprint theme plan here (a System/Light/Dark switch, then a console repaint).
**The owner removed it:** *"Themes should be its own planning. Not just dark but other likely
themes, as well, which may cover UX, etc."*

That is the right call and the draft was the wrong shape — it treated "dark mode" as the
requirement, when dark is one theme among several and the expensive part (naming every colour in
the app) is the same work regardless of how many themes end up sitting on top of it. A plan built
around one output would have chosen the token set that suited that output.

**Nothing theme-related shipped.** The only artefact was a `theme` key reserved in
`src/lib/uiPrefs.ts`, which presumed the answer to "does it follow the person or the device" — it
has been deleted, and that module now carries a note saying its reasoning covers a menu's width
and does not generalise.

**Carried forward as INPUT to that planning exercise, not as decisions:**

- **Measured cost.** 1,537 hard-coded light colours across 119 files; 31 of those files are the
  console. The brand ramp is already CSS variables (`--brand-*`, overridden per tenant at runtime),
  so a theme changes the GROUND under the brand and must never touch the brand itself.
- **Open questions the removed draft had silently answered:** how many themes; whether a theme is a
  person's choice, a device's, or a tenant's; whether it covers the student and sponsor surfaces or
  only the console; how it interacts with tenant branding; and whether density/typography belong to
  the same setting.
- The interactive mock-up
  <https://claude.ai/code/artifact/df8ab5ae-cc10-47b5-acc4-ed57e944a280> shows a working
  light/dark console. Treat it as evidence that the ground can move, **not** as an approved design.

**Scope and sequence, owner 2026-07-28:** *"We'll discuss themes (admin pages, sponsor pages, and
student pages) separately after we've landed on PF-1."* So it spans **all three surfaces**, not the
console alone — which retires my "console only" answer on its own terms, not just procedurally — and
it starts **after PF-1**, not after N4.

**Route in:** `Settings/_workflows/implementation-planning.md`, its own roadmap file.

## ⚠ Both of these still queue behind PF-1

Recorded in the escalation note above, and unchanged by this arc being approved.

---

# Where the remaining work lives — this file is closed

| Work | Home | State |
|---|---|---|
| **PF-1** — the open cohort is chosen platform-wide | `docs/plans/2026-07-28-pf1-open-cohort-org-context.md` | **Next.** Brief written; owner reassigned it to this agent 2026-07-28. Blocked on one product question (§2 of the brief), and its **safety half is not** — that ships first. |
| **Theming** — admin + sponsor + student surfaces | its own roadmap, not yet written (`implementation-planning.md`) | After PF-1, by the owner's sequencing. |
| **N3a** — switchers | above, parked with its trigger | After a second organisation exists. |
| **Sprint E** (erasure) + the unsignable DPA | tenant gates, not engineering | Neither closed. |
