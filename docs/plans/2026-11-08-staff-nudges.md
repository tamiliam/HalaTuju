# Staff nudges: profile completion bar, profile banner, overdue-payment banner (2026-11-08)

Owner-requested platform feature, **exempt from the audit freeze by owner ruling 2026-11-08**, target: deploy
just AFTER audit group G7. Mock-ups approved by the owner 2026-11-08:
https://claude.ai/artifact/GPv4CHQ8zycNDE7MzvABav (artboards: completion bar on My Profile; blue profile
banner and red overdue banner under the top bar; phone width).

Executor: Opus agents. Branch `staff-nudges` (from origin/main fdd3c9a2). **Main is under audit: commit and
push to `staff-nudges` only. Never push or merge main, never deploy, no production writes, no paid calls.**
Two phases, one agent each: Phase A (sprints 1+2, profile) then Phase B (sprint 3, overdue), B on top of A.

## Owner-settled decisions

| # | Decision |
|---|---|
| 1 | Completion bar for every staff account from org admin down (org_admin, admin, finance, reviewer, qc, mentor, partner, source_partner). **Not** the super. |
| 2 | Items, equal weight, only those the person's role is asked (`profileCards.cardsFor`): everyone — photo, name, job title, About, phone; works with students (`worksWithStudents`) — + qualifications (the Reviewer-hold set: qualification, university, graduation year, field of study, as ONE item), + a language (EN/BM/TA ≥ conversational, as the hold), + address; mentors (`mentorsNow`) — + mentoring area. Optional extras (4th language, share toggles) never count. |
| 3 | "Important" fields for the banner: **photo and phone**; plus the mentoring area for mentors. Address never (private). Reviewer-hold fields are already enforced, never repeated here. |
| 4 | Profile banner: blue/info, under the top bar on every admin page EXCEPT `/admin/profile`; text names what is missing; "Complete profile" link; X hides it for **7 days** (per browser, localStorage); it returns if still incomplete; disappears once filled. |
| 5 | Overdue rule (server, ONE home, new module e.g. `apps/scholarship/invoice_overdue.py`): an invoice is overdue when SENT, not void, balance > 0, and today > `due_on` (Asia/Kuala_Lumpur date). Part-paid counts. An invoice with an open tenant payment declaration (`payment_declared`) does NOT count, part-paid or not (owner confirmed 2026-11-09). No grace period. Replace the web chip's own rule (`src/lib/invoices.ts` ~64) with the served flag so the chip and the banner agree. |
| 6 | Overdue banner: red, for those who may read invoices for their own organisation (`surface_gates.may_read_invoices` / `billing.view`, never a new role-label check) — in practice org admins; NOT the super (no own org). Text: invoice number, amount owing, days overdue; "View invoice" → `/admin/billing`. If several are overdue: the oldest, plus "and N more". X hides it **until the next sign-in** (sessionStorage or a sign-in-scoped key); gone once paid or declared. |
| 7 | One banner at a time: overdue first. |
| 8 | No email reminder (banner only). |

## Binding constraints (verified by the investigation; re-check)

- Serve, never derive: the completion % and missing items and the overdue flag are computed on the SERVER and served; any web copy needs a `drift-test:` marker.
- `apps/scholarship/urls.py` is at 599/600 lines and audit G6 moves the `/me` routes into a new `urls_me.py` — put any new route in a separate urls file, never grow urls.py. `apps/courses/views_admin.py` (AdminRoleView) is ledgered full — put new `admin/role/` data in a helper module or serve it from `admin/me/` instead. `views_admin/invoices.py` is 573 lines — do not grow it; `invoicing.py` existing functions untouched (audit A4.5 will build on your helper).
- AppShell.tsx 506/600 lines; the banner rides on every admin route: lazy-load it, keep the first-load median under its ratchet (157.6 kB budget; check `npm run bundle-budget -- --gate`).
- Read localStorage/sessionStorage only after mount (hydration; see `AppShell.tsx` ~162 and `src/lib/uiPrefs.ts` — its header asks for a deliberate decision before reuse; give the banners their own keys, per account id).
- No new role-label gate (`test_role_is_display_only.py`); use `may_read_invoices` / v2 `billing.view` and the existing profile card rules.
- Mobile Standard (`docs/mobile-standard.md`): no sideways scroll, X is a 44×44 target, text ≥12px, wraps on phones; `npm run mobile-check` must pass.
- i18n en/ms/ta for every string (admin slice `messagesAdmin`); flag ms/ta for language review. British English.
- Tenancy conventions (`docs/build-for-tenancy-conventions.md`): no org names in copy; endpoints through `_AdminBase`; tunables not hard-wired where the convention requires.
- No migration (dismissal is per browser). If you find you need one, stop and report — scholarship migration numbers 0206+ are reserved by the audit session.
- Existing live gaps (counts): every non-super lacks a photo; most lack job title/About; 1 invoice is past due today (the banner will fire for that org on deploy — expected).

