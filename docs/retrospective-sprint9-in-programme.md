# Retrospective — B40 Phase E/F Sprint 9: Student in-programme results + progress + graduation relay (F9a)

**Date:** 2026-06-09
**Branch:** `main` (held local, not pushed — deploy owner-gated; ships dark behind `SPONSOR_POOL_ENABLED`)
**Migration:** `0053` (two new models: `SemesterResult`, `GraduationMessage`)

## What Was Built

The backend for the in-programme student lifecycle — the data + the anonymity-preserving graduation relay. Backend-only;
the student/sponsor UI is F9b (Sprint 10).

- **New module `apps/scholarship/in_programme.py`** owns the writes (one-way import `in_programme → pool → models`, so no
  cycle with the allowlist serializer). Errors are an `InProgrammeError(code)` mapped to a 400 `{code}`.
- **Semester results → real progress.** New `SemesterResult` model (semester, cgpa 0.00–4.00, graduated, optional
  myNADI-only `results_slip` link). `record_semester_result` gates on `status='sponsored'` (`not_in_programme`) and
  validates CGPA (`bad_cgpa`). **`pool.derive_progress_state` is now REAL** — derived from the latest `SemesterResult`
  (`graduated` > CGPA≤2.00 `needs_attention` > a CGPA `semester_completed` > else `on_track`). Single source of truth, no
  stored column to drift; the uploaded slip stays myNADI-only, only the coarse band crosses.
- **18+-only promotional consent.** New `promotional_use` consent via `grant_promotional_consent` — a hard server-side
  18+ gate (`is_minor` from the NRIC → `minor_not_allowed`), **no guardian path** by design; `CONSENT_VERSION` bumped
  `2026-draft-4` → `2026-draft-5`. Withdrawable (PDPA).
- **Graduation thank-you relay.** New `GraduationMessage` model. `submit_graduation_message` runs
  `pool.scan_anon_for_identifiers` as a STRUCTURAL gate — a message leaking the student's own
  name/school/city/NRIC/phone/email is saved `blocked` (with the offending fields), a clean one is `pending`; staff
  approve (re-scanning any `scrubbed_text` edit → `scrubbed_leak`) or reject. Approved messages surface to the funding
  sponsor via a plain allowlist `GraduationRelaySerializer` ({ref, text, approved_at}) linked ONLY to the anonymous
  `pool.pool_ref` — never identity, never a reply channel.
- **Endpoints:** student `semester-results/`, `promotional-consent/`, `graduation-message/`; admin
  `graduation-messages/` + `.../<id>/review/` (reviewer/super); sponsor `graduation-messages/` (flag + approved gated).

## What Went Well

- **No import cycle by construction.** Keeping the progress *read* (`derive_progress_state`) in `pool` reading the model
  directly, and all *writes* in `in_programme` (which imports `pool`), meant the allowlist serializer never gained an
  `in_programme` dependency. The direction was decided up front, so there was nothing to untangle later.
- **Reused the existing safety primitive.** The relay didn't need a new scanner — `pool.scan_anon_for_identifiers`
  (built for the anon-blurb publish gate) is exactly the right structural check, and re-scanning the staff `scrubbed_text`
  closes the "staff edit reintroduces an identifier" hole cheaply. The leak test plants the student's own name/city and
  asserts the relay output carries nothing (allowlist-by-construction, lesson #107/#108).
- **The S8 stub tests survived the real derivation.** `TestProgressState`'s `none_until_sponsored` /
  `on_track_when_sponsored` still hold (sponsored + no result → `on_track`), so I *extended* the class with the new bands
  rather than rewriting — the stub was designed to forward-fit, which paid off.
- **Full-suite run caught the only drift immediately** (see below). 935 scholarship + 1051 courses/reports green.

## What Went Wrong

- **The `CONSENT_VERSION` bump broke one test that hard-coded the old version string.** *Symptom:*
  `test_complete_onboarding_records_consent_and_stamps` asserted `c.version == '2026-draft-4'`; bumping to `-5` failed it.
  *Root cause:* the test pinned a literal version, so any future bump is a guaranteed (unrelated) failure — the same
  class as lessons #48/#131 (a change to shared state breaks an earlier sprint's test). *System change:* fixed it to
  assert against `services.CONSENT_VERSION` (the constant), so the test now verifies "the recorded consent uses the
  current version" — true across every future bump — instead of a brittle literal. Captured as a lesson. Surfaced only
  on the FULL suite, never on the new-tests-only run — reinforcing the run-the-whole-suite rule.

## Design Decisions

- **`SemesterResult` as a new model, not an overload of the SPM `results_slip`.** The in-programme university semester
  result is a different fact from the application-time SPM slip the academic engine parses; giving it its own table keeps
  one fact per home (lesson #51) and avoids reusing one doc-type's signal for another purpose (lesson #124). The slip is
  an optional FK (myNADI-only evidence), not the source of the CGPA. Logged in decisions.md.
- **`progress_state` derived, never stored.** Keeps a single source of truth and means F2's sponsor card needs no
  backfill and can't drift from the results pipeline. Logged.
- **18+ promo consent has no guardian path** (owner decision 2026-06-09) — enforced structurally (`is_minor` raises),
  not by a UI checkbox. A minor literally cannot record it.
- **Relay rejects on scan, re-scans the staff edit, and exposes only `{ref, text, approved_at}`** via a plain
  `Serializer` — three independent guards (student-submit scan, staff-edit re-scan, allowlist serializer) so no single
  miss leaks identity.

## Numbers

- **Backend:** 935 scholarship (+26) + 1051 courses/reports = **1986 pytest** green. Migration `0053` applies locally;
  `makemigrations --check` clean; `manage.py check` clean.
- **Frontend:** untouched (backend-only sprint) — 283 jest unchanged; no `next build` needed.
- **Files touched:** ~14 (models, `in_programme.py` [new], pool, services, serializers ×2, views ×3, urls, 2 test files
  [1 new], migration `0053`) + close docs.
- **Deploys:** 0 (held; ships dark). **Carried:** TD-102 (migration `0053` contenttypes workaround + RLS at deploy),
  TD-103 (results-slip OCR auto-fill deferred — CGPA student-entered).
