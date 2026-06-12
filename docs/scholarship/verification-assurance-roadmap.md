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

## Sprint 1 — IC genuineness fingerprint, end-to-end (the identity anchor)
- **Goal:** an uploaded IC gets a genuineness CONFIDENCE from its standard fingerprints, shown honestly,
  flagged to the reviewer when low, fed into the Identity prediction as a confidence (never auto-fails).
- **Scope:** new genuineness read on the IC (one Gemini multimodal call, **flag-gated `DOC_GENUINENESS_CHECK_ENABLED`,
  default OFF**); store the result in the existing `vision_fields['authenticity']` JSON (**no migration**);
  downgrade the over-confident IC "Match" badge to confidence-aware on the student page + cockpit; officer
  pre-interview flag (`ic_low_confidence`); student "upload a clear photo of your physical MyKad" nudge.
  Tests + i18n + **Stitch** (badge + flag). Builds the reusable machinery (confidence model, flag, badge
  pattern, anomaly flag, rollout playbook) on the riskiest single document.
- **Acceptance:** typed/fake IC → low confidence + flag + honest badge + nudge; genuine IC → "highly
  probable", normal badge; never blocks; dark behind the flag until prod-validated.
- **Complexity:** high (new IC AI call, two UI surfaces, Stitch). No migration (JSON storage).

## Sprint 2 — Fingerprints for the standardised documents + wrong-type
- **Goal:** the other key documents get the same confidence, folded into the AI reads they already get
  (~zero extra cost); a document in the wrong slot (the IC-in-STR case) is caught as wrong-type.
- **Scope:** add marker/`looks_official` fields to the existing extraction prompts (results slip, BC, EPF,
  STR, salary slip, offer letter); teach the STR path to recognise an IC/wrong-type; per-doc confidence +
  reviewer flags + honest "this is an IC, not an STR / upload the original" messaging; official-source
  preference (a plain typed letter = weak → interview). Each strong doc validated on our real files first.
  Tests + i18n. Reuses Sprint 1's machinery.
- **Acceptance:** IC-in-STR named as wrong-type (no phantom recipient); typed doc → low confidence + flag;
  genuine docs unaffected; zero extra Gemini calls on already-extracted docs.
- **Complexity:** medium.

## Sprint 3 — The scorekeeper (measured AI-vs-human reliability)
- **Goal:** every time a reviewer saves their four-fact Pass/Fail, capture what the AI had suggested, and
  compute the agreement rate — the measured evidence of reliability ("can you rely on it?").
- **Scope:** at verdict-save (the Decision panel), snapshot the AI's per-fact suggestion (Identity /
  Academic / Pathway / Income); store the (AI, human) pairs; finish/surface the parked `verdict-metrics` /
  `overall` (TD-083) as an agreement figure per fact + overall, in an admin view. Tests + i18n.
- **Acceptance:** after a handful of reviews, the admin sees "AI agreed on Identity X%, Academic Y%, …";
  no change to the reviewer's clicks beyond the silent capture.
- **Complexity:** medium.

---
**Total: 3 sprints.** Vertical slices; riskiest/highest-value first (IC — the validated headline fix);
cheap fold-ins next (share one mechanism); measurement last (scores predictions that are richer by then).
Flag-gated where billable; nothing hard-blocks; reviewer remains the authority.
