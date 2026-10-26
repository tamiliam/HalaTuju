# Retrospective — Corpus gaps C1 + C2: a known public TVET issuer reads "not checked"; UiTM scores as a public university (2026-10-26)

C1: `1a2b4962` (the net) + `95131a65` (narrowed after review) — live as api-01144-sfg / web-00988-nhg.
C2: `1accaab9` (UiTM) + `a781b49a` (digital PDFs; the officer hold) — live. Built in the worktree
`ai-outage` against the owner-approved roadmap `docs/plans/2026-10-25-document-corpus-gaps-roadmap.md`
(decisions A–D), from the brief of org request #47. Decisions: `docs/decisions.md` 2026-10-26 (owner
rulings A, B, C). Register: TD-406 raised.

## What Was Built

- **C1 — "not checked" (MODEL_VERSION 1.8.0).** A suspect-band offer (0.35–0.70) with offer wording,
  from an issuer on a closed list named on its letterhead (Belia & Sukan / IKBN / IKTBN / ILKBS; MARA /
  TVETMARA / IKM / KKTM / Kolej MARA / Kolej Profesional MARA; JTM / ADTEC / ILP / JPK), is stored
  `unchecked` (`genuineness/offer_issuers.py`, `bands.NOT_CHECKED`). Every reader takes it as no signal:
  no ladder step (TD-114 holds Probable), `offer_official_status` `unknown` (no block, no
  official-document request), no student chip; the officer's Pathway card says "not checked — check
  it by eye" (`offer_issuer_not_checked`, en/ms/ta). TVET pathways join the tertiary family (ruling B);
  KPTM and UniKL are MARA-owned but private (ruling C). A private college gets an honest "private
  college / university (IPTS)" reason. `VERDICT_ENGINE_VERSION` 2026-10-26.1.
- **C2 — UiTM (MODEL_VERSION 1.8.1, 1.8.2).** UiTM's own offer line (kept whole: "…program di UiTM"),
  office and summons join the public-university family; on a digital PDF's text layer (no letterhead)
  UiTM's own clauses that name it count as the university's name. All seven real letters (OCR and
  text layers) genuine; the 95 cached offers unchanged.
- **The officer's request.** A "not checked" upload no longer closes an officer's own official-offer
  request: it is held for the officer (`needs_officer_eye` — the existing "our team is checking this
  personally" card) until closed by hand.

## What Went Well

- **Real data before and after, read-only.** Every scorer change was run against the 95 cached offer
  OCR texts and the seven UiTM letters before and after (no API call), so "every other family
  unchanged" was a diff, not a claim. C2's own finding — "Mod Pengajian" sits on 29 of the 95 — came
  from that run and kept a non-specific signal out.
- **Every guard was bitten**, including one fault per review guard and the whole module put back to
  its pre-review version (all the review's probes then failed).
- **The frozen record stayed frozen.** The 1.7.0 rule (`_pre_c1`) and the 1.8.0 university list are
  restated in the tests, so each version's change is pinned as a diff against the one it replaced.

## What Went Wrong

1. **C1's first net excused pages that are not offers at all.** It turned ANY sub-genuine score naming
   a listed body into "not checked" — a typed fake headed "ILKBS" at p=0.00, a JPK skills
   certificate, a MARA loan letter, a page reading only "JTM", a private college "Tajaan Majlis Amanah
   Rakyat". Each would have read Probable and closed the officer's official-offer request. *Root
   cause:* the net was specified by what it should EXCUSE (a genuine TVET letter the model reads as
   suspect) and tested only on that; nobody asked what else carries those names. The owner's ruling
   was for a genuine-looking letter, and the code did not encode "genuine-looking". *System change:*
   the net now needs the suspect band, offer wording, a letterhead issuer, a short acronym only beside
   offer wording, and never a sponsor line; the five probes are regression tests scoring exactly as at
   `7d0f013a`; lesson recorded (an exception is specified by what it must not excuse).
2. **C2's first fix missed digital PDFs.** UiTM letters were verified on their OCR texts; production
   reads a digital PDF through its text layer, which has no letterhead, so two letters still reached
   only suspect 0.60 and would have kept the block. *Root cause:* "the document" was taken to be one
   text; a document reaches the scorer by more than one reading, and only one was checked. The brief
   even noted the text-layer score, and the builder filed it as "a note, not a blocker". *System
   change:* UiTM's own naming clauses (never the copyable offer line) carry the name; the check now
   runs on every reading we hold (OCR + text layer); lesson recorded.
3. **A reviewer's claim was wrong, and was disproved by a test before any code moved.** The C2 review
   said the held officer request gets `attempts=1` (so the Action Centre shows "isn't the page we
   asked for"). A throwaway probe showed the stamp never reaches an officer request: the counter and
   the circuit-breaker find requests by system / Check-2 code, and an officer's is `officer_N`. The
   real defect sat beside it — the upload answered `pending`, which the student reads as "still
   checking — refresh" — and that was fixed instead (the existing officer-hold card). *Root cause of
   the near-miss:* a plausible reading of the call order, not a run. *System change:* none new — the
   existing lesson "verify each finding's failure reproduces before fixing it" held; the non-stamp is
   pinned by a test.

## Review (sprint-close step 4b)

No `/code-review`, by the coordinator's instruction: two review rounds per sprint plus a read of 107
real offer texts by the lead, each answered in the worktree. C1 round 1: the net's breadth (blocker),
the UiTM text-layer "private college" reason, and owner ruling C. C1 round 2: nothing blocks; the
officer-request follow-up (taken into C2). C2 round 1: digital PDFs; the student-facing hold copy.
C2 final: nothing blocks; TD-406 raised.

## Numbers

- API (`python -m pytest -q -n auto -p no:cacheprovider`): 8,815 → 8,839 (C1) and 8,848 → 8,865 (C2)
  passed / 3 skipped in the worktree; combined on main 8,848 (C1, lead).
- Web (lead): 287 suites / 4,543 jest after C1; C2 changed no web file.
- No migration. MODEL_VERSION 1.7.0 → 1.8.2; VERDICT_ENGINE_VERSION 2026-10-26.1.
