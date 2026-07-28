# Sponsor module enrichment — roadmap (S3, S4 remaining)

**Design of record:** <https://claude.ai/code/artifact/9eec1f75-e38d-49d3-9df9-d4ad7a7b9fe3>
(both screens + the email panel, built on real production figures).
**Moved here 2026-07-28** from `.claude/plans/snazzy-whistling-biscuit.md` at sprint close, so the
unbuilt half of the roadmap lives in the repo rather than a scratch file. S1/S1.1/S2 detail is in
`docs/retrospective-2026-07-28-sponsor-fixes-and-credit-ui.md` and
`docs/retrospective-2026-07-27-sponsor-detail-s1.md`.

## Shipped

- **S1 (2026-07-27)** — the sponsor detail page, read-only. Migration `0132` (`last_seen_at`).
- **S1.1 (2026-07-28)** — referral attribution by email, honest last-seen copy, Students column.
- **S2 (2026-07-28)** — the wallet-credit interface: record / sign / void. No migration.

## Owner decisions still governing the remainder (2026-07-27)

1. The three existing hardcoded sponsor emails become editable too, via a `{student_cards}`
   structural token — so the panel covers all eleven and is not a half-truth.
2. Sponsorship history shows the anonymous `pool_ref` only, hyperlinked to the cockpit. *(Done in S1.)*
3. The mockup is approved before any code (CLAUDE.md design-first rule).

---

## S3 — sponsor email templates

**The gap it closes:** a sponsor is approved and never told. `AdminSponsorReviewView` flips the
status field and returns. There is no approval email, no rejection email, no suspension email, and
no welcome email on registration (registration emails *us*, not them). Eight people were approved
in silence.

**Copy the partner-comms architecture exactly** (`partner_comms.py` + `PartnerEmailTemplate` + the
Sources card, shipped 2026-07-26): one switch per email, wording editable inline, two-gate dark
launch (`SPONSOR_COMMS_ENABLED` platform flag **and** each template's own `enabled`), every attempt
logged, placeholders validated against a per-kind allowlist.

New `SponsorEmailTemplate` (kind unique, `enabled`, subject, body, `updated_by_email`) and
`SponsorEmailLog` (sponsor FK, kind, recipients, subject, ok, note, sent_at) — the siblings of
`partner_email_templates` / `partner_email_log`, same RLS convention. Migrate-first.

**Eleven kinds**, five of them closing the silence above:

| Kind | When | Exists today? |
|---|---|---|
| `welcome` | registered, vetting pending | **No — new** |
| `approved` | vetting approved | **No — new** |
| `rejected` | vetting declined | **No — new** |
| `suspended` | account suspended | **No — new** |
| `reinstated` | suspension lifted | **No — new** |
| `credit_confirmed` | a credit reaches `confirmed` | **No — new** |
| `new_students` | hourly realtime alert | Yes, hardcoded |
| `weekly_digest` | Monday digest | Yes, hardcoded |
| `referral_invite` | they invite someone | Yes, hardcoded |
| `low_balance` | balance below one award | **No — new** |
| `annual_statement` | yearly giving summary | **No — new** |

The three existing ones carry generated per-student mini-cards with artwork. Adopting them into
editable templates requires a **`{student_cards}` structural token** — exactly the
`{counts_table}` / `{student_table}` mechanism `partner_comms.render` already implements. **Extract
that renderer into a shared `email_templates.py` seam** so partner and sponsor templates share one
block-splitting implementation rather than growing a second copy.

**`credit_confirmed` fires only on `confirmed`** — reading through `visible_donations`, never on a
draft. Telling a donor we hold money that has not been signed off is the one unrecoverable mistake
available here. (S2 makes this reachable: a real person now drives credits to `confirmed` in the UI.)

**The badge pair ships with this sprint, not before.** `/admin/sponsors` gains the segmented
**Sponsors** | **Emails** badges we shipped on the Sources page. They were deferred from S1
deliberately: the Emails panel *is* S3, and a badge that opens nothing is the failure the
partner-comms card exists to avoid. Do not add them early.

---

## S4 — reason, log, export

- **A suspension or rejection needs a reason.** There is no field for one today. If we start
  emailing the sponsor we must be able to say why — so a mandatory note on reject/suspend, stored,
  shown on the detail page, available to the template as `{reason}`. (A hand-declared serializer
  field needs an explicit `max_length` — L289.)
- **The per-sponsor email log** rendered on the detail page ("Emails we have sent", collapsed).
- **CSV export** of a sponsor's statement — finance will ask, and the payments module already has
  the CSV idiom to copy.

---

## Risks that still apply

- **Anonymity is load-bearing.** Sponsor-facing serializers are allowlists by deliberate design,
  with planted-identifier leak tests. A template placeholder that could resolve to a student's name
  would breach that from a new direction — so the per-kind placeholder allowlist and the
  `unknown_placeholders` guard are not optional.
- **Consent.** `consent_at` / `consent_version` records PDPA consent at registration. Transactional
  account mail (approved, suspended, credit confirmed) is covered; `annual_statement` and
  `low_balance` edge toward marketing and want an owner decision before they are switched on.
- **Tax receipts are a question, not a build.** A donor receipt is only meaningful with LHDN
  s44(6) status, which turns on the Foundation entity question that is still open. Flagged, not
  scoped.
- **Two agents share this repo.** Work in a worktree, stage explicit paths, never `git add -A`.

## Constraint carried from the nav/IA sprint

`halatuju-web/src/lib/navigation.ts` is the one route registry and `navigation.test.ts` fails the
build on drift. **S3 adds no route** — the Emails panel is a badge on `/admin/sponsors`, and nested
dynamic routes are exempt — so it should not trip the guard. A new TOP-LEVEL
`app/admin/<segment>/page.tsx` would need a `NAV_GROUPS` entry **and** an i18n label in en/ms/ta.

## Verification (both sprints)

- `pytest apps/scholarship` — plus: `credit_confirmed` never firing on a draft, placeholder +
  banned-phrase rejection, the template payload's exact key set, and a leak test asserting no
  student identifier can reach a sponsor email.
- `npx jest` — the badge swap, the panel's pure decisions.
- Prod read-only checks: `sponsor_email_log` empty while dark; `SPONSOR_COMMS_ENABLED` unset.
- Migrate-first for S3's migration (hand-written Postgres DDL via MCP, `django_migrations` row,
  RLS + one `service_role` policy), then push. A hand-written `CreateModel` must use
  `BigAutoField` (L113), and run `makemigrations --check` before committing.

## Lessons that bit this module (apply them again)

- **L277** — the admin payload is a curated allowlist and the FE type is a second copy; they change
  in the SAME diff, and `tsc`/`next build` is the check (jest is node-env and never type-checks a page).
- **L252** — for a hard boundary use a plain dict/Serializer, never a `ModelSerializer`.
- **L109** — i18n parity does not prove a key EXISTS; ~47 `sponsorPortal.*` keys shipped as raw key
  paths for four sprints because all three locales were equally missing. New keys go into the
  key-existence guard, and any server-code→copy mapping goes through an allowlist (see
  `creditErrorKey`).
- **L380** — "dark by default" in a comment is not a flag check. S3's panel gates on a real
  `comms_enabled` the backend returns, exactly as the partner card does.
- **2026-07-28** — when a sprint gives a role a new power, re-read that role's SUMMARY row in
  `docs/scholarship/role-matrix.md` and its manual chapter's opening sentence, not only the section
  being added. S3 gives `org_admin` control of what sponsors hear; that is a role power.
