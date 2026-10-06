# Retrospective — Sprint 15.1: Requests v1.1 (2026-07-24)

Brief: `docs/plans/2026-07-24-sprint15-1-requests-v11-brief.md`. **Status: SHIPPED + DEPLOYED +
LIVE 2026-07-24** — commits `b2a842cd`..`54b5fbbf`, both Cloud Builds SUCCESS for `54b5fbb`,
migrations `scholarship/0113`+`0114` applied migrate-first with RLS, smoke green,
`REQUESTS_ENABLED=1` held throughout (additive to the already-live Sprint 15 feature — no dark
period, no flag flip needed).

## What Was Built

Three additive extensions to the live Requests space:

1. **Role-correct component choices.** Sprint 15 shipped the request-component dropdown with
   `students` and `course_data` in it — surfaces an org_admin can never actually reach (they are
   super-only, both in the FE nav and enforced by backend 403s). 15.1 removes them and rebuilds the
   choice set around a single source of truth, `models.REQUEST_COMPONENT_TREE`:
   `org_requests.VALID_COMPONENTS` and the model field's own `choices` are both derived from the
   tree, and the FE mirror (`requestStatus.REQUEST_COMPONENT_TREE`) plus the en/ms/ta i18n key sets
   are pinned to it by consistency tests (pytest: tree ↔ i18n×3 ↔ `VALID_COMPONENTS` ↔ model
   choices; jest: FE mirror ↔ i18n×3).
2. **Two-level B40 sub-component selector.** `applications` gained 8 `applications_*`
   sub-components (`_student_details`, `_documents`, `_ai_prediction`, `_queries`, `_interview`,
   `_decision`, `_agreement`, `_student_profile`) — stored in the SAME `component` varchar(30)
   column with an underscore separator, because a dot separator would be misread by the nested i18n
   lookup helper as a path split. The FE submit form is a dependent select (the PathwayPicker
   pattern: child keyed on parent, cleared on parent change). Migration `0113` is choices-only — no
   DDL, `sqlmigrate` is a no-op.
3. **Org-fenced screenshot attachments (resolves TD-172).** New `OrgRequestAttachment` model
   (migration `0114`, table `org_request_attachments`, RLS enabled). Bytes go browser→Supabase
   directly via a signed URL, never through Django (Rule 5) — storage key
   `requests/<org_id>/<request_id>/<uuid>` via the new `storage.build_request_attachment_key`, with
   `resolve_org_for_path` extended to resolve the org off this new scheme for the download fence.
   Three endpoints on `_OrgRequestsBase` (sign-upload / record / delete), org-fenced and classified
   in `test_org_fence.py`; images-only (no pdf), ≤5 per request, ≤8MB each, count-capped at both
   sign and record time. FE: a staged picker on the submit form (upload after create; a post-create
   upload failure is a non-blocking warning, not a form error) plus inline add/remove on the detail
   page while the request is non-terminal. The AI review prompt notes "ATTACHMENTS: N image(s)" when
   present on a re-run (the initial AI run always predates any upload, by construction — documented
   in `_build_review_prompt`, not treated as a bug).

## Went Well

- **The consistency-test pattern caught exactly the class of bug it was built to prevent, before
  shipping.** Deriving `VALID_COMPONENTS`/model choices/FE mirror/i18n keys all from one tree and
  testing the derivation meant there was no place left for a "looks right, isn't reachable" value to
  hide — see "What Went Wrong" below for the bug this generalises from.
- **The attachment security invariants were each individually test-proven**, not asserted as a
  group: foreign-path rejection, count cap at BOTH sign and record (a second upload can land between
  the two calls), images-only (no pdf), cross-org signed URL → None, cross-org delete → 404,
  flag-off → 404 on every new route. Six separate assertions for one feature, each with its own
  test, rather than one broad "security is fine" test.
- **The attachment namespace decision (new `requests/` prefix, not the applicant-document vault)
  kept the blast radius small.** Reusing the proven signed-URL PATTERN while isolating the new use
  case in its own storage key scheme and table meant zero risk to the existing scholarship-applicant
  upload path, and TD-172 closes without a speculative "general attachment store" being built for a
  single use case.
