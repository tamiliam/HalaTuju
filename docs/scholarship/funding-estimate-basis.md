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
Every post-SPM figure below is unchanged by the 2026-11-07 degree work (owner decision 1).

## Degree (post-STPM) scope

Added 2026-11-07 (owner decisions 2-8; `docs/decisions.md`). Some gifts admit STPM-level students, so a
**degree-bound** student (`results_route.degree_bound`: the results route says DEGREE, or a no-id
programme named as a degree) is estimated as a degree **before** any stored pathway code is read. The
code can lag the course (#251 kept a stale `stpm`).

| Item | Figure | Constant (`funding_estimate.py`) |
|---|---|---|
| Living costs | RM1,200 a study month × **10 study months** a year | `DEGREE_LIVING_MONTHLY`, `DEGREE_STUDY_MONTHS_PER_YEAR` |
| Fee | flat **RM2,900/yr** (the SLS IPTA bachelor mean); `variable` caveat shown | `DEGREE_FEE_PER_YEAR` |
| PTPTN (IPTA bachelor maximum) | arts **6,180**, science **6,650**; any other stream → arts | `DEGREE_PTPTN_BY_STREAM`, `DEGREE_DEFAULT_STREAM` |
| Years | by name first: Perubatan / Pergigian (medicine, dentistry) **5**, Pendidikan **4**; then by stream: arts **3**, science **4**; else **4** | `DEGREE_YEARS_BY_NAME`, `DEGREE_YEARS_BY_STREAM`, `DEGREE_DEFAULT_YEARS` |
| Continuing | years left = years − (cohort year − course-start year), at least 1; start unknown → full length | `_years_done` |

Annual shortfall = 12,000 + 2,900 − PTPTN: **arts 8,720** (≈872 per study month), **science 8,250**
(≈825). Monthly = round(annual / 10); months = 10 × years left; total = annual × years left, rounded
to RM100. `variable` is true and `practical` false. The dict carries two extra keys:
`study_months: true` (the cockpit says "study months") and `continuing` (true when years were taken
off; the cockpit adds "Continuing student: estimated for the years left."). Example, #278 (UH6145006,
Pendidikan, arts): 872 × 40 study months, **RM34,900**.

The stream is read from `stpm_courses.stream` in one query. ⚠ The live column holds three values, not
two: `arts` 95, `science` 686 and **`both` 331**. `both` is read as "unknown": arts PTPTN and the
default 4 years, unless a name keyword applies.

