# Sources and referral partners — roadmap (four sprints)

**Status:** Sprint A BUILT 2026-10-09 (uncommitted at writing; migration `courses/0078_two_referral_columns`,
cutover `docs/scholarship/two-columns-cutover-sql.md`). Sprints B–D not started.
**Owner's model (settled 2026-10-09 — do not re-litigate):** *"Referral partners and sources and orgs
are different. Referral partners are a category of their own. Orgs > sources."* Three categories:

| Category | Who | Owned by | What it has |
|---|---|---|---|
| **Organisation** (tenant) | BrightPath | — | gifts, staff, the console; `PartnerOrganisation.objects.tenants()` |
| **Source** | SMC, EWRF, HSS, HYO, MHM, PPTM, CUMIG… | the organisation that added it | a place on a gift's "Who referred you?" list; contact details for partner emails |
| **Referral partner** (platform) | CUMIG | no organisation | two `partner`-role logins on the course-selector side, the `?ref=cumig` link, and the students it sees through `StudentProfile.referred_by_org` |

All three are rows of `PartnerOrganisation` today; the `cumig` row is both CUMIG (source) and CUMIG
(referral partner). **The student record has TWO INDEPENDENT columns — SOURCE and REFERRAL PARTNER.**
Either may be empty, both may be filled, they may name the same organisation, and neither writer ever
touches the other (decisions.md, 2026-10-09). Each application also keeps the answer given at submit
in `intake_snapshot['profile']['referral_source']`.

Related debt: TD-379 (drop `PartnerOrganisation.programme`), TD-380 (loose `referred_by_org` links —
Sprint A closes most of it), TD-381 (sources not fenced by organisation — Sprints B and C).

---

## Sprint A — two columns on the student, referral partners marked ✅ BUILT 2026-10-09

**The live bug it fixes.** The bursary submit (`profile_sync`) linked `referred_by_org` whenever a
student picked a source, so picking CUMIG (source) put her on CUMIG (referral partner)'s
course-selector list, where the two partner logins see NRIC, phone, address and household income.
The course-selector `ProfileView.put` and `ProfileSyncView.post` linked ANY active row by code
(tenants and sources included), and the sign-in sync re-wrote the chip and the link from
localStorage on EVERY sign-in, so a `?ref` and the bursary answer overwrote each other.

**What was built.**
- `PartnerOrganisation.is_referral_partner` (boolean, `db_default=False` so the image already serving
  can still insert a source). A boolean, not a `kind` enum: one row is BOTH a source and a referral
  partner today (`cumig`), and a tenant is already derived (`tenants()`) — a single-valued kind could
  not say "source AND referral partner" without a combined value Sprint B would have to unpick.
  Backfilled from `PartnerAdmin role='partner'` (production: `cumig` only); the migration refuses to
  mark a tenant. A new referral partner is marked BY HAND until Sprint B's screen. It does NOT stop `cumig` being offered as a source (sources are still
  `gift_sources.active_sources()`).
- `StudentProfile.source` — nullable FK to `PartnerOrganisation`, `related_name='sourced_students'`
  (Sprint B repoints it to the sources table, same ids). `referred_by_org` keeps its name and becomes
  the REFERRAL PARTNER column (a rename costs a column rename on a live table plus every reader, for
  no behaviour).
- Writers (`apps/courses/referral_links.py` holds the rules for the partner column):
  - **Bursary submit** (`profile_sync.sync_profile_fields`) writes ONLY `source` — the offered source,
    or NULL for a fixed choice or blank; absent key = untouched. Never `referred_by_org`. The
    `is_offered` refusal is unchanged.
  - **`?ref=`** (`ProfileSyncView.post` → `referral_links.apply_ref_code`) writes ONLY
    `referred_by_org`, only for an ACTIVE referral-partner row, FIRST TOUCH only; an unknown,
    source, tenant or switched-off code links nothing. Never `source`.
  - **`ProfileView.put` IGNORES `referral_source`** (the key left `ProfileUpdateSerializer`): no web
    caller sends it; a stale bundle that did would lose its whole save to a 400; and letting it write
    the chip would let a client overwrite the bursary answer the counts read.
  - **The legacy chip `referral_source`** keeps exactly two writers: the bursary submit (unchanged —
    its readers below are bursary readers) and the `?ref` sync, now FIRST TOUCH and only while the
    student has NO application. So a sign-in can never overwrite a bursary answer, and a `?ref` can
    never move what the bursary counts and partner emails see; the course-selector readers still get
    the first `?ref` code as before. The web is unchanged: the server makes the resend harmless, and
    it must anyway, for the bundles already in browsers.
