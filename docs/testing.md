Moved word for word from halatuju_api/CLAUDE.md on 2026-11-03. CLAUDE.md keeps the short rules; this is the full text.

## Testing

### Reviewing the console locally (TD-194, 2026-10-05) — no production data, ever

```bash
cd halatuju_api                      # NO DATABASE_URL / DB_HOST in the environment → SQLite
python manage.py migrate
python manage.py seed_local_console --email you@example.com   # made-up org, gift, applications
SUPABASE_URL=https://pbrrlyoyyiftckqvzvvo.supabase.co python manage.py runserver
cd ../halatuju-web && npm run dev    # .env.local already points at http://localhost:8000
```

Sign in at http://localhost:3000/admin with that address. Supabase does the sign-in only; the
local API verifies the token through the public JWKS (`SUPABASE_URL`) and links your account to
the seeded super admin on the first VERIFIED sign-in. Development settings allow every origin, so
nothing changes on the live API. The command refuses any database that is not SQLite. It cannot
show documents (no Storage) — never re-run extraction locally.

### ⚠ The API gate — run the deploy gate's OWN line, not a serial run

```bash
cd halatuju_api
python -m pytest -q -n auto -p no:cacheprovider   # ⬅ what cloudbuild.yaml runs (xdist). A serial
                                                  # run passes things the gate refuses: subTest /
                                                  # parametrize values travel to the controller and
                                                  # execnet cannot serialise a datetime (TD-352's
                                                  # push, 2026-10-06: 1 failed in the gate, 0 here).
```

### ⚠ The FRONTEND gate list — all four, before any push that deploys web

```bash
cd halatuju-web
npm run gates                # ⬅ ONE WORD, runs all four below in order — `typecheck`, `lint`,
                             # `i18n`, `test` — and stops at the first failure. Each is also a
                             # script of its own in package.json, for iterating on one gate. The
                             # warnings below still apply; this only saves you typing them.

# ── or the same four by hand ──
npx jest --maxWorkers=2      # --maxWorkers=2 was required on the old 8 GB box (a full run OOMed and
                             # reported worker contention as FAILURES, exit 253). The dev box has
                             # 32 GB since 2026-08-02, so that note is stale; the flag is harmless.
npx tsc --noEmit --incremental false
                             # types. ⚠ 0 ERRORS REQUIRED since 2026-09-18 (TD-221 closed: the 24
                             # old test-file errors are gone, so ANY error is yours). Keep
                             # `--incremental false`: with the cache on, tsc REPLAYS errors from
                             # tsconfig.tsbuildinfo after the cause is fixed.
npx next lint                # ⚠ 0 ERRORS REQUIRED (warnings are fine — passing builds carry
                             # several). NEITHER jest NOR tsc runs ESLint, and `next build` LINTS
                             # BEFORE IT EMITS: on 2026-07-30 two eslint-disable comments naming a
                             # rule this config never loads failed the WEB build while the api
                             # deployed, so production ran new server code behind an unchanged UI
node scripts/check-i18n.js   # parity across en/ms/ta
```

**⚠ AND FOR ANY UI CHANGE, THE PHONE CHECK (Mobile M0, 2026-10-31)** — local only, not in Cloud
Build (build minutes). Rules: `docs/mobile-standard.md`; status: `docs/mobile-ledger.md` (generated).

```bash
cd halatuju-web
npm run mobile-check         # BEFORE A PUSH. THIS BRANCH's public pages + every sandbox surface
                             # (local `next dev -p 3100`, started for you) × 360/390 px × en/ms/ta.
                             # API reads are fetched from the live API by Playwright and handed to the
                             # page (no local API needed; CORS does not apply). FAILS if any cell is
                             # worse than mobile-check/baseline.json. Read-only: never signs in, blocks
                             # anonymous sign-in and every non-GET request.
npm run mobile-check -- --update   # after a fix: lowers the baseline, never raises it
npm run mobile-ledger        # regenerate docs/mobile-ledger.md; commit it with baseline.json
MOBILE_PUBLIC_BASE=https://halatuju.xyz npm run mobile-check
                             # AFTER A DEPLOY: measures PRODUCTION's public pages — never a
                             # substitute for the default run before a push
```