- **Additive-only, no dark period.** Because Sprint 15 was already live and both 15.1 migrations are
  additive (choices-only + a wholly new table), there was no flag-flip decision to make and no
  window where the feature was half-shipped — old and new code both work against the schema at every
  point in the deploy sequence.

## What Went Wrong

1. **The Sprint 15 dropdown shipped with two unreachable options.**
   - *What happened:* the original `component` choices included `students` and `course_data` —
     values an org_admin submitting a request could select in the form, but which correspond to
     super-only admin surfaces the same org_admin can never actually view or act on. The choice list
     was cosmetically correct (valid strings, no crash) but semantically wrong for who was filling
     the form in.
   - *Why it happened:* the choices were derived from the FULL admin navigation — every module the
     admin app knows about — rather than from the SUBMITTER'S role-scoped view of the product. Sprint
     15 built the component list by enumerating "what modules exist" instead of "what can the person
     filling this form actually see".
   - *What system change prevents recurrence:* the new consistency test doesn't just check that the
     tree, i18n, `VALID_COMPONENTS`, and model choices agree with EACH OTHER — the tree itself was
     rebuilt from a role-verified pass (FE nav + backend 403s) before any of those consumers were
     regenerated from it. The generalisable lesson: when a choice list is meant to represent "what a
     specific role can act on", derive it from a role-verified surface census, not from a full
     capability inventory — and once derived, pin every consumer to the SAME single source so a
     future change to reachable surfaces can't drift back out of sync one consumer at a time.

## Design Decisions

- **Underscore separator for hierarchical component values** (not a dot) — a dot breaks the nested
  i18n lookup, which splits keys on `.`. Logged in `docs/decisions.md`.
- **`REQUEST_COMPONENT_TREE` as the single authored source, with derivation tests** rather than
  hand-enumerating the choice list in each of model/service/FE/i18n independently — the direct fix
  for the root cause above. Logged in `docs/decisions.md`.
- **Attachments live in a NEW `requests/` storage namespace**, reusing the signed-URL pattern rather
  than the applicant-document vault or a fully general attachment store — the narrowest correct
  resolution of TD-172 for a single new attaching model. Logged in `docs/decisions.md`.
- **Images-only, capped at 5** — the stated use case is "a screenshot resolves ambiguity in one
  glance"; pdf/other formats are out of scope for v1. Logged in `docs/decisions.md`.

## Numbers

- **Commits:** `b2a842cd`..`54b5fbbf` (components+sub-components, attachments backend,
  attachments frontend, CHANGELOG).
- **Migrations:** exactly 2 — `scholarship/0113` (choices-only, no DDL) + `scholarship/0114`
  (`CREATE TABLE org_request_attachments` + indexes + FKs + RLS) — both applied migrate-first with
  RLS enabled.
- **Tests:** pytest 4458 → **4486** (0 fail, 0 skip); jest 712 → **719** (+1 known pre-existing
  local-Node-26 failure, TD-171, held constant).
- **Serializer surface:** org-visible payload 19 → 20 keys (`attachments`), deliberately widened
  and caught by the exact-key-set snapshot test; `ai_*`/`triage_*` leak tests still green.
- **Cloud Builds:** SUCCESS for `54b5fbb` (both api + web where path-filtered).
- **Technical debt:** TD-172 resolved; TD-173 logged (HEIC/HEIF accepted in the attachment
  allowlist but not auto-converted to JPEG — the Supabase-direct signed-URL upload path has no
  Django-side hook to run the existing `imaging.convert_heic_to_jpeg`, unlike `ApplicantDocument`
  uploads which are Django-mediated; low priority, most screenshot uploads are PNG/JPEG).

## Carry

- **Owner (unchanged from Sprint 15):** brief BrightPath org admins on the Requests space + rate
  card; monitor the first real requests as they arrive.
- **ms/ta first-drafts to review** — now including the new component/sub-component/attachment
  strings, on top of the Sprint 15 backlog.
- **Sprint 7** (per-org timing/reminders/consent version) stays GATED to ≈21 Aug 2026 by the
  Phase-2 rule-stability clock — unaffected by this sprint.
