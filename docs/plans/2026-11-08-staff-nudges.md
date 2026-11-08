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
| 5 | Overdue rule (server, ONE home, new module e.g. `apps/scholarship/invoice_overdue.py`): an invoice is overdue when SENT, not void, balance > 0, and today > `due_on` (Asia/Kuala_Lumpur date). Part-paid counts. An invoice with an open tenant payment declaration (`payment_declared`) does NOT count. No grace period. Replace the web chip's own rule (`src/lib/invoices.ts` ~64) with the served flag so the chip and the banner agree. |
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
