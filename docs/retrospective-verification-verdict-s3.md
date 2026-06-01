# Retrospective — Verification Verdict roadmap, Sprint 3 (2026-06-02)

Branch `feature/verification-verdict` (committed + pushed, **not deployed** —
feature branch; CI deploys only on `main`). Plan:
`docs/scholarship/verification-verdict-plan.md`.

## What Was Built

The **resolution-ticket backend** — the IBKR model. Each unresolved item from the
verification verdict becomes a discrete, independently-resolvable **`ResolutionItem`**
(migration `0036`, RLS deny-by-default) closable by a **document**, a typed
**explanation**, or a one-tap **confirm**. This is the backend that makes a
phone call the exception, not the routine.

- `resolution.py` — `CODE_TO_TICKET` maps the *ticketable* verdict codes →
  `{fact, kind, doc_type}`; `sync_resolution_items` is **idempotent** (one
  `source='system'` item per `(application, code)`, enforced by a partial unique
  constraint + an `IntegrityError` catch for races) and **auto-resolves** a
  ticket the moment its gap clears, while **never re-nagging** an answered
  confirm; `resolve_item` (student response) and `add_officer_item` (the
  structured successor to `info_request_note`).
- Three verdict codes are **deliberately not ticketed** (confirmed with the user):
  `ic_service_down` (transient — auto-retries, escalates to `ic_unreadable` if
  persistent), `grades_unverified` (a machine "not-read-yet" state), and
  `str_present_unverified` (officer-side confirmation).
- Student endpoints (list + resolve) and officer endpoints (add + waive/resolve);
  sync wired into document upload + delete; the admin detail serializer exposes
  the live open queue. **Backend only** — the student Action Centre UI is S4.

## What Went Well

- **Generation falls straight out of the verdict.** Because S1's verdict already
  emits structured `{code, params}` unresolved items, the ticket generator is a
  thin map + reconcile — no new analysis. The whole sprint reused the verdict
  as its single source of truth.
- **Idempotency by construction.** A partial `UniqueConstraint` on
  `(application, code) WHERE source='system'` + an `IntegrityError` catch makes
  `sync` safe to call from anywhere (upload, delete, student GET, admin GET)
  without dedupe bookkeeping. The "no re-nag" rule is the same constraint doing
  double duty.
- **Real-data check matched the design first try:** Theresa → exactly 2 tickets
  (STR upload + add 2 subjects); the three excluded codes produced none.

## What Went Wrong

1. **A throwaway-preview field-name bug (`name_match` vs `vision_name_match`)
   silently produced no output.** *Symptom:* the preview test wrote no file; the
   `cat` failed. *Root cause:* `ApplicantDocument`'s match column is
   `vision_name_match`; I passed `name_match=` straight to `create()`, which
   raised `TypeError` and aborted before the write — masked by `>/dev/null`.
   *Why it didn't hit the real tests:* the real test helper maps
   `name_match → vision_name_match` explicitly. *Fix:* throwaway-only; corrected
   the kwarg. Not promoted to a lesson (the real tests already use the right
   field; this was scratch-code sloppiness, not a systemic gap).
2. **One real-test omission:** `test_no_renag_…` asserted on a ticket before
   calling `sync` to create it → `DoesNotExist`. Caught on the first run, fixed
   by adding the missing `sync` call. Cheap, no system change warranted.

## Design Decisions

See `docs/decisions.md` (this sprint): the resolution-ticket model — idempotent
verdict-driven generation, the no-re-nag rule, the three deliberate exclusions,
and officer items as the structured successor to `info_request_note`.

## Numbers

- Backend tests: **1490** (was 1481; +9). Frontend jest: 183 (unchanged — backend-only sprint).
- Migration: **`0036_resolutionitem`** (created on branch; prod migrate-first at deploy).
- Files: ~12 (model, migration, `resolution.py`, serializers ×2, views ×2, urls, RLS, tests, CHANGELOG, plan).
- New TD: **TD-079** (sync writes on GET; a deleted compulsory doc doesn't resurface a resolved ticket).
- Scholarship suite 454; full backend 1490; no deploy.
