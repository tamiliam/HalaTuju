# TVET Catalogue Reconciliation — 2026-06-14 (read-only audit, NOT yet applied)

**Status:** audit complete, **nothing written to the DB**. This doc is the resume point.

## What was done
Audited HalaTuju's **83 TVET courses = 180 offerings** (ILJTM + ILKBS) against the live
UP_TVET catalogue. Each offering's `course_institutions.hyperlink` carries `?id_kursus=N`;
matched those against `halatuju_api/data/tvet/uptvet_latest.csv` (988 live programmes, scraped
2026-06-14, kept + gitignored).

**Method:** exact `id_kursus` match first; for misses, match on **course-name** (strip leading
code prefixes like `SHF 03` / `SAK 03` / `SEME03P` via "from first *sijil/diploma* + alnum",
containment) + **campus** (institution text before the trailing `, STATE`) + **family**
(IJTM→ADTEC/Proton/JMTI, IKBN/IKTBN→"belia negara"). Two portal quirks: `id_kursus` **rotates
each intake**, and ADTEC campuses are **rebadged** as `(ILP …)` / `Proton Institute (ADTEC …)`.

## Result
| Outcome | Count | Action |
|---|---|---|
| CURRENT (id still live) | 114 | none |
| **REFRESH** (re-IDed: old→new) | **32** | update hyperlink (owner-gated, reversible) |
| GONE (no name+campus match) | 34 | review: clear or keep |
| AMBIGUOUS | 0 | — |
| **NEW offerings** (extra campuses, our courses) | **70 across 38 courses** | expansion / ingest |

## Next-step options (none done)
- **(a) Apply the 32 refreshes** — `UPDATE course_institutions SET hyperlink='https://mohon.tvet.gov.my/awam-kursus/kursus?id_kursus=<NEW>' WHERE hyperlink LIKE '%id_kursus=<OLD>%'` (one per pair).
- **(b) Gone (34)** — decide clear-vs-keep per offering.
- **(c) New (70)** — scope as catalogue expansion (adds `course_institutions` rows; golden-master-adjacent).
- **Regenerate:** re-run `scrape_uptvet` (needs `PYTHONIOENCODING=utf-8`) + the recon (CSV + 180-offering block reproducible via the prod query in the chat log).

---

## REFRESH map (32) — old id_kursus → new
| old → new | Institution | Course |
|---|---|---|
| 7102 → 47405 | ADTEC Pasir Gudang | Elektronik Industri |
| 7219 → 36710 | ADTEC Jitra | Polimer |
| 7375 → 44059 | ADTEC Labuan | Minyak dan Gas (Mekanikal Plant Downstream) |
| 7378 → 44053 | ADTEC Labuan | Komputer (Sistem) |
| 7480 → 47984 | ADTEC Pedas | CADD-Senibina |
| 7489 → 47408 | ADTEC Pedas | Telekomunikasi |
| 8718 → 47351 | JMTI | Diploma Teknologi Elektronik |
| 9269 → 47378 | ADTEC Kuala Lumpur | Rekabentuk Grafik |
| 9551 → 36791 | ADTEC Ipoh | Fabrikasi Struktur Logam (Minyak Dan Gas) |
| 9581 → 47420 | ADTEC Taiping | Diploma Jaminan Kualiti |
| 9617 → 47369 | ADTEC Kepala Batas | Telekomunikasi |
| 10790 → 47372 | ADTEC Kepala Batas | Elektronik Industri |
| 14195 → 48575 | IKBN Bandar Penawar | Hospitaliti (Penyediaan Makanan) |
| 14240 → 48626 | IKBN Jitra | Fesyen Dan Pakaian (Jahitan Pakaian Wanita) |
| 14306 → 48533 | IKTBN Bachok | Hospitaliti (Penyediaan Pastri) |
| 14411 → 48635 | IKTBN Temerloh | Automotif (Penyelenggaraan Kereta) |
| 14435 → 46702 | IKBN Pekan | Mekanikal (Operasi Fabrikasi Paip) |
| 14456 → 48707 | IKBN Kuala Perlis | Automotif (Vehicle Painting) |
| 14471 → 48638 | IKBN Kuala Perlis | Marin (Penyelenggaraan) |
| 14483 → 48554 | IKBN Kuala Perlis | Automotif (Penyelenggaraan Kereta) |
| 14504 → 48608 | IKTBN Bukit Mertajam | Mekanikal (Penyelenggaraan Industri) |
| 14525 → 48689 | IKBN Miri | Mekanikal (Penyelenggaraan Industri) |
| 14561 → 48701 | IKBN Miri | Hospitaliti (Penyediaan Makanan) |
| 14759 → 48437 | IKBN Wakaf Tapai | Mekanikal (Kimpalan Arka) |
| 30540 → 47393 | ADTEC Kuantan | CADD-Senibina |
| 30582 → 36933 | ADTEC Kota Samarahan | Fabrikasi Struktur Logam Minyak dan Gas |
| 30635 → 34158 | IKBN Naka | Elektrik (Penyamanan Udara & Pemanasan Domestik) |
| 30656 → 46699 | IKBN Pekan | Mekanikal (Pesawat - Komposit) |
| 30659 → 48548 | IKBN Kuala Perlis | Awam (Scaffolding - Tubular) |
| 30661 → 48680 | IKTBN Bukit Mertajam | Mekanikal (Mekatronik) |
| 33929 → 40513 | ADTEC Melaka (Proton Institute) | Automotif (Automasi Industri) |
| 45421 → 48641 | IKBN Tanah Merah | Mekanikal (Rekabentuk Produk Industri) |

