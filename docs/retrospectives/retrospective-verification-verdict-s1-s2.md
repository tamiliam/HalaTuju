# Retrospective — Verification Verdict roadmap, Sprints 1 & 2 (2026-06-02)

Branch: `feature/verification-verdict` (committed, **not pushed** — held until the
roadmap is further along, per the push-deploy rule). Plan:
`docs/scholarship/verification-verdict-plan.md`.

## What Was Built

**The problem.** The coordinator opened a shortlisted application to *scattered*
signals — Vision chips per document, a flag list, eight raw uploads — and had to
re-assemble the picture in their head. The intelligence existed; the *synthesis*
didn't. (Driven by a real session reviewing Theresa Arul Mary A/P A.Philips.)

**Sprint 1 — Verdict engine + officer scorecard.** New deterministic
`verdict_engine.py` rolls the existing signals (Vision matchers, doc-assist,
completeness, anomaly engine) into ONE four-fact verdict the coordinator
*audits*: **Identity / Academic / Income / Pathway**, each with a status
(`verified` / `review` / `recommend` / `gap`) + evidence + unresolved lists.
Surfaced as a scorecard card on `/admin/scholarship/[id]` above the Pre-interview
flags. `AdminApplicationDetailSerializer.verdict` (mirrors `anomalies`). No
migration. 23 tests; i18n `admin.scholarship.verdict.*` × en/ms/ta.

Design rules encoded: **green is expensive** (under-claim); **resolve before you
escalate** (an OCR name truncation — IC tokens a subset of the typed name — is
settled silently, never raised); **income green needs a verified STR document**,
not the self-declared flag; **address is a coherence test** (only a state-level
divergence escalates).

**Sprint 2 — Grade OCR + academic verification.** Results-slip extractor now
reads `results: [{subject, grade}]`. New `academic_engine.py` runs
**completeness** (every slip subject entered) and **accuracy** (typed grades match
the slip) by *normalised subject name*. Academic reaches `verified` when the slip
is the student's, complete, and accurate. No migration (grades in `vision_fields`).
12 tests.

## What Went Well

- **~80% reuse.** The hardest logic already existed; both sprints were mostly
  *composition*. `_ic_identity_blockers` (the consent gate) became the Identity
  signal source, so the verdict and the gate can't disagree.
- **Real-data validation at each close.** A throwaway preview ran the real engine
  on Theresa's actual stored signals → Identity *Verified* (name truncation
  auto-resolved), Income *Recommend* (STR claimed, no letter), Academic "8 of 10,
  missing Moral + Tamil Literature" — matching the hand-analysis exactly.
- **Completeness works on legacy data.** `read_slip` supports the old
  `subjects`-only shape, so the 8/10 check fires on existing applicants with no
  re-OCR; only accuracy needs the new extraction.

## What Went Wrong

1. **The extraction-shape change nearly broke the document display silently.**
   *Symptom:* changing the results-slip schema from `subjects: [name]` to
   `results: [{subject, grade}]` would have made the generic admin field renderer
   (`Array.isArray(v) ? v.join(', ')`) print `[object Object]`.
   *Root cause:* the renderer assumed array elements are strings; an extracted-JSON
   shape change has a hidden frontend display consumer.
   *Fix (system):* lesson added — when changing a doc-assist/Gemini extraction
   shape, grep the renderer(s) of `vision_fields.fields` and handle the new element
   type in the same change. Caught here before commit; the renderer was updated in
   the same diff.

2. **Two throwaway-preview path bugs cost a couple of re-runs.** *Symptom:* the
   preview test couldn't find `halatuju-web/src/messages/en.json` (wrong number of
   `dirname()` hops — the web folder is a *sibling* of `halatuju_api`).
   *Root cause:* eyeballed the relative depth instead of deriving it.
   *Fix:* minor; throwaway-only. Noted, not promoted to a lesson (not cross-cutting).

## Design Decisions

See `docs/decisions.md` (this sprint): verdict as a deterministic rollup (not a new
AI pass); academic comparison by normalised subject name; income green gated on a
verified STR *document*.

## Numbers

- Backend tests: **1481** (was 1446; +23 S1, +12 S2). Frontend jest: 183 (unchanged).
- `next build` clean (both sprints). i18n parity 1701 (S1) → **1704** (S2) × en/ms/ta.
- Migrations: **0** (both sprints read existing signals / reuse `vision_fields`).
- Files: S1 ~7, S2 ~7. New modules: `verdict_engine.py`, `academic_engine.py`.
- Deferred: billable real-slip OCR smoke (user-run); subject-map duplication (TD-078).