**⚠ AND FOR INTERACTIVE BEHAVIOUR, A RENDERED TEST — a source-shape guard is not evidence.**
This repo has 17 `@testing-library/react` + jsdom tests; `components/admin/CommandPalette.test.tsx`
is the model and its docblock states the reason. Source-shape guards are right for **structural**
claims (no bare `disabled`, no hard-coded hex, no surface forgotten). They are blind to anything
depending on **focus, event propagation, keyboard, drag, mount/unmount or async flush** — a paste
handler on an unfocused `<div>` satisfied `/onPaste=/` for a day while the feature could not fire at
all. See `components/OrgRequestAttachments.paste.test.tsx` for the shape: dispatch the event from
somewhere ELSE on the page, because dispatching at the panel passes under both implementations and
proves nothing.


### Backend

```bash
cd halatuju_api
pip install -r requirements.lock -r requirements-dev.txt     # a fresh clone needs nothing else
python -m pytest -q -n auto -p no:cacheprovider              # the gate's line (above)
python -m pytest apps/courses/tests/test_golden_master.py apps/courses/tests/test_stpm_golden_master.py -q
python manage.py check
python manage.py makemigrations --check --dry-run            # "No changes detected"
```

Golden masters: **SPM 5,319**, **STPM 2,025** (2,026 until 2026-10-29, owner: a subject counts once per SPM prerequisite group — decisions.md) — if either moves, you broke eligibility. At v3.0.0:
8,084 pytest / 3 skipped · 4,146 jest / 252 suites (measured at the cut). Measure your own
baseline before you start; never quote an inherited number.

### Pre-deploy checklist

1. Both suites green with the gates' own command lines; `bundle-budget` green on the dev box.
2. A migration? Production applied by hand, ledger row recorded, ledger diffed (no gap).
3. A new table? RLS on (automatic), one `service_role` policy added, Security Advisor 0 errors.
4. Eligibility, money or identity? Adversarial review done, findings fixed or answered.
5. A version bump owed? `VERDICT_ENGINE_VERSION` if a band can move; the genuineness `MODEL_VERSION`
   on any doc-recognition signature change; a `PROMPT_VERSION` when a prompt changes.
6. New strings in en/ms/ta (Malay and Tamil are first drafts until the owner reads them **in Sol**,
   never in chat — label them with `python manage.py sol_tag --project halatuju --tag "<sprint>"
   --new` from `C:\Users\tamil\Python\Development\Sol`; at pre-flight `sol_status --project
   halatuju` lists message files holding the owner's Sol edits, which are committed on their own
   as `i18n: owner review via Sol` after `npm run i18n`); a changed reviewer surface updates the
   reviewer Guide + FAQ in the same change.
7. The owner's yes to push.

**Common profile S2 (2026-10-31) — release order and one standing danger.**
- **Migrate first (scholarship 0193, by hand), then the API, then the web — the API BEFORE the web.**
  The new web saves the phone, the card and a source's name through `admin/me/` (which the old API
  does not serve); the old web kept saving the phone through `admin/reviewer-profile/` during the rollout.
  *(Superseded 2026-10-31, TD-439: that route serves the phone and "share with students" but no longer
  writes them; `admin/me/` is their one writer — `docs/decisions.md`.)*
- **⛔ Never run `cleanup_orphan_blobs --apply` from a checkout or image older than S2.** Its
  `known_paths` learned the staff photos (`ReviewerProfile.photo_path`, `staff-photos/…`) in S2; an
  older copy reads every staff photo as an orphan and DELETES it. Dry-run first, always, and read the
  list.

### Test fixtures

