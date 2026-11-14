# Sponsors tagged to an organisation: DRAFT analysis

Date: 13 November 2026. Status: DRAFT for the owner. No code changed.
Place: `docs/analysis/` did not exist; the project keeps plans in `docs/plans/`. This is an analysis, not a plan, so it has its own folder.

Owner ruling (13 Nov 2026): "Sponsors should be tagged to an organisation. An org may have different onboarding from another."

Sources read: `models/sponsors.py`, `models/funding.py`, `models/comms_templates.py`, `models/review.py`, `sponsor_signup.py`, `sponsor_invite_gifts.py`, `sponsor_terms.py`, `pool.py`, `views_admin/sponsors.py`, `views_admin/sponsorships.py`, `views_admin/sponsor_terms.py`, `views_admin/org_emails.py`, `urls.py`, `tests/access_manifest.json`, `tests/test_org_fence.py`. Paths below are under `halatuju_api/apps/scholarship/` unless stated.

---

## 1. How sponsors relate to organisations today

**The Sponsor row has no organisation.** `Sponsor` (table `sponsors`) holds one account per sign-in: name, email, phone, status (pending / approved / rejected / suspended), trust flag, consent, notification settings, `reviewed_by`. The only field called `organisation` is a free-text `CharField`: the sponsor's own company name. It is NOT a tenant link. Do not reuse it (same name, different meaning).

**The link to an organisation already exists, one step down, through the programme.** A `Programme` (a gift) belongs to one `PartnerOrganisation`.

| Thing | Links to | So the organisation is |
|---|---|---|
| `SponsorProgrammeMembership` (sponsor, programme, status) | programme | `programme.organisation`. One row per sponsor per gift, with its own status. The organisation accepts or takes it back. |
| `Donation` (table `sponsor_donations`) | programme (nullable FK) | `programme.organisation`. The wallet is per sponsor per programme. |
| `Sponsorship` (sponsor, application) | the student's application | `application.owning_organisation`. |
| Pool (`pool.for_sponsor`) | approved memberships | a sponsor sees only gifts they are approved into. |
| `SponsorReferral` | inviter sponsor only | none. It is sponsor to sponsor. |
| `SponsorTermsVersion`, `SponsorTermsSection`, `SponsorEmailTemplate` | nothing | platform-wide. No organisation field. |
| `SponsorTermsAcceptance` (sponsor, version) | sponsor + version | platform-wide. One acceptance per version, whatever the organisation. |

