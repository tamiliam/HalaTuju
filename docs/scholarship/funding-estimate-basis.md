# Funding-estimate basis — per-pathway B40 expense figures

**Status:** Owner-validated from student interviews (2026-06-15). Figures are RM, grounded
in 2025 Malaysian costs. This is the **source of truth** for
`apps/scholarship/funding_estimate.py` — tune the numbers here and in that module together.

## Why estimate instead of ask

Pre-college students can't reliably self-report funding need — they haven't been there yet.
So we estimate the realistic **monthly shortfall an assistance top-up would fill, *after*
the government's own coverage (allowance) and any PTPTN loan**, from the student's pathway,
times the typical programme length. Their funding checkboxes stay a *signal*, not the
baseline. Since applicants are B40, even small monthly sums matter.

**It's an assistance, not a full ride.** We bank on the student also taking the government
allowance (matrik BSHP, IPG allowance) and the PTPTN loan where applicable; the estimate is
the gap *on top of* those.

**No device cost.** Support is paid out over time in small tranches, unsuitable for a
lump-sum device purchase — so device is deliberately excluded from the model.

## Post-SPM scope

Students can't enter a bachelor's **degree** directly out of SPM. The one exception is
**PISMP** (a 5-year, degree-level teacher-training programme — its own category). So the
pathway **"university" means a public-university (Universiti Awam) DIPLOMA**, not a degree.

## Per-pathway figures (RM)

Single **monthly shortfall** = monthly living costs − government allowance − PTPTN loan,
rounded. **Total** = monthly × months, rounded to the nearest RM100 (ballpark, not invoice).

| Pathway | After (govt covers) | Monthly shortfall | Months | ≈ Total | Notes |
|---|---|---|---|---|---|
| **stpm** (Form 6, lives at home) | Free schooling + STPM exam fees | **~500** | 18 | **~9,000** | Daily travel, meals, tuition classes. |
| **matric** (Matrikulasi KPM) | BSHP allowance (~RM250/mo), hostel & teaching | **~200** | 10 | **~2,000** | Best covered — mostly meals + small fees. |
| **asasi** (public-uni foundation) ⚠️ | Heavily subsidised; hostel usually provided; some fully borne | **~700** | 10 | **~7,000** | **Varies** by university (fees/hostel/allowance; arts vs science). Confirm. |
| **poly** (Politeknik diploma) | Cheap provided hostel + **PTPTN loan** | **~120** | 36 | **~4,000** | Mostly meals + misc. Practical term may add travel. |
| **university** (public-uni diploma) ⚠️ | **PTPTN loan** | **~220** | 30 | **~6,600** | **Varies** by university & field. Practical term may add travel. |
| **pismp** (IPG teacher training) | IPG allowance (~RM530/mo) + hostel | **~180** | 60 | **~10,800** | 5-year programme. Meals, hostel top-up, travel. Practicum may add travel. |
| **kkom / iljtm / ilkbs** | — | — | — | — | Different, institution-specific cost structure → **no estimate** (assess at interview). |
| **unknown / undecided** | — | — | — | — | Pathway not yet readable → **no estimate**; fall back to checkboxes + ask. |

⚠️ = `variable` flag (cost swings by institution/field — the cockpit shows a "confirm at
interview" caveat). Diploma duration spans ~24–36 months; 30 is the planning midpoint.
A student-stated `funding_need.programme_months` (whole years) overrides the default.

## Classification

Read the pathway in priority order (`classify_pathway`):
1. `chosen_pathway` when `pathway_certainty == 'sure'`.
2. else `chosen_pathway` / `intended_pathway` (older rows).
3. else the **chosen PROGRAMME** — the concrete course (e.g. auto-filled from the offer
   letter) pins the pathway even when the pathway-type fields are blank: `POLY-*` id →
   `poly`; a non-Politeknik diploma name (MOHE-coded id) → `university`; `Asasi…` → `asasi`;
   `PISMP`/`Perguruan` → `pismp`; `kkom`/`iljtm`/`ilkbs` ids or "Kolej Komuniti" → no estimate.
4. else a single value in `pathways_considered`.
5. else **unknown**.

Value → category map: `matric/matrik/matrikulasi→matric`, `stpm→stpm`,
`asasi/foundation→asasi`, `university/degree→university`, `poly/politeknik→poly`,
`pismp/ipg→pismp`. `kkom`/`iljtm`/`ilkbs`/`tvet` → unmapped → **no estimate**.

## Revisit if

- A pathway's government coverage changes (BSHP rate, IPG allowance, PTPTN policy).
- Real award data shows the estimate is consistently over/under for a pathway.
- We add figures for kkom / iljtm / ilkbs (currently un-estimated).
- A new pathway value appears in `chosen_pathway` that isn't mapped above.