## Phase A — sprints 1 + 2 (profile)

Server rule (one home) for completion: per-role items, done/missing, %, and the "important missing" list; served
where the profile page and the shell can read it cheaply (e.g. on `admin/me/`, or a small helper the shell's
existing probes call). Completion card at the top of `/admin/profile` exactly as the mock-up (bar, "N of M done",
ticks, links that scroll to the right card; one line at 100%). Profile banner in the shell per decision 4, built
as a small reusable top-banner slot that Phase B reuses (tone, text, link, dismiss key, dismiss scope).
Tests: per-role item sets (each role), %, important list, super excluded, banner hidden on /admin/profile,
dismiss 7 days then returns, rendered tests, mobile.

## Phase B — sprint 3 (overdue)

`invoice_overdue.py` (the ONE rule) + an org-level summary (oldest overdue invoice no., amount owing, days,
count) served cheaply to the shell for readers of invoices; the billing page's chip switched to the served flag.
Red banner per decision 6 via Phase A's slot; overdue wins over the profile banner. Tests: the rule's edge
cases (due today, part-paid, declared, void, zero balance, unsent, timezone), the fence (another org, super,
reviewer, finance), banner render/dismiss-until-sign-in, chip agreement.

## Handover (fill in at the end)

Where the overdue rule lives and what "overdue" means (for audit A4.5), files touched, gates, hours.

### Phase A handover (2026-11-08)

- **The completion rule** is `halatuju_api/apps/scholarship/profile_completion.py` (`item_keys`, `completion`), served as
  `completion` on `GET`/`PATCH admin/me/` and on the `admin/me/photo/` POST/DELETE answers (None for a super). Done means:
  photo = a `photo_path`; name/job title/About/phone = non-blank text; qualifications = the four Reviewer-hold parts
  (`reviewer_onboarding.REQUIRED_TEXT_FIELDS` less the phone, plus graduation year); language = EN, BM or TA at
  conversational or better (`LANG_FIELDS`/`SPEAKS`); address = street, postcode, city and state all filled; mentoring
  area = the mentor's `Mentor.area`. Percent rounds down.
- **The web reads it, never derives it:** the admin auth provider's existing once-per-session `admin/me/` read (the
  header photo) also keeps `profileCompletion`; the Profile page sets it after a save or a photo change.