- Witness readers (`bursary._resolve_witness_org`, `views_admin/graduation.py` witness authority, the
  cockpit's `referred_by_org` payload) read `referral_links.referring_org(profile)` = source, else
  referral partner — the same organisation as before for every student whose bursary answer named a
  source. Payload keys unchanged.
- Migration `courses/0078_two_referral_columns`: schema + marker + backfill (owner's rulings: source
  from the latest application's snapshot when it names a source row; KEEP every link to the referral
  partner, including the 13 CUMIG pickers — "Filled"; CLEAR links to any other row, after a dated
  backup). Cutover SQL: `docs/scholarship/two-columns-cutover-sql.md`.

**Readers left on the legacy chip `StudentProfile.referral_source` — Sprint C moves them:**

| Reader | File | Reads |
|---|---|---|
| Partner emails — `partner_applications`, `chip_tally` (`CHIP_FIELD`) | `apps/scholarship/partner_comms.py` | `profile__referral_source == org.code` |
| Partner digests / milestones | `apps/scholarship/partner_notify.py` (~l.244) | the chip, by application |
| Sources page "Students" counts | `apps/scholarship/views_admin/sources.py` `_source_application_counts` | the chip, by application |
| Applications list Source filter, column and sort | `apps/scholarship/views_admin/applications.py` (~l.108, ~l.139); `serializers_admin.py` list (~l.256, ~l.335) | the chip |
| Cockpit referral pill | `serializers_admin.py` detail `referral_source`; web `CockpitHeader.tsx` | the chip (labelled through `referred_by_org`) |
| Apply form pre-fill | web `src/lib/scholarship.ts` ~l.433 (`referringOrg: profile.referral_source`) | `GET /profile/` `referral_source` |
| Course-selector partner dashboard Source dropdown, filter, list and CSV | `apps/courses/views_admin.py` (~l.368-397, ~l.458-493); `serializers_admin.py` (courses) | the chip |
| The intake snapshot itself | `profile_sync.build_intake_snapshot` | the chip at submit (this is the per-application answer Sprint C reads) |
| Staff student pages | web `admin/students/page.tsx`, `admin/students/[id]/page.tsx` | the chip |

**Review fixes (Sprint A, 2026-10-09):** `referral_partners()` also excludes tenants, the fixed codes
and the house code; a `?ref` code must be ASCII `[a-z0-9_-]{1,50}` after lower-casing; the witness
authority check is tested end to end; `bursary_e2e` seeds the witness as a source; the cutover asserts
no OPEN gift offers `cumig` (an old-image CUMIG pick in the deploy window would otherwise stay on
CUMIG's list) and lists any after the deploy.

**Size budgets (Sprint A):** `courses/models.py` grew within its +20 allowance to 1386 of 1388 (no
split owed now — it has no Phase-4 sprint; Sprint B must split it first); `courses/views.py` shrank; `bursary.py`, `serializers_admin.py` and
`graduation.py` changed by a line or two. New: `apps/courses/referral_links.py`,
`apps/scholarship/tests/test_two_referral_columns.py`.

---

## Sprint B — sources become their own table, owned by an organisation

**Goal:** a source is its own record with an owning-organisation FK (TD-381 part 1–2). Platform
referral partners stay on `partner_organisations`, unowned, with their logins, links and students
untouched. Expand-contract, migrate-first.

1. New table `referral_sources` (`scholarship` app — it is a bursary concept): `id` (SAME ids as the
   `partner_organisations` rows they come from, so every FK repoint is a constraint swap, not a data
   rewrite), `organisation` FK (today's seven → BrightPath, the house tenant), `code`, `name`,
   contact person / email / phone, `show_in_apply`, `is_active`, `created_at`. RLS on + `service_role`
   policy. A unique `(organisation, code)`; the reserved codes refused as today.
2. Repoint, each a migrate-first FK swap with the old column kept until D:
   `ProgrammeReferralSource.source`, `StudentProfile.source` (Sprint A's column), `witness_org` ×2
   (`ScholarshipApplication.witness_org`, `BursaryAgreement.witness_org`), `PartnerEmailLog.organisation`
   (⚠ CASCADE today — repoint, never delete a row), `Invitation.organisation` for `source_partner`.
3. Fence by owning organisation: the Sources list / POST / PATCH (`views_admin/sources.py`), the
   gift Configuration card (`gift_sources.sources_for`), partner emails and the partner email log.
   Never list a tenant row or a platform referral partner. The house row (`brightpath`) leaves the
   Sources list.
4. **TD-379 contract:** drop `PartnerOrganisation.programme` — deploy the image without the field
   FIRST, then drop the column and record the ledger row (migrate-first is the wrong order for a drop).
5. **Referral partners get a screen** (super only): mark / unmark `is_referral_partner` — until then
   it is a reviewed SQL update. And **inviting a `partner` login onto a row that is not a referral
   partner: refuse, or mark it** — owner's choice at sprint start (`AdminInviteView`,
   `courses/views_admin.py`). Today nothing stops it, and such a login sees no students (the
   `?ref=` writer links only marked rows) until someone marks the row.
6. Tests: the fence (A cannot see B's sources), the id-preserving copy, every repointed FK.

**Size and splits:** `views_admin/sources.py` and `gift_sources.py` are small. ⚠ **`courses/models.py`
is at 1386 of its 1388 cap after Sprint A, so Sprint B STARTS with a moves-only split of it** (its own
commit, no behaviour change, ledger keys moved through `_moved`) before any field is touched there. The
new model goes in `apps/scholarship/models/` (its own module; register it in the re-export shell). `scholarship/views.py` (5 lines of room at Sprint A) — touch it only through
a moves-only split first if the submit needs more than a line.

## Sprint C — readers move to the per-application answer; the categories stop leaking into each other

1. **Counts, partner emails and the Applications filter read the per-application answer**
   (`intake_snapshot.profile.referral_source`, or a new indexed `ScholarshipApplication.source` FK
   filled at submit and backfilled from the snapshot — decide at sprint start; an FK is cheaper to
   filter and count). Every reader in the Sprint A table above moves; the chip stops being a bursary
   signal.
2. **A source-names endpoint every list role can call** (reviewer and QC get 403 on `getSources()`
   today, so their Source filter shows only the three fixed choices — TD-381 part 4), fenced by
   organisation.
3. **Witness from the source only** (owner: never from the referral partner; **only super records a
   witness**): `referring_org` and the `AdminBursaryWitnessView` authority check go; the cockpit's
   `referred_by_org` key is replaced by a `source` key (web and api in step, old key kept one release).
4. **`?ref` never pre-fills the bursary form** — the apply pre-fill stops reading the chip.
5. **CUMIG (source) and CUMIG (referral partner) contact details kept separate** — the source row's
   contact (partner emails) and the referral partner's (its logins) stop sharing one row's fields.
6. The course-selector partner dashboard's Source dropdown/CSV: show the referral partner and drop
   the chip, or read it from the per-application answer — owner question at sprint start.

**Size and splits:** `scholarship/views.py` (cap 2441, 2436 at Sprint A) and `courses/views_admin.py`
(cap 1264) are near their caps; `serializers_admin.py` (cap 1234) too. Each that must grow gets a
moves-only split in its own commit first. Web: `admin/scholarship/page.tsx`, `CockpitHeader.tsx`,
`lib/scholarship.ts` (in the oversize ledger) — run `npm run bundle-budget` before adding any
string (TD-360, en.json is at its line).

## Sprint D — retire the old shared fields and rows; close the debt

1. Retire, never delete: the chip `StudentProfile.referral_source` (stop writing; keep the column one
   release, then a contract migration), the sources' copies on `partner_organisations` (switched off,
   kept — `PartnerEmailLog` and old snapshots point at them; a delete CASCADEs the email log).
2. Close TD-380 and TD-381 with evidence; update `docs/architecture.md`, `ARCHITECTURE_MAP.md`,
   `role-matrix.md`, the Sources and Configuration help text, and the reviewer Guide/FAQ if a
   reviewer surface changed.
3. Contract migrations ordered image-first (a dropped column the serving image selects 500s every
   read).
