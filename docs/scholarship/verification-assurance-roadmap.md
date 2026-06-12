# Verification Assurance — document genuineness + measured reliability (roadmap)

Approved 2026-06-12. Decomposed via `Settings/_workflows/implementation-planning.md`.

## Governing principle (applies to every sprint)
We do **not** claim certainty. For each document we compute a **"highly probable" genuineness
confidence from several independent fingerprints**, show the evidence (the marker checklist), and let
the **human review score the AI's per-fact call**. Soft throughout — never hard-blocks a submission;
the reviewer is the authority. **Threat model:** casual / wrong-document / typed-fake uploads from a
high-performing student population — NOT a determined forger (which OCR/AI cannot stop, and we don't
pretend to). The goal is to move the bar from *"a typed sheet passes"* to *"you'd need something that
genuinely looks like the real document"*, and to make reliability **measured**, not asserted.

Empirically validated on our real ICs (2026-06-12): genuine cards scored all 8 fingerprints
(KAD PENGENALAN / MALAYSIA / IDENTITY CARD / MyKad / WARGANEGARA + face + chip + physical-card look);
a typed-text fake carried only the words someone typed and failed every physical marker → `suspect`.
The **physical** markers (face, chip, card-look) are the strong discriminators; text alone is foolable —
hence "a few independent checks together".

## Scope (layers 1–3 + thin measurement). Deferred (owner's call): the full audit-trail VIEW, and verify-before-disbursement (money-gate).

## Coverage by document
| Document | Fact | Fingerprint strength | Sprint |
|---|---|---|---|
| IC / MyKad | Identity | Strong (validated) | 1 |
| SPM results slip | Academic | Strong (Lembaga Peperiksaan format) | 2 |
| Birth certificate | Income (relationship) | Strong (JPN format) | 2 |
| EPF / KWSP statement | Income | Strong (KWSP format) | 2 |
| STR / MySTR | Income | Strong (MySTR surfaces) | 2 |
| Salary slip | Income | Weak — varies by employer → best-effort | 2 |
| Offer letter | Pathway | Weak — varies by institution → best-effort | 2 |

The documents that matter most for eligibility are the standardised ones, so the fingerprint approach
is strongest where it counts; the two varied ones lean on name cross-checks + interview, not fingerprints.

---

## Status — ALL THREE SPRINTS SHIPPED & LIVE 2026-06-12. Programme (layers 1–3) complete.
Per-sprint detail now lives in the retrospectives; this file remains the durable governing-principle + coverage reference.

- **Sprint 1 — IC genuineness fingerprint** ✅ SHIPPED (`main` `29d5e7e`; flag `DOC_GENUINENESS_CHECK_ENABLED` ON; no
  migration). `vision.ic_genuineness()` → `vision_fields['authenticity']`; Identity caps at review on a suspect card;
  officer flags `ic_low_confidence`/`parent_ic_low_confidence`; honest student amber note. Retro `retrospective-ic-genuineness.md`.
- **Sprint 2 — standardised supporting docs + wrong-type** ✅ SHIPPED (`main` `4922003`; no migration).
  `vision.doc_genuineness()` for STR / results slip / BC / EPF; uniform `_apply_genuineness_caps` (Academic/Income,
  downgrade-only); officer flag `document_not_genuine`; shared `GenuinenessNote`. Retro `retrospective-doc-genuineness-s2.md`.
- **Sprint 3 — the scorekeeper (measured reliability)** ✅ SHIPPED (no migration, no backend change — TD-083 surfacing).
  `verdictReliability()` + `AiReliabilityCard.tsx` at the top of the B40 list: agreement = 1 − override rate per fact +
  overall, over the pre-existing `getVerdictMetrics()`. Retro `retrospective-verdict-scorekeeper.md`.

**Owner-deferred (not built):** the full audit-trail VIEW; verify-before-disbursement (the money-gate); the explicit
`officer_verdict.overall` accept/decline toggle (the unbuilt half of TD-083). Salary slip + offer letter remain
deliberately un-fingerprinted (too varied — name cross-checks + interview carry them).