`apps/scholarship/tests/factories.py` builds the supporting rows (`make_org`, `make_programme`,
`make_cohort`, `make_admin`, `make_student`, `make_shortlistable_student`, `auth_token`,
`authed_client`) and, above all, **`make_application(stage=…, outcome=…)`** — an application at a
named stage, carrying every field the product would have stamped by then and none it would not.
`**overrides` sets anything explicitly; an unknown stage, or an `outcome` at a stage that has none,
raises a clear `ValueError`.

| Stage | `status` | What the product has set by then | What it deliberately has NOT |
|---|---|---|---|
| `submitted` | `submitted` | locale, notify_email, declaration + `declared_at`, consent-to-contact | verdict, any decision stamp |
| `scored` | `submitted` | `verdict`, `bucket`, `shortlist_reason`, `decision_due_at` | `decision_released_at`, `shortlisted_at` |
| `shortlisted` | `shortlisted` | `decision_released_at`, `shortlisted_at`, `reminder_anchor_at` | `profile_completed_at` |
| `profile_complete` | `profile_complete` | `profile_completed_at`, frozen `requirements_snapshot` | reviewer, verdict |
| `assigned` | `profile_complete` | `assigned_to`, `assigned_at` — **the status does not move** | verdict |
| `interviewing` | `interviewing` | `reporting_date` (the officer settles it here) | verdict |
| `verdict_recorded` (needs an outcome) | `interviewing` | `officer_verdict`, `verdict_decided_at/_by`, engine version; `award_amount` applied on accept / cleared on decline — **the status does not move** | every verify stamp |
| `awaiting_qc`, `outcome='recommend'` | `interviewed` | the verdict stamps **plus** `verified_at`, `verified_by`, `verify_checklist`, `profile.nric_verified` | QC/award stamps |
| `awaiting_qc`, `outcome='decline'` | `interviewed` | the verdict stamps only | **`verified_at`, `verified_by`, `verify_checklist`, the NRIC lock, `award_amount`** |
| `recommended` | `recommended` | `recommended_at/_by`, published anon `SponsorProfile`, active share consent, `award_amount` → in the sponsor pool | `awarded_at` |
| `awarded` / `active` / `maintenance` | same | `awarded_at` / `active_at` / `maintenance_at` + `maintenance_substate` | later stamps |
| `closed` | `closed` | `closure_reason`, `closed_at/_by` (the factory builds a FUNDED close; a stalled pre-award close is `make_application(<stage>)` + `closure.close_application`, TD-352) | — |
| `rejected` (branches off the decline road) | `rejected` | `rejection_category`, `rejected_at/_by`, `pre_decline_status`, `pending_rejection_category`, `decline_due_at`, `pending_decline_by` | `decline_email_sent_at`, any QC/award stamp |
| `expired` (branches off `shortlisted`) | `expired` | `expired_at`, `reminder_stage` 4, `last_reminder_at` | any verdict or reviewer |

⚠ **Two roads reach QC and they leave different marks.** A reviewer who RECOMMENDS goes through
`verify-accept`, which stamps `verified_at` / `verified_by` / `verify_checklist` and locks the
NRIC; a reviewer who DECLINES goes through `submit-decline`, which stamps **none** of those,
because a decline has no identity or completeness gate. Asking for `verified_at` on the decline
road is asking for a mark production never writes — that was BrightPath request #24.

`test_factories.py` walks a fresh application to **every** stage through the real services and the
real endpoints and asserts the factory agrees, so the factory cannot become the next stale fixture.
**New test files must use it** — enforced by `test_code_standards.py`; the ~134 files that still
hand-build one convert as they are next touched (`small-change-lane.md`), and their ledger entries
may only fall.

### Rendered tests for the cockpit

**Where the harness lives** (code health H6, front end): `halatuju-web/src/test/`.