## GONE (34) — old id_kursus, no current name+campus match (review)
| old id | Institution | Course |
|---|---|---|
| 8002 | ADTEC Miri | Telekomunikasi |
| 8005 | ADTEC Miri | Pemasangan Paip Minyak dan Gas |
| 9290 | ADTEC Kuala Lumpur | Automotif Servis |
| 10049 | ADTEC Shah Alam | Diploma Pengeluaran Automotif |
| 14276 | IKTBN Bachok | Automotif (Penyelenggaraan Kenderaan Perdagangan) |
| 14342 | IKTBN Alor Gajah | Hospitaliti (Penyediaan Pastri) |
| 14432 | IKBN Pekan | Mekanikal (Boilermaker) |
| 14450 | IKBN Seri Iskandar | Elektronik (Elektronik Industri) |
| 14453 | IKBN Seri Iskandar | Maklumat (Perekabentuk Multimedia Pengarangan) |
| 14531 | IKBN Miri | Automotif (Vehicle Painting) |
| 14567 | IKTBN Dusun Tua | Mekanikal (Kimpalan) |
| 14603 | IKTBN Dusun Tua | Diploma Mekanikal (Rekabentuk Produk Industri) |
| 14612 | IKTBN Dusun Tua | Automotif (Penyelenggaraan Jentera Berat) |
| 14639 | IKBN Peretak | Hospitaliti (Penyajian) |
| 14660 | IKBN Peretak | Kosmetologi (Perekaan Gaya Rambut) |
| 14783 | IKBN Kemasik | Hospitaliti (Penyediaan Roti) |
| 14798 | IKBN Kemasik | Hospitaliti (Kaunter Hadapan - Front Office) |
| 30438 | ADTEC Pasir Gudang | Minyak dan Gas (Mekanikal - Plant Downstream) |
| 30653 | IKBN Pekan | Mekanikal (Pesawat - Metal) |
| 33995 | ADTEC Sandakan | Elektrik Pendawaian Tiga Fasa |
| 33998 | ADTEC Kota Samarahan | Pembuatan Pemesinan |
| 34007 | ADTEC Miri | Elektrik Pendawaian Tiga Fasa |
| 34149 | ADTEC Miri | Penyejukbekuan dan Penyamanan Udara |
| 34562 | ADTEC Kepala Batas | Penyejukbekuan dan Penyamanan Udara |
| 35118 | IKBN Peretak | Diploma Fesyen Dan Pakaian (Rekaan Fesyen) |
| 35199 | IKTBN Alor Gajah | Diploma Elektrik (Penjaga Jentera Elektrik - A1) |
| 36897 | ADTEC Kuala Terengganu | Pemasangan Paip Minyak dan Gas |
| 36921 | ADTEC Bintulu | Mekatronik |
| 40510 | ADTEC Melaka | Automotif (Pembuatan) |
| 43845 | IKTBN Chembong | Automotif (Vehicle Painting) |
| 44014 | ADTEC Sandakan | Kimpalan |
| 44202 | IKTBN Chembong | Automotif (Penyelenggaraan Kereta/EV) |
| 44208 | IKBN Kemasik | Kosmetologi (Terapi Kecantikan) |
| 45289 | IKTBN Bachok | Automotif (Vehicle Painting) |

## NEW-offering candidates (70 offerings, 38 of our courses) — extra public ILJTM/ILKBS campuses we don't list
Top by count (full list reproducible from the recon):
- **+6** Sijil Teknologi Elektrik Pendawaian Tiga Fasa — ADTEC Bukit Katil, Jitra, Kota Samarahan, …
- **+4** Sijil Lanjutan Teknologi Hospitaliti (Penyediaan Makanan) — IKBN Kemasik, Peretak, IKTBN Alor Gajah, Bachok
- **+4** Sijil Lanjutan Teknologi Hospitaliti (Penyediaan Pastri) — IKBN Bandar Penawar, Kemasik, Miri, …
- **+3** each: Automotif (Penyelenggaraan Kenderaan Perdagangan); Mekanikal (Kimpalan); Hospitaliti (Penyajian); Sijil Teknologi Penyejukbekuan dan Penyamanan Udara (ADTEC Bintulu/Mersing/Sandakan); Sijil Teknologi Kimpalan (ADTEC Mersing/Miri/Pedas); Sijil Teknologi Penyelenggaraan Mekanikal (ADTEC Bukit Katil/Kota Kinabalu/Pasir Gudang)
- **+2** ×8 and **+1** ×many — see recon output. All ILJTM/ILKBS, Sektor Awam (public).
