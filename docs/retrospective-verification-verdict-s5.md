# Retrospective — Verification Verdict roadmap, Sprint 5 (2026-06-02)

Branch `feature/verification-verdict` (committed + pushed, **not deployed**). Plan:
`docs/scholarship/verification-verdict-plan.md`. **The LAST sprint of the roadmap** —
S1–S5 are now complete; the whole branch deploys next (user-gated).

## What Was Built

The **Officer Review Cockpit** — the two-stage-profile hinge. The admin
`/admin/scholarship/[id]` page becomes a cockpit where the coordinator *audits*
the AI's four-fact verdict rather than assembling it, clears leftover caveats, and
records their own verdict which can trigger the final sponsor profile.

- **Audit / override capture (backend, additive).** Five fields on
  `ScholarshipApplication` (migration `0037`): `ai_verdict_snapshot` (the
  `build_verdict` snapshot at decision time), `officer_verdict`, `verdict_reason`,
  `verdict_decided_by`, `verdict_decided_at`. `AdminRecordVerdictView` records the
  officer's verdict beside the AI's and optionally fires the existing Phase-D
  refine; `AdminVerdictMetricsView` + pure `audit.py` compute the **override rate**.
- **Cockpit (frontend).** Four-fact verdict **tiles**; a **Caveats** panel (open
  `resolution_items`) with officer Ask/Resolve; a redesigned **Documents drawer**
  (grouped by fact, consistent pills, extracted fields, View link — replaces the
  "messy box"); and a sticky **Record-verdict** panel (per-fact pass/fail + reason
  + "Save verdict & generate final profile" + Tools + an "AI suggested … — you
  decide" footer). Pure `lib/officerCockpit.ts` (27 jest tests).

Numbers: backend **493** scholarship pytest (+17), frontend **226** jest (+27),
i18n parity **1782** (Tamil first-draft). `next build` clean; migration matches the
model. Cockpit layout **A** + the standalone documents drawer approved in Stitch.

## What Went Well

- **The backend de-risked the deploy by staying additive.** Capturing the audit as
  fields on the existing `ScholarshipApplication` (not a new `VerdictAudit` table)
  means `0037` is a plain additive `ALTER` — it avoids a *second* new-model
  contenttypes/auth workaround (TD-058) on top of `0036`, and one snapshot per
  application is all the override metric needs.
- **Reuse over re-derivation held.** `record-verdict` calls the existing
  `refine_sponsor_profile` for the final profile rather than re-implementing it;
  the cockpit reads the existing `verdict`/`resolution_items` serializer fields.
- **Parallelism paid off.** The backend slice was built + fully tested (493 green)
  on the main thread *while* Stitch generated, so the delegated FE build started
  against a finished, green contract.
- **The re-verify gate caught two subagent inaccuracies** (see below) — exactly the
  "a subagent's 'verified' is a claim, not evidence" discipline working as intended.

## What Went Wrong

1. **Stitch timed out twice on the dense desktop cockpit and didn't persist on the
   call — then BOTH attempts landed late as duplicates.**
   *Symptom:* two `generate_screen_from_text` calls for the full cockpit timed out
   client-side; `list_screens` showed no new screen for several minutes, and the
   only desktop screen present was a *stale* older one ("Verification - Admin View")
   whose content did not match the prompt. *Root cause:* a fully-specced desktop
   cockpit (4 verdict tiles + draft + caveats + documents drawer + a 4-toggle record
   panel + tools) is too content-dense to render within the client timeout, and a
   timed-out gen persists *late* (#72/#76). Verifying the stale screen's content
   (not its title) is what prevented signing off the wrong screen. *Fix (applied):*
   a drastically **trimmed, single-purpose** prompt (the documents drawer alone)
   succeeded synchronously; and the user's pasted preview-URL `node-id`s →
   `get_screen` recovered both late-landed cockpit variants. *Fix (system):* lesson
   sharpened — for a dense DESKTOP admin screen, split into one-pattern-per-screen
   from the start rather than one all-in-one screen; don't sit in a retry loop.
2. **The subagent reported a gate it could not have run, and "fixed" a non-problem.**
   *Symptom:* the subagent reported `npm test → 226 passed`, but there is **no
   `test` script** in `package.json` (jest runs via `npx jest`); and it replaced all
   `primary-600` with `indigo-600` claiming "`primary-600` is not defined" — but
   `primary.600` (#1066c2) **is** defined in `tailwind.config`. *Root cause:* a
   delegated agent self-reports commands/claims that read plausibly but weren't
   verified against this repo's actual scripts/config. *Resolution:* the orchestrator
   re-ran the real gates (`npx jest` → 226 genuinely green; `next build` EXIT=0 via a
   captured log; `check-i18n` 1782) and checked the colour claim against
   `tailwind.config` — the indigo *outcome* turned out correct anyway (this admin
   page already uses indigo as its AI/action accent, so the cockpit is consistent),
   so no revert was needed. *Fix (system):* lesson added — when a subagent names a
   gate command or asserts a config fact, re-run/verify it against the repo, not the
   report; the claim and the underlying reasoning can both be wrong even when the
   visible result happens to be fine.

## Design Decisions

Logged in `docs/decisions.md`: (1) audit captured as **additive fields on
`ScholarshipApplication`**, not a new `VerdictAudit` model — to keep `0037` a simple
additive `ALTER` and avoid a second contenttypes workaround; (2) `record-verdict`
**reuses** `refine_sponsor_profile` for the final profile rather than forking the
logic, with the audit recorded even when finalise can't run.

## Numbers

- Backend: **493** scholarship pytest (+17 `test_verdict_audit.py`). Frontend:
  **226** jest (+27 pure `officerCockpit.ts`). i18n parity **1782** × en/ms/ta.
- Migration `0037` (additive; `makemigrations --check` clean). `next build` EXIT=0.
- New: `apps/scholarship/audit.py`, `migrations/0037_verdict_audit_fields.py`,
  `tests/test_verdict_audit.py`, `lib/officerCockpit.ts` (+ tests). Changed:
  `models.py`, `views_admin.py`, `urls.py`, `serializers_admin.py`, the admin
  `page.tsx` (cockpit), `admin-api.ts`, 3 i18n files.
- New TD: **TD-083** (verdict-metrics endpoint + `officer_verdict.overall` built but
  not surfaced in the UI).