| File | What it is |
|---|---|
| `adminApplicationDetail.ts` | `buildApplicationDetail(stage, overrides?)` — a complete, type-correct `AdminScholarshipDetail` at a NAMED STAGE. It mirrors the stage table above, including the two roads to QC, and `adminApplicationDetail.test.ts` reads `factories.py` and fails if the two stage lists drift apart. |
| `renderCockpit.tsx` | Mounts the real `src/app/admin/scholarship/[id]/view.tsx` for a given ROLE, with i18n, the admin-auth context, the router and `@/lib/admin-api` mocked, every on-mount call primed, and **any `console.error` failing the test**. |
| `view.decision` / `view.closed` / `view.roles` / `view.actions` `.test.tsx` | 59 rendered tests, beside the page. |

**The rule.** A change to `view.tsx`, or to any cockpit panel split out of it, runs `view*.test.tsx`.
**A new panel gets a rendered test, not a source guard** — the screen is the subject, so mount it.
Two text guards were retired into this harness (`approveLockoutGuard`, the component half of
`docFileLayout`) and two more converted to mounts (`ActionCentre.vircle`, the per-surface half of
`screenshotInput`).

**The text guards that remain, ON PURPOSE.** Each one's subject really is the shape of the source,
and there is nothing to render:

| Guard | Why it stays text |
|---|---|
| `brand-guard.test.ts` | One home for a brand literal. The claim is "this string appears nowhere else", which only a scan of everywhere can make. |
| `sandbox-safety.test.ts` | The sandbox must reach no real service. A mount proves one path is safe; the scan proves no path exists. |
| `icPadlockGuard.test.ts` | A verified NRIC stays locked. Structural: one expression either consults the rule or it does not. |
| `no-icu-messageformat.test.ts` | The SHAPE of a message value. `t` has no ICU engine, so an ICU construct renders its template verbatim — that is a property of the catalogue, not of a screen. |
| `navigation.test.ts` | Walks the routes on DISK against the registry, so a page that exists with no row (or the reverse) is found. Only the filesystem can answer that. |
| `soft-evidence-drift.test.ts` | A backend list copied into the front end. The guard is that the copy still matches its source. |
| `codeStandards.test.ts` | The standards themselves. Deliberately ONE file, so the project gains one source-reading test and not a habit of them. |
| `theme.test.ts`, `pageWidth.test.ts` | Convention checks that belong in ESLint. Noted, not moved (H6 scope). |
| `applicationStatus` / `requestStatus` / `screenshotInput` (the disk-walk half) | Each asks "is there a case/surface nobody thought about?" — a question only a walk of the tree can answer. The BEHAVIOUR each one used to assert now lives in a mount. |

## Moved from halatuju_api/CLAUDE.md, 2026-11-05 (audit sprint A0.3)

Testing rules (full text, unchanged).

- **Full suites run ONCE locally, right before the push, after the last rebase.** Not after each review
  round or fix — re-run only the affected test files then. Cloud Build runs the full suite again and
  ships nothing red.

- ⚠ Run the API gate with `-n auto`, not serially. ⚠ Frontend: all four gates before any push that deploys web; tsc and `next lint` need 0 ERRORS (`next build` lints before it emits).
- ⚠ For any UI change run `npm run mobile-check` (and `npm run mobile-ledger`); ⚠ interactive behaviour needs a RENDERED test, a source-shape guard is not evidence.
- Golden masters SPM 5,319 / STPM 2,025: if either moves you broke eligibility. Measure your own baseline; never quote an inherited number.
- Reviewing the console locally: SQLite + `seed_local_console`, no production data, ever; never re-run extraction locally.
- Pre-deploy checklist: both suites green; migration applied by hand + ledger row; new table has RLS + `service_role` policy + Advisor 0 errors; eligibility/money/identity adversarial review; version bumps (`VERDICT_ENGINE_VERSION`, genuineness `MODEL_VERSION`, `PROMPT_VERSION`); strings in en/ms/ta; the owner's yes to push.
- ⛔ Never run `cleanup_orphan_blobs --apply` from a checkout or image older than S2 (it deletes staff photos). Dry-run first.
- ⚠ Two roads reach QC (recommend via `verify-accept`, decline via `submit-decline`) and leave different marks; fixtures and the cockpit's rendered tests are in the doc.

