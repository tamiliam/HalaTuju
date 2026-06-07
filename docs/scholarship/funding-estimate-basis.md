# Funding-estimate basis — per-pathway B40 expense figures

**Status:** Owner-validated as "ballpark" (2026-06-08). Figures are RM, grounded in 2025
Malaysian costs. This is the **source of truth** for `apps/scholarship/funding_estimate.py` —
tune the numbers here and in that module together.

## Why estimate instead of ask

Pre-college students can't reliably self-report funding need — they haven't been there yet.
So we estimate the realistic **gap a scholarship would fill, *after* the government's own
coverage**, from the student's pathway. Their funding checkboxes stay a *signal*, not the
baseline. Since applicants are B40, even small monthly sums matter.

## Per-pathway figures (RM)

Ranges are low–high. "Monthly" = recurring; "one-off" = one-time (device, registration).

| Pathway | Govt covers | Monthly gap | One-off | Notes |
|---|---|---|---|---|
| **matrik** (Matrikulasi KPM) | Hostel + teaching free; BSHP ~RM1,250/sem (≈RM250/mo) for food+transport | meals/personal **100–150** | device **1,800–2,500**; registration **546–599** | Best covered. Gap is mostly a device + small top-up. |
| **asasi** (public-uni foundation) | Heavily subsidised; hostel usually provided; some programmes fully borne incl. allowance | meals **150–250**; transport **0–50** | device **1,800–2,500**; registration/tuition **0–1,000** (varies by uni) | Registration/tuition varies — confirm per uni. |
| **stpm** (Form 6, lives at home) | School + STPM exam fees free — little else | transport **100–300**; tuition **200–400**; books **25–50** | device **1,800–2,500** | Highest monthly need; transport (daily travel) is the big one and varies with distance → still worth asking the actual number. |
| **poly_diploma** (Politeknik / Kolej Komuniti / TVET-residential / diploma) | Tuition RM200/sem; hostel cheap & provided | meals **150–300**; misc **20–50** | device **1,800–2,500**; registration+misc **600–900** | Hostel provided but meals are the recurring gap. |
| **pismp** (IPG teacher training) | Allowance + hostel (like matrik) | top-up **50–150** | device **1,800–2,500** | Well covered by the IPG allowance. |
| **degree / university** | Varies widely (PTPTN, faculty) | living **300–600** | device **1,800–2,500**; registration **varies** | Uncommon straight from SPM; flag for officer review — varies too much to trust the estimate. |
| **unknown / undecided** | — | — | — | Pathway not yet chosen → **no estimate**; fall back to the student's checkboxes + ask. |

**Device (all pathways):** budget laptop RM1,800–2,500 new (~RM800–1,200 refurbished). One-off.

## Classification

Read the pathway in priority order:
1. `chosen_pathway` when `pathway_certainty == 'sure'` (authoritative).
2. else `intended_pathway`.
3. else a single value in `pathways_considered` (if exactly one).
4. else **unknown**.

Value → category map: `matric→matrik`, `asasi→asasi`, `stpm→stpm`,
`poly`/`kkom`/`iljtm`/`ilkbs`/`diploma`→`poly_diploma`, `pismp`→`pismp`,
`university`/`degree`→`degree`, anything else / blank → `unknown`.

## Sources

- Matrikulasi BSHP + fees — hargaterkini.my/yuran-matrikulasi, afterschool.my matrik aid
- Asasi — malaysia.gov.my foundation programmes, UPM Asasi (fully-borne example)
- STPM — tabung.my/pendidikan/stpm/kos, infokolej.com yuran tingkatan 6
- Politeknik — themalaysiamirror.com kos politeknik
- Laptop prices — press.com.my student laptops 2025

## Revisit if

- A pathway's government coverage changes (e.g. BSHP rate, matrik registration).
- Real award data shows the estimate is consistently over/under for a pathway.
- A new pathway value appears in `chosen_pathway` that isn't mapped above.
