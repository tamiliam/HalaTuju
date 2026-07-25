# Institution is a must-fill fact — implementation roadmap

**Date:** 2026-07-25 · **Status:** approved 2026-07-25 · Sprint 1 shipped · Sprints 2–3 open
**Origin:** owner live review of #48 — "Institution is a must fill, as this is required in the
sponsor's portal as well."

---

## 1. The requirement (owner, 2026-07-25)

1. `chosen_programme.institution` must be **filled**, not resolved-at-read or fallen-back-to.
   It is sponsor-facing: `card_display.resolve_institution` returns `''` on a blank and the sponsor
   FE renders the line only when truthy, so an unfilled institution does not read as "—" to a
   sponsor — **the line vanishes from the card**.
2. The **Chosen programme** shows the course name **hyperlinked to its HalaTuju course page**, plus
   the **specialisation** for STPM / Matric / PISMP. Confirmed against the code as the general rule.
   The sponsor surface should hyperlink it too (today only the cockpit does).

## 2. Current state — verified, not assumed

**From `interviewing` onwards the institution is 100% filled: 53/53** (interviewing 4/4,
recommended 6/6, awarded 43/43). No sponsor is currently seeing a missing institution. The review
flow (`confirm_pathway` + a clean offer autofill) does get it there reliably — #48 is the one case
where the fill silently didn't happen and nothing noticed.

Every blank is pre-review, and they are **five distinct causes needing different answers**:

