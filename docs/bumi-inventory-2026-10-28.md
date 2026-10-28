# Bumiputera + Islamic course inventory — 2026-10-28 (Sprint A)

Roadmap: `docs/plans/2026-10-28-bumi-and-islamic-coverage-roadmap.md`. No database writes were made.

## How it was measured
- `scrape_mohe_stpm --with-bumi --with-syarat` (new flags) over MOHE e-Panduan, SPM category A and STPM S + A.
- **Two independent Bumi signals per programme** (lessons L539):
  1. the portal's own "Program BUMI = Ya" filter (`bumi_portal`);
  2. the Syarat modal wording, e.g. "Berketurunan Melayu, Anak Negeri Sabah, Anak Negeri Sarawak dan Orang Asli sahaja" (`bumi_syarat`).
- Compared with prod (`courses`, `stpm_courses`, `stpm_requirements`) by read-only query.
- SPM input file for Sprint D: `halatuju_api/data/spm/mohe_bumi_2026-10-28.csv` (369 rows).

## Results

### Signals agree everywhere
| Track | Programmes | Both Bumi | Neither | Disagree |
|---|---|---|---|---|
| SPM | 369 | 136 | 233 | **0** |
| STPM (unique codes) | 1,112 | 162 | 950 | **0** |

The listing badge "Program Perintis (Feeder) Bumiputera" is NOT a Bumi rule (it means a feeder into one university's degree). Do not use it.

No programme on either track says "beragama Islam" or "Muslim". Islamic courses are gated by subjects only, as the owner said.

### STPM — nothing to add
- The 1,112 unique codes on the portal are exactly the 1,112 we hold (the 1,679 raw rows double-list 567 codes under both S and A).
- The 162 Bumi codes are exactly the 162 we already flag `req_bumiputera` (all UiTM).
- **Sprint E is not needed.** Sprint B alone unlocks STPM Bumi courses.

### SPM — 150 courses to add in Sprint D
**136 Bumi-only** (94 diploma, 39 asasi, 2 matrikulasi, 1 other):
| Institution | Count |
|---|---|
| Universiti Teknologi MARA | 87 |
| Universiti Islam Antarabangsa Malaysia | 20 |
| MARA, Bahagian Pendidikan Tinggi (Kolej MARA / KPM) | 15 |
| Universiti Malaysia Sabah | 4 |
| Universiti Malaysia Sarawak | 3 |
| Universiti Malaya | 3 |
| Universiti Sultan Zainal Abidin | 2 |
| Bahagian Matrikulasi KPM | 2 |
27 of the 136 also need an Islamic subject.

**14 open to all, never loaded** (all need an Islamic subject — the old "Islamic" exclusion):
- UniSZA 9 diplomas (Al-Quran & As-Sunnah, Bahasa & Kesusasteraan Arab, Dakwah, Media Penyiaran Islam, Pentadbiran Islam, Sejarah & Tamadun Islam, Syariah, Undang-Undang, Usuluddin).
- USIM 4 Tamhidi (Perakaunan & Muamalat, Perubatan/Pergigian/Sains, Sains Sosial, Syariah & Undang-Undang).
- UM 1 (Asasi Pengajian Islam).

**Not new** (held under internal IDs, see lesson L710): 80 Politeknik + 47 Kolej Komuniti rows, and 4 open Matrikulasi rows (we hold matric as 4 tracks). The 2 Bumi Matrikulasi rows need a decision in Sprint D: add as a Bumi track, or note it on the existing tracks.

All 89 MOHE-coded SPM courses we already hold are still on the portal, and none of them is Bumi-only.

### UP_TVET (MARA) — sizes Sprint F
- The `kelayakan_url` (semak-pra-syarat) pages now need a login. **The public course page (`info_url`) still shows the full "Syarat Kursus"**, as structured "KRITERIA UTAMA" blocks.
- Sample of 20 random MARA courses (GIATMARA + TVETMARA): **20/20 say "Calon Bumiputera Sahaja"**. 3 non-MARA samples (IKTBN, ADTEC): 0/3.
- GIATMARA entry is light (age 15–70, basic schooling); TVETMARA diplomas ask for SPM passes. 544 MARA rows in `uptvet_latest.csv` (2026-06-14).
- Sprint F should parse `info_url`, not `kelayakan_url`, and take the Bumi flag from the "Taraf Bumiputera / BUMIPUTERA" criterion.

## Revised roadmap impact
- Sprint E: **dropped** (STPM data already exact).
- Sprint D: 150 SPM courses (136 Bumi + 14 Islamic-subject); split D1 = UiTM 87, D2 = the other 63, if the review is heavy.
- Sprint F: parse source changes to `info_url`.