The medicine keyword is matched as a phrase ("Doktor Perubatan", "Sarjana Muda Perubatan", "Doktor /
Pembedahan Pergigian", medicine, dentistry, dental surgery), so allied-health degrees whose names
contain "Perubatan" (Bioperubatan, Pengimejan Perubatan, Teknologi Makmal Perubatan) stay at 4.

PISMP ("Ijazah Sarjana Muda Perguruan") stays `pismp`, and a UA diploma stays `university`.
A degree-bound student is also sized at the RM2,000 bursary (decision 7, `award.py`) and is not
asked the STPM daily-travel question (decision 8).

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
| **degree** (public-university bachelor) ⚠️ | **PTPTN loan** (by stream) | **~872** arts / **~825** science per *study* month | 10 × years left | **~34,900** (arts, 4 yrs) | See *Degree (post-STPM) scope*. |
| **mara_diploma** (Kolej Profesional MARA / a MARA TVET diploma) ⚠️ | MARA education loan | **~220** | 30 | **~6,600** | Same numbers as `university` (decision 9). |
| **ilkbs** (IKBN / IKTBN) | Free tuition & hostel + ~RM100/mo allowance | **~350** | semesters × 6 (else 24) | e.g. 24 → **~8,400** | Decision 10. Lead's derivation (Matrikulasi ~RM450 living − RM100); owner may adjust. |
| **iljtm** (ILJTM) | Free tuition & hostel, no allowance | **~450** | semesters × 6 (else 24) | e.g. 24 → **~10,800** | Decision 11. |
| **kkom** (Kolej Komuniti) | Free tuition & hostel, no allowance | **~450** | semesters × 6 (else 24) | e.g. 24 → **~10,800** | Decision 11. |
| **mara_cert** (MARA skills certificate) | Free tuition & hostel, no allowance assumed | **~450** | semesters × 6 (else 24) | e.g. 6 → **~2,700** | Decision 12. |
| **tvet** (every other TVET course or family) | Free tuition & hostel, no allowance assumed | **~450** | semesters × 6 (else 24) | e.g. 24 → **~10,800** | Decision 12. |
| **unknown / undecided** | — | — | — | — | No pathway, no readable programme, or several pathways considered → **no estimate**; fall back to checkboxes + ask. |

`iljtm`, `kkom`, `mara_cert` and `tvet` share ONE spec (`_TVET_SPEC`); the keys differ only so the
cockpit label can. A skills course's months are its catalogue `courses.semesters` × 6
(`MONTHS_PER_SEMESTER`), or 24 when there is no catalogue course or no semesters.

⚠️ = `variable` flag (cost swings by institution/field — the cockpit shows a "confirm at
interview" caveat). Diploma duration spans ~24–36 months; 30 is the planning midpoint.
A student-stated `funding_need.programme_months` (whole years) overrides the default.

## Classification

Read the pathway in priority order (`classify_pathway`):
0a. **degree-bound** (`results_route.degree_bound`) → `degree`, before any stored code.
0b. a **MARA diploma** → `mara_diploma`: an `OP4…` id (Kolej Profesional MARA, stored `university`), or
   no id and a diploma name under the MARA-BPT division or the `mara` code. UiTM `UE4…` stays
   `university`.
0c. the `mara` code → its readable programme, else `mara_cert`.
1. `chosen_pathway` when `pathway_certainty == 'sure'`.
2. else `chosen_pathway` / `intended_pathway` (older rows).
3. else the **chosen PROGRAMME** — the concrete course (e.g. auto-filled from the offer
   letter) pins the pathway even when the pathway-type fields are blank: `POLY-*` id →
   `poly`; a non-Politeknik diploma name (MOHE-coded id) → `university`; `Asasi…` → `asasi`;
   `PISMP`/`Perguruan` → `pismp`; `IKBN-`/`IKTBN-`/`ILKBS-` → `ilkbs`; `KKOM-` or "Kolej Komuniti" →
   `kkom`; `IJTM-`/`ILJTM-` → `iljtm`; a `TVET-` id by its provider family
   (`course_pathway.course_pathway_type`): ILKBS → `ilkbs`, ILJTM → `iljtm`, MARA Diploma →
   `mara_diploma`, MARA other level → `mara_cert`, anything else → `tvet`.
4. else a single value in `pathways_considered`.
5. else **unknown**.

Value → category map: `matric/matrik/matrikulasi→matric`, `stpm→stpm`,
`asasi/foundation→asasi`, `university/degree→university`, `poly/politeknik→poly`,
`pismp/ipg→pismp`, `ilkbs→ilkbs`, `iljtm→iljtm`, `kkom→kkom`, `tvet/tvet_other→tvet`. `mara` is read
through its programme (step 0c). (`degree→university` survives in the map but is reached only through
`intended_pathway` or a single considered pathway; a `degree` CHOSEN pathway is degree-bound first.)

## Revisit if

- A pathway's government coverage changes (BSHP rate, IPG allowance, PTPTN policy).
- Real award data shows the estimate is consistently over/under for a pathway.
- The owner adjusts the skills-institute figures (RM350 / RM450 are the lead's derivation).
- `stpm_courses.stream` gains a reliable arts / science split for the `both` courses.
- A new pathway value appears in `chosen_pathway` that isn't mapped above.