| Cause | Cases | Right answer |
|---|---|---|
| **Pre-U split** — the value sits in `pre_u_institution` only; the sponsor card (single-source, no fallback) can't see it | 8 — #19 #94 #124 #129 #140 #142 #144 (+#141 rejected) | Write the canonical college into `chosen_programme.institution` |
| **Genuine clash** — the offer names a different, usually private institution than the declared public course (#11 UPO vs UPNM · #64 i-CATS vs UPM · #86 Cyberjaya vs UMK · #113 UTAR vs UMK · #93 UniMAIWP vs UMK) | 5 | Nothing automated. `catalogue_institution` correctly refuses to write a conflict; a human decides |
| **Catalogue gap** — the course has ZERO `course_institutions` rows, so even a clean offer value can't be validated in (#132 UUM law · #136 UPSI education) | 2 | Catalogue data fix |
| **Real bug** — #48: `autofill_pathway_from_offer` bailed at the wrong-person guard on 2026‑07‑07 because the offer OCR read "LAKSMITHAA" for "LAKSMITHA"; the doubled-letter tolerance shipped 2026‑07‑08 and the function has never re-run | 1 | Re-run (the tolerance is already live — verified: `_name_status` now returns `match`) |
| **No offer on file yet** | ~14 shortlisted | Catalogue-unique fill works for single-campus |

### Why the institution is blank at all (root cause)

The apply-form programme picker stores `{course_id, course_name, field_key}` and **never an
institution** (`lib/scholarship.ts` — reasonable: it is a programme list, and a multi-campus poly
course has no single campus to pick). All 24 blank cases carry no `source` key, i.e. every one is a
student's own pick. The only writers that fill it are `confirm_pathway`,
`autofill_pathway_from_offer`, and the POLY-only read-time `poly_institution_from_live_offer` — and
the autofill's institution merge sits **below four `return` guards about the PATHWAY**. That is the
same structural fault the 2026‑07‑23 sprint fixed for `reporting_date` by hoisting
`sync_reporting_date_from_offer` above them; the institution was left below. It is exactly why #48
shows a ticked reporting date and no institution: one letter, one function, one fact hoisted.

`offer_pathway.catalogue_institution` also **refuses to answer without a hint** ("With no hint it
can't verify → ''"). That guard is load-bearing for a multi-campus course, but for a course with
exactly ONE `course_institutions` row there is no ambiguity — filling a blank there is not swapping
one institution for another, it is the catalogue answering the question. #48's UB4213001 has one
row: Universiti Tun Hussein Onn Malaysia (Johor).

## 3. Design decision — a gate, not a periodic backfill

Because the review flow already reaches 100%, the durable fix is not to chase backfills but to make
the fill **impossible to skip**. `reporting_date` already works this way: QC cannot accept a case
without one, absolutely, because three things silently default off a missing date. The institution
now has a declared must-fill status with a sponsor-facing consequence, so it earns the same
treatment — plus a reviewer entry box, because an absolute gate is only fair when a remedy exists.

Two decisions, both **settled by the owner 2026-07-25**:

- **D1 — the QC gate is ABSOLUTE.** No override, exactly like the reporting-date stop: the honest
  remedy is to record the institution, not to wave the case through, and Sprint 2 ships the entry box
  that makes recording it easy. No override columns, one path. (Rejected: overridable-with-a-reason
  like the red-fact floor; and backfill-only with no gate, which would let the fill miss silently
  again as it did for #48.)
- **D2 — one format everywhere: the cockpit's grey ` · `.** The sponsor card drops its parens
  (STPM/Matric) and em dash (PISMP) in favour of `Title · Specialisation`. Standardising the other
  way was rejected on sight — parens nest badly on PISMP, whose bidang already carries its own
  ("Ijazah Sarjana Muda Perguruan (Bahasa Tamil Pendidikan Rendah (SJKT))").

---

## 4. Sprint roadmap (3 sprints)

### ~~Sprint 1 — the institution becomes a filled fact~~ ✅ SHIPPED 2026-07-25
Retro `docs/retrospective-2026-07-25-institution-must-fill-s1.md`; decisions ×2; lessons ×3.
`sync_institution_from_catalogue` (hoisted above every guard) + `sole_catalogue_institution` +
`offer_contradicts_course_institution` + the `backfill_institution` command. 4559 pytest, no
migration. **The data pass is owner-gated and NOT run** — 11 fillable rows (live #16 #42 #48 #49 #74
#97 #122 #145; rejected #7 #40 #139). **Sprint 2 must not ship before it runs**, or the QC gate
deadlocks live cases.

### Sprint 2 — it cannot leave review empty (the gate)
**Goal.** A case cannot reach `recommended` without an institution, and the reviewer has a one-box
remedy.

**Scope.**
- QC-accept precondition `institution_required` in `AdminQcDecisionView` (mirrors
  `reporting_date_required`; D1 decides absolute vs overridable).
- `AdminInstitutionView` (`POST .../<pk>/institution/`) + `services.set_institution_by_officer`
  with an AUDIT log line — mirrors `AdminReportingDateView` exactly, `_require_app_write` gated.
- Cockpit entry box in the reviewer window (`interviewing` / on a reopen), mirroring
  `showsReportingDateBox`; hidden when a value is already stored.
- Retire the cockpit's `pre_u_institution` display fallback (page.tsx:1268) once Sprint 1's data
  pass lands, so the cockpit and the sponsor card can no longer disagree.
- i18n en/ms/ta (ms/ta first-drafts).

**Files (~11).** `views_admin.py`, `services.py`, `urls.py`, `tests/test_qc_gate.py`,
`tests/test_org_fence.py` (classify the new endpoint), `page.tsx`, `officerCockpit.ts` + its test,
`en/ms/ta.json`.

**Acceptance.** QC accept refused with a blank institution · the entry box clears it and the accept
proceeds · endpoint org-fenced + classified · `interviewing`+ still 100% filled after the change
(i.e. the gate blocks nobody who is already through) · full suite green.

**Gating.** Do NOT ship before Sprint 1's data pass, or the gate deadlocks live cases.

**Complexity.** Medium. **This is the risky sprint** — it can block real QC accepts.

---

### Sprint 3 — sponsor surface parity (independent of 1 and 2)
**Goal.** A sponsor sees the programme as a link, formatted the same way the cockpit formats it.

**Scope.**
- A course-page href on the sponsor pool card + detail. **Allowlist care:** the sponsor
  serializers are plain allowlists with an exact-key snapshot test; a course link is
  non-identifying (hundreds of students share a course — the same class as `field_image_slug`) but
  must be added to the leak scan and the key snapshot deliberately.
- Specialisation punctuation per D2.
- Catalogue `course_institutions` rows for #132 (UUM law) and #136 (UPSI education) — a courses-app
  data fix, migrate-first if it needs one.

**Files (~8).** `serializers.py`, `card_display.py`, sponsor pool card + detail pages,
`tests/test_pool_anonymity.py`, `poolCard.ts` + test, i18n.

**Acceptance.** Link resolves for catalogue courses and pre-U picks · anonymity suite green with the
new field · exact-key snapshot updated deliberately · #132/#136 resolve an institution afterwards.

**Complexity.** Low–medium.

---

## 5. Sequencing, risk, and what is explicitly out of scope

- **Order:** 1 → 2 (hard dependency: gating before the data can be filled would deadlock QC).
  Sprint 3 is independent and can go before, between, or after.
- **Riskiest early?** No — inverted deliberately. Sprint 2 carries the live risk (blocking QC), and
  it is only safe once Sprint 1 has proven the data can be filled.
- **Out of scope:** the 5 genuine clashes stay a human decision; no change to award sizing, payment
  eligibility, or any verdict/band (this is a stored-display fact, not a means test); no new model,
  no new page.
- **Carry:** ms/ta first-drafts for every new string, as usual.