- **The banner slot for Phase B:** `halatuju-web/src/components/admin/ShellBanners.tsx` (lazy behind
  `LazyShellBanners.tsx`, mounted under the Topbar in `AppShell.tsx`). Push the overdue candidate FIRST in
  `candidates` (`{ id: 'overdue', tone: 'critical', text, link: { href: '/admin/billing', label }, dismissLabel,
  scope: { kind: 'signIn', stamp } }`); the first candidate that applies and is not dismissed shows. Dismissals are
  `src/lib/topBanner.ts` (`bannerKey(name, accountId)`, `isDismissed`, `dismiss`; scopes `days` and `signIn` — the stamp
  should name this sign-in, e.g. the session user's `last_sign_in_at`). New props go on `ShellBannersProps` and are
  passed from `AppShell`'s `Chrome`. `TopBanner.tsx` draws either tone (`critical` is `role="alert"`).
- Sandbox surface `nudge-profile-banner` (mobile-check) shows the banner; the two `m8-profile-*` surfaces show the bar.

### Phase B handover (2026-11-09) — for audit A4.5

- **Where the overdue rule lives:** `halatuju_api/apps/scholarship/invoice_overdue.py`, ONE module, read-only, a leaf
  (`is_overdue(inv, today=None)`, `days_overdue(inv, today=None)`, `org_summary(organisation_id, today=None)`). No existing
  `invoicing.py` function was touched; nothing else in the API or the web answers "is it late?".
- **What "overdue" means, exactly:** an `Invoice` is overdue when ALL hold — `sent_at` is set; `voided_at` is not;
  `balance()` (total less receipts) is > 0.00; `has_open_payment_declaration()` is False (an open tenant claim, neither
  confirmed nor rejected, means "being checked", NOT late — even when part of the money has arrived and the status reads
  `part_paid`; a rejected claim no longer shields it); and today's date in Asia/Kuala_Lumpur (`timezone.localdate()`) is
  strictly AFTER `due_on`. On the due date itself it is not overdue; the day after is 1 day overdue. Part-paid counts; a
  zero-balance (fully discounted) month never does; no grace period. `days_overdue` = today − `due_on` in whole days.
- **The summary:** `org_summary` takes one organisation's sent, live invoices due before today, applies `is_overdue`, and
  names the OLDEST (earliest `due_on`, then `issued_on`, then id): `{invoice_id, number, currency, balance_myr (string),
  due_on, days_overdue, count, more = count − 1}`, or None.
- **Served:** `is_overdue` on every row of `GET admin/scholarship/billing/invoices/` (`views_admin/invoices.py`, still 573
  lines); `GET admin/scholarship/billing/overdue/` (`views_admin/invoice_overdue.py`, route in `urls_billing.py`; `urls.py`
  still 599) → `{overdue: null | summary}` for the caller's `owning_organisation` only (never a parameter), behind
  `_InvoiceBase._caller` (`surface_gates.may_read_invoices`: dark 404 for a non-super while billing is off, 403 for every
  role but org_admin); a super gets null. Classified in `test_org_fence.py`; `invoice_overdue.py` is in its `SCANNED` list.
- **Web:** `ShellBanners.tsx` pushes the red `overdue` candidate first; asks `getOverdueSummary` only while the shell's
  billing probe is live and the reader is not a super (the server's answer for a super is always null), never on
  `/admin/billing`, and afresh on leaving it. **Not shown on `/admin/billing`** (its chip says Overdue there; review of
  sprint B); it shows again elsewhere until paid or declared. X = `{kind:'signIn', stamp: session.user.last_sign_in_at}`,
  kept TWO ways (`lib/topBanner.ts`): a per-tab mark in `sessionStorage` that holds for this browser session even when
  the stamp moves (`last_sign_in_at` is per ACCOUNT, so a sign-in on another device moves it) and is cleared by
  `clearSignInDismissals` in `adminSignOut`; plus the stamp in `localStorage`, so a new tab of the same sign-in stays
  quiet. A new tab after a sign-in elsewhere shows it again (the safe direction). Also hidden for the page view. `lib/invoices.ts` `statusChip` takes `overdue` (the served flag) and
  keeps no date compare; tenant side: a late `sent` or `part_paid` reads Overdue; the owner's wording is unchanged.
- **Tests:** `tests/test_invoice_overdue.py` (rule edge cases: due today, part-paid, declared, rejected declaration,
  part-paid + declared, void, zero balance, unsent, KL vs UTC midnight; summary; the door: own org, another tenant, super,
  reviewer/finance/admin, dark billing, list flag = banner); web `ShellBanners.overdue.test.tsx`, `invoices.test.ts`,
  `InvoicesSection.test.tsx`. Sandbox surface `nudge-overdue-banner`.
- **The access matrix:** `test_team_tables_matrix.py` gives the new route its cells as the invoices list GET's own
  (`nudges_added_cells`); no existing cell moved.
- **Gates (merged tree, origin/main had nothing new):** API `pytest -n auto` 13,397 passed / 3 skipped, `manage.py check`
  clean, `makemigrations --check` no changes; web `npm run gates` (444 suites, 6,881 tests), `bundle-budget --gate` ok
  (median 156.767 of 157.6 kB), `mobile-check` 787 passed (the new surface at 360/390 in en/ms/ta).
- **Hours:** about 6.0 wall-clock, of which roughly 2.5 hands-on; the rest waiting on the shared test queue and the
  24-minute mobile-check.
- **Review round (2026-11-09):** the points above, plus the profile banner's second line is neutral for everyone
  (`admin.nudge.helpOne/helpMany`: "Adding it/them completes your profile." — the old "helps your team reach you" was
  untrue for mentors, referral partners and source users, whose phone only their inviting organisation sees); tests
  added for a void invoice in the summary count, an org_admin with no organisation (null), and 403 for qc, partner,
  source_partner and a mentor.
- **Left for A4.5 / open:** the banner refreshes on sign-in, on any token change and on leaving Billing, not live;
  the owner (super) chip never says Overdue (unchanged, by choice); ms/ta strings `admin.nudge.overdue*` need a language
  review.