**Sign-up and approval today.**
1. The sponsor signs in with Supabase and posts `sponsor/register/`. A `Sponsor` is created as `pending`.
2. `sponsor_signup.signup_programmes_for` decides which gifts they join. Source one: the sponsor invitation matched on email (an admin filed it under that admin's organisation, so its gifts all belong to that organisation). Source two: the platform's single active gift, if there is exactly one. Otherwise the answer is empty on purpose: a stranger off the public form, with several active gifts, gets no membership.
3. Registration opens a `pending` membership per gift (`open_signup_memberships`).
4. An admin posts `admin/sponsors/<pk>/review/`. This sets the ACCOUNT status, stamps `reviewed_by`, settles the memberships registration opened, and emails the sponsor.
5. Another organisation's gift needs that organisation's own acceptance: `admin/sponsors/<pk>/membership/` (`AdminSponsorMembershipView`). It is already fenced to the caller's gifts and answers 404 across organisations.
6. The sponsor reads and accepts the platform terms (`sponsor/terms/`, `/quiz/`, `/accept/`).

**Can a sponsor fund students in more than one organisation today? Yes.** Nothing in the models forbids it. Several approved memberships in gifts of different organisations are allowed, and the wallets are kept apart per gift. Whether any live sponsor does this is a live-data question (section 6).

**Is there an existing field for "owning organisation"? No.** The nearest thing is derived: the organisation of the sponsor's memberships, donations and sponsorships. A stored "home organisation" would be new.

---

## 2. Every sponsor surface and its fence today

| Endpoint / screen | Who is let in | Organisation fence now |
|---|---|---|
| GET `admin/sponsors/` (list; web `/admin/sponsors`) | super, org_admin, admin, finance | **None on the accounts.** Every sponsor is listed with email and phone. The money (`given`) and student counts inside are fenced to the caller's organisation. |
| GET `admin/sponsors/pending-count/` | same | **None.** Counts all pending sponsors platform-wide. |
| GET `admin/sponsors/<pk>/` (web `/admin/sponsors/[id]`) | same | **Account open to all** (email, phone, note, source). Credits, memberships and sponsorships inside go through `_SponsorScope`, which is fenced. |
| POST `admin/sponsors/<pk>/review/` | super, org_admin | **None.** Any org_admin can approve, reject or suspend any sponsor. Flagged INTENT-UNCLEAR. |
| POST `admin/sponsors/<pk>/membership/` | super, org_admin | **Fenced** to the gift's organisation (404 across organisations). The model to copy. |
| Credit chain (`admin/scholarship/credits/<pk>/sign`, `cancel`) | admin, finance, org_admin | **Fenced** by programme to organisation. Needs an approved membership. |
| GET `admin/sponsorships/` | super, org_admin, admin, finance | Students inside are fenced by the application's owner. I read the shape only; confirm per-row fencing in the security sprint. |
| `admin/scholarship/sponsor-terms/` and `<pk>/` (list, create draft, read, edit, sections, validate, preview, import-docx) | super, org_admin, admin (`sponsor_terms` door) | **None.** Platform-level. Any organisation's admin authors. Flagged INTENT-UNCLEAR. |
| POST `.../sponsor-terms/<pk>/publish/` | super, org_admin | **None.** Publishing archives the active version and changes what EVERY sponsor accepts. Opened to org_admin 2026-07-28. |
| `.../sponsor-terms/<pk>/sections/<n>/generate-quiz/` | none in the test world (AI off) | Same platform scope. Spends Gemini credit. |
| GET `admin/scholarship/sponsor-emails/`, PATCH `<kind>/` (nine templates, on/off switch) | super, org_admin, admin | **None.** One platform row per kind (`kind` is unique). In the test world PATCH is refused for all (switch off); org_admin_b can read. |
| Sponsor portal: `sponsor/register/`, `terms/`, `terms/quiz/`, `terms/accept/`, `me/`, `wallet/`, `pool/`, `pool/<ref>/fund/`, `sponsorships/`, `my-students/<ref>/` | the sponsor | Pool is fenced to approved gifts. Terms are one platform document. Own-record checks are in the manifest (sponsor_b refused on sponsor_a's student). |
| `sponsor/referrals/` | the sponsor | Sponsor to sponsor. The invitee lands in no organisation. |
| Web pages | | Admin: `/admin/sponsors`, `/admin/sponsors/[id]`, `/admin/sponsors/terms/[id]`, the sponsor-emails editor. Sponsor: `/sponsor/register`, `/sponsor/(portal)/terms`, `account`, `students`, `my-students`, `trust`. |

The manifest holes this analysis answers (INTENT-UNCLEAR): review (any organisation's admin acts on any sponsor); list and detail (other organisations' admins and finance read the whole record, including email and phone); terms (any organisation's lead writes and publishes the platform terms).

---

## 3. Options

Both options keep the existing `SponsorProgrammeMembership`. It is the right place for the per-gift decision and already works.

### Option (a): one owning organisation per sponsor

**Shape.** Add `Sponsor.owning_organisation` (FK to `PartnerOrganisation`, nullable at first, PROTECT). Use this name to match `ScholarshipApplication` and `PartnerAdmin`; never `organisation` (clash with the free-text field).

**Model / migration.**
- One column on `sponsors` plus a data migration to backfill.
- Terms: add `organisation` FK (null = platform default) to `SponsorTermsVersion`; "one active version" becomes one active per organisation. `SponsorEmailTemplate.kind` unique becomes unique per (organisation, kind). Acceptance stays (sponsor, version); the version now implies the organisation.
- Registration sets the owner from the invitation's organisation. A stranger with no invitation stays null and lands in a super-only queue.

**Backfill rule (do not run on live from here; ship a dry-run command that prints the plan).**
1. If all the sponsor's memberships, donations and sponsorships sit in ONE organisation, that is the owner.
2. Else if a sponsor invitation matched on their email, the invitation's organisation.
3. Else if the platform has exactly one organisation with an active gift, that one.
4. Anything else (several organisations, or none) stays null and is listed for the owner. Never guess.

**Fence changes.** Review, detail, list, pending-count: an organisation's admins see and act only on sponsors it owns (404 across organisations, as `AdminSponsorMembershipView` does). Finance reads only its own organisation's sponsors. Terms and emails scoped by organisation; super sees all. Pool unchanged.

**The weakness.** A sponsor is one person who may fund two organisations, and today may. Option (a) either forbids that (a rule nobody asked for; it would strand any live sponsor already funding two organisations) or keeps cross-organisation gifts while the "owner" alone sees the record. Then the second organisation cannot see its own funder. That is why (a) is the weaker fit.

**Size.** About 1.5 sprints, roughly 20 files (model, migration, backfill command, 6 views, terms and email services, 3 web pages, tests).

### Option (b): per-organisation membership (recommended)

**Shape.** The account stays platform-level (one login, one identity). Add table `SponsorOrganisationMembership` (sponsor, organisation, status, vetted_by, vetted_at; unique on sponsor + organisation). It sits ABOVE the per-gift membership: an organisation approves the sponsor first, then approves them into its gifts. An organisation sees only sponsors who have a row with it. Approving into a gift without an organisation row creates one.

**Model / migration.**
- New table (one migration) plus a data migration creating a row for each (sponsor, organisation) pair found in `SponsorProgrammeMembership`.
- `SponsorTermsVersion.organisation` (null = platform default). One active version per organisation. An organisation's own version replaces the default for its sponsors; an organisation with none uses the platform default.
- `SponsorTermsAcceptance` gains `organisation` (null = platform), so a sponsor accepts each organisation's terms on joining it. Existing acceptances count for the platform default. Keep `basis` as it is; never collapse "grandfathered" into "accepted".
- `SponsorEmailTemplate`: unique on (organisation, kind), falling back to the platform row. This is what "different onboarding" means for the welcome, approved, rejected, suspended and reinstated emails.
- Registration: a sponsor registering through an invitation joins that organisation. A stranger joins nobody until they pick an organisation or super assigns one.

**Backfill rule.**
1. For each (sponsor, organisation) pair found in memberships, donations or sponsorships, create an organisation row. Status: `approved` if any gift membership there is approved; otherwise `pending`; `rejected` or `suspended` to match.
2. Terms: every sponsor keeps their platform-default acceptance. No re-asking until an organisation publishes its own version.
3. A sponsor with no gift membership, donation or sponsorship: use the invitation's organisation (email match); otherwise leave unassigned (super only).
4. The dry run lists: single-organisation sponsors (the large majority expected), multi-organisation sponsors, and unassigned. The owner reads the last two.

**Fence changes.**

| Endpoint | After |
|---|---|
| list, pending-count | rows where the caller's organisation has a row. Super sees all, plus an "unassigned" filter. |
| detail | 404 for a sponsor with no row in the caller's organisation (not 403, so the tenant is not confirmed). Email and phone shown only to a member organisation. |
| review | acts on THIS organisation's row. Account-wide suspend (all organisations) stays super. An organisation's reject or suspend affects its own gifts only. |
| membership | unchanged (already fenced). |
| sponsor-terms read, edit | own organisation's versions; the platform default is super only. |
| sponsor-terms publish | own organisation's version only; platform default super only. |
| sponsor-emails | own organisation's rows; platform rows super only. |
| portal terms, accept, quiz | the terms of the organisation the sponsor is joining. |
| pool | unchanged, plus a "terms accepted for this organisation" gate (decide in the feature slice). |

**Web pages.** `/admin/sponsors`, `/admin/sponsors/[id]` (organisation column, per-organisation status), `/admin/sponsors/terms/[id]` (which organisation), the sponsor-emails editor (which organisation), `/sponsor/register`, `/sponsor/(portal)/terms`, `account` (which organisations they belong to). A sponsor must never see another organisation's name for a gift they are not in.

**Tests.** Move the INTENT-UNCLEAR manifest entries to fenced (section 4). Add: two-organisation sponsor, unassigned sponsor, terms acceptance per organisation, email fallback, backfill dry-run output.

**Size.** About 2.5 sprints in two parts (section 4), roughly 30 to 35 files in all.

### Recommendation: (b)

- It matches what exists: money, pool and acceptance are already per gift, so per organisation is the natural step up.
- It never strands a sponsor who funds two organisations, which (a) can.
- The security slice needs no new table (section 4), so the money work is not delayed.
- (a) is cheaper by about one sprint but gets the person wrong: a sponsor is one person with possibly several funders, not one organisation's property.

---

## 4. The split

### Security slice (before M4 money goes live): small, one sprint, no migration

Goal: stop another organisation reading or vetting a sponsor. Derive "this organisation's sponsor" from data that exists today, so there is no schema change and no backfill risk.

**Rule for the slice.** A sponsor belongs to organisation X if they have a membership (any status) in a gift of X, OR a donation or sponsorship in X, OR a sponsor invitation from X matched on email. Super sees all.

Changes:
1. `views_admin/sponsors.py`
   - `AdminSponsorDetailView`: 404 for a sponsor not belonging to the caller's organisation. Hide email and phone from anyone else.
   - `AdminSponsorListView`: same filter (super unfiltered).
   - `AdminSponsorPendingCountView` and `my_pending.pending_sponsor_count`: same rule for the badge and the Overview card.
   - `AdminSponsorReviewView`: an org_admin may act only on a sponsor belonging to their organisation. If the sponsor also belongs to another organisation, only super may reject or suspend the account (account status gates every organisation's pool).
2. `views_admin/sponsor_terms.py`: publish becomes super only. This reverses the 2026-07-28 opening, an owner decision, so ask first. Draft and edit can stay open because only publish changes what sponsors accept.
3. `views_admin/org_emails.py`: sponsor-email edit to super only until per-organisation rows exist.
4. `tests/access_manifest.json`: move the INTENT-UNCLEAR entries to fenced. Detail and review: org_admin_b and finance_b hidden, org_admin_a allowed. List and pending-count: assert only own rows. Terms publish: org_admin_a and org_admin_b hidden. Add tests for the unassigned sponsor (super only) and the two-organisation sponsor.
5. One helper, `sponsor_in_org(sponsor, admin)`, in one module, so every view asks the same question.

Size: about 6 to 8 source files and 3 to 4 test files. It touches personal contact data and the gate on money, so it is a full sprint with an adversarial review before the push, not a small change. Roughly one small sprint.

### Feature slice (after about 4 December): per-organisation onboarding, about 1.5 sprints

1. `SponsorOrganisationMembership` table, migration, dry-run-first backfill command, registration and approval writing it.
2. Per-organisation terms: `organisation` on versions, one active per organisation, acceptance per organisation, the portal reads the right one, publish scoped per organisation.
3. Per-organisation email templates with platform fallback.
4. Web: terms editor, emails editor, admin sponsors screens, sponsor register, terms and account pages.
5. Guide and FAQ update (the project rule: a feature change updates them in the same change).
6. Replace the slice's derived rule with the table (one place to change, by design).

---

## 5. Risks

**Money.** Credits, payment runs and pool funding key on the gift's organisation, not on the sponsor. So a wrong tag on a live sponsor does NOT move money or change a balance. What it breaks:
- **Visibility.** The right organisation's finance and admin lose sight of their own funder (detail answers 404), so they cannot work a credit through the sponsor screen. The credit chain itself is fenced by gift and keeps working.
- **Vetting.** The wrong organisation can approve or suspend. A suspension shuts the sponsor out of every organisation's pool at once. It is the one change that cuts across organisations, which is why account-wide suspend stays with super for a two-organisation sponsor.
- **Unassigned sponsors.** Only super sees them. Safe, but it can look like "my funder disappeared". Give super an "unassigned" list and clear it quickly.
- **Never re-point live money.** The tag says who may see and vet. Donations and sponsorships stay as they are.

**Data protection.** The sponsor list shows email and phone to every organisation's staff today. These are personal data of people who consented to one organisation's terms. The slice closes that exposure. Per-organisation terms also tidy consent: someone who accepted the platform terms has not necessarily accepted another organisation's. Keep `basis=grandfathered` visible so "we did not ask" is never read as "they agreed". Benefactor anonymity towards students is unchanged and must stay so.

**Other.**
- Narrowing terms publish reverses an owner decision (28 July); get the owner's word.
- Several active gifts and no invitation leaves a stranger unassigned by design (the PF-1 rule). Do not "fix" it by guessing an organisation.
- Keep one helper for "which organisation", so the pool, the screens and the emails never disagree.

---

## 6. Questions for the owner (live data)

1. Does any live sponsor have memberships, donations or sponsorships in MORE THAN ONE organisation? This decides how many two-organisation cases the backfill must list and confirms (b) over (a). Use the dry-run report, not a hand query.
2. How many live sponsors have no membership, donation or sponsorship (so no organisation can be derived)? Who vets them: super only, or the organisation they name?
3. May terms publish go back to super only until per-organisation terms exist (reversing 28 July), or do you accept the risk until after 4 December?
4. When one organisation suspends a sponsor, should it hit every organisation's pool (today) or only its own gifts? The slice leaves the cross-organisation case to super; the feature slice makes it per organisation.

## Owner ruling (13 Nov 2026)

- Sponsors are tagged to an organisation. An organisation may have its own onboarding.
- Today there is ONE tenant organisation (live check 13 Nov: 1 organisation owns all 4 gift programmes; staff are bound to 1 organisation; every linked sponsor is in that organisation). So all sponsors belong to it, and the cross-organisation access found by the access test cannot be used today.
- PARKED until a second organisation is planned. When it is, an intermediate step will channel sponsors to organisations (owner).
- TRIPWIRE: do not onboard a second tenant organisation until the security slice above ships (fence sponsor list, detail, review; terms publish and sponsor emails). The feature slice (per-organisation onboarding and terms) is designed together with the channelling step.
