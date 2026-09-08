# Retrospective — Vircle Airtable V1: the two webhooks (2026-09-09)

## What shipped
The data path that retires the typed eWallet ID, both directions, backend only, no migration:
- `vircle_airtable.py` — `recipient_payload` / `push_recipient` (outbound, best-effort, stamped
  on the resolution item) and `_match_application` / `apply_update` (inbound).
- The push rides the student's Action-Centre "installed" confirmation in `views.py` — the agreed
  moment Vircle is told WHO (the student may register with a different mobile than the
  application's, so award-time would be too early).
- `VircleAirtableUpdateView` at `POST /api/v1/internal/vircle/airtable/` — X-Vircle-Secret,
  constant-time, inert while unset; mirrors CronRunView. Always 200 on a matched-or-not payload
  so Vircle's automation never retry-storms over our data questions.
- Settings: `VIRCLE_AIRTABLE_PUSH_URL` + `VIRCLE_AIRTABLE_SECRET`, env-only (both are secrets —
  Vircle's guide treats the webhook URL itself as the credential).
- 17 tests in `test_vircle_airtable.py`; two guards bite-checked (overwrite guard, empty-secret
  refusal) with the injection verified as landed and the suite verified GREEN after restore.

## The decisions that must not be tidied
1. **A stored `vircle_id` is never overwritten by the webhook.** Mismatch → ERROR log, human
   resolves. The 2026-07-30 audit-line lesson taught that this field's changes need witnesses;
   an automated overwrite is a change with no witness at all.
2. **The inbound value still passes `valid_vircle_id`.** Vircle is authoritative for WHICH
   wallet, not exempt from the format gate — a mis-keyed Airtable cell must not become a
   payment destination.
3. **Matching is by NRIC digits, restricted to `VIRCLE_SETUP_STATES`.** A webhook row can never
   write onto a rejected or expired file, whatever it claims.
4. **The push is best-effort by the usage-meter contract** — fault-injected: a dead webhook
   leaves the student's confirmation fully successful, and the failure is visible in
   `params.airtable_push` rather than in nothing.

## Lessons applied (from docs/lessons.md, named at sprint-start)
- Env vars read into settings (`base.py`), never bare `getattr` on an undefined name — the
  `CHECK2_AUTO_GENERATE` class.
- The inbound endpoint is tested THROUGH THE URL with the secret on — the 2026-08-18
  view/service-seam lesson.
- Bite-checks restore by writing the original bytes back, and the suite is re-run to GREEN
  after each restore — the 2026-09-08 restore-missed lesson.

## Known limits (accepted, recorded)
- Rishvin (#114): his Vircle account is under his father's IC → inbound `no_match`, human
  reconciles. Named in the module docstring.
- V1 changes nothing a student sees. The wallet-id box, the 48h activation email and the relay
  sheet all keep running — V2 retires the student-facing half once the webhook pair is proven
  live with Gokula.

## What V2 owes
Remove the wallet-id box from the Action Centre (mobile stays); retire the 48h activation email;
keep the relay sheet (owner: mirror, keep for now); update the reviewer Guide/FAQ in the same
change (house rule); en/ms/ta copy for the shortened task.
