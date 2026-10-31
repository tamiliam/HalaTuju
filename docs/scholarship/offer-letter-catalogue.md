# Offer-letter catalogue — per-issuer markers & variables

**Owner-supplied 2026-07-08.** The authoritative reference for (a) the reporting-date label each
institution prints, (b) the provisional variable set per issuer family, and (c) the raw material for
the future per-issuer POSITIVE offer fingerprints (roadmap). The **reporting date** is the *tarikh
mendaftar / tarikh lapor diri* — NEVER the letter-issue date ("Tarikh" in the reference block) or
"Tarikh Cetakan". **Not every letter carries one — its absence is a signal** (live cohort 2026-07-08:
6 of the 7 offers without a reporting date were non-genuine documents — interview slips, pemakluman,
notices; only one genuine offer lacked it, and that copy was cropped).

| Issuer family | Reporting-date label | Confirmed live sample |
|---|---|---|
| STPM (Sektor Operasi Sekolah) | Tarikh Lapor Diri | cohort-wide (8 Jun 2026 cluster) |
| Matriculation (Bahagian Matrikulasi) | Tarikh Kemasukan ke kolej | cohort-wide |
| Polytechnic (JPPKK) | Tarikh dan Masa Daftar | #125 (Politeknik Sultan Idris Shah) |
| PISMP (IPG) | TARIKH PENDAFTARAN | #107 |
| UPNM | Tarikh Pendaftaran | — |
| UKM ASASIpintar | TARIKH LAPOR DIRI | — |
| UMP | TARIKH PENDAFTARAN | — |
| UTeM | Tarikh / TARIKH PENDAFTARAN | #87 |
| UPSI | **Tarikh Mendaftar** | **#44** (9 Jun 2026) |
| UTHM | bare **"Tarikh"** inside the *"diminta untuk mendaftar pada tarikh, tempat dan masa"* clause | **#48** (12 Julai 2026) |

## Per-issuer structure (headers → clauses → variables)

### STPM — Sektor Operasi Sekolah
Jata Negara · SEKTOR OPERASI SEKOLAH · TAWARAN KEMASUKAN KE TINGKATAN ENAM · Bidang ·
Pusat Tingkatan Enam · Tarikh Lapor Diri · Dokumen diperlukan ·
"Keputusan ini adalah muktamad berdasarkan syarat kemasukan ke tingkatan enam." ·
"Tawaran ini terbatal serta-merta jika murid berstatus bukan warganegara Malaysia."
**Variables:** name, IC, date, college, stream + optional reporting date.

### Matriculation — Bahagian Matrikulasi
Jata Negara · Bahagian Matrikulasi · TAWARAN KEMASUKAN PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN ·
Jurusan · Kolej · Tarikh Kemasukan ke kolej ·
"Saudara/Saudari perlu mendaftar pada tarikh yang ditetapkan oleh pihak kolej." ·
"Tawaran ini terbatal serta-merta jika saudara/saudari berstatus bukan warganegara Malaysia atau
maklumat permohonan tidak benar."
**Variables:** name, IC, date, college, stream + optional reporting date.

### Polytechnic — JPPKK
JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI · KEMENTERIAN PENDIDIKAN TINGGI ·
SURAT TAWARAN PENGAJIAN · Program · Institusi · Tarikh dan Masa Daftar ·
"Tawaran ini adalah MUKTAMAD dan TERBATAL sekiranya anda tidak mendaftar di institusi berkenaan pada
tarikh dan masa yang ditetapkan." ·
"Tawaran ini adalah tertakluk kepada kesahihan maklumat dalam borang permohonan dengan dokumen asal
yang dikemukakan."
**Variables:** name, IC, date, program + optional institusi + optional reporting date.

### PISMP — Institut Pendidikan Guru
INSTITUT PENDIDIKAN GURU MALAYSIA · KEMENTERIAN PENDIDIKAN MALAYSIA ·
TAWARAN MENGIKUTI PROGRAM IJAZAH SARJANA MUDA PERGURUAN (PISMP) · BIDANG PENGKHUSUSAN ·
TARIKH PENDAFTARAN · ALIRAN SEKOLAH · TEMPAT PENGAJIAN ·
"Surat tawaran ini hendaklah dibaca bersama-sama Perjanjian Pendidikan Guru" ·
"Tawaran ini akan TERBATAL dengan sendirinya jika:" · "Penetapan bidang dan tempat pengajian adalah
muktamad"
**Variables:** nama, IC, date, bidang pengkhususan + optional elektif + optional reporting date.

### Asasi UPNM
UPNM logo · Pusat Pengurusan Akademik dan Pengijazahan ·
TAWARAN KEMASUKAN KE UNIVERSITI PERTAHANAN NASIONAL MALAYSIA · "Sukacita dimaklumkan bahawa" ·
Program Pengajian · Tarikh Pendaftaran · "Sebarang pertukaran program adalah TIDAK dibenarkan."
**Variables:** name, NRIC, date, program pengajian + optional reporting date.

### ASASIpintar UKM
UKM logo · UNIVERSITI KEBANGSAAN MALAYSIA · PUSAT PENGURUSAN AKADEMIK ·
TAWARAN KEMASUKAN PROGRAM ASASIpintar UKM · "Dengan sukacitanya" · Program Pengajian ·
TARIKH LAPOR DIRI · "Tawaran yang diberikan adalah muktamad dan sebarang pertukaran program adalah
tidak dibenarkan."
**Variables:** name, NRIC, date, program pengajian + optional pusat pengajian + optional reporting date.

### UA Diploma — UTHM
UTHM logo · PEJABAT PENGURUSAN AKADEMIK · TAWARAN KEMASUKAN KE UNIVERSITI TUN HUSSEIN ONN MALAYSIA ·
"Tahniah diucapkan" · Program & Kod Program · reporting date via the numbered clause
*"Saudara/i diminta untuk mendaftar pada tarikh, tempat dan masa seperti butiran berikut: Tarikh : …"*
(confirmed on #48; also carries Masa/Tempat, Kolej Kediaman, No. Matrik, Yuran Kemasukan, and the
footer *"Surat tawaran ini merupakan surat tawaran rasmi dan boleh digunapakai untuk sebarang urusan
berkaitan"* — a computer-generated letter, "tidak memerlukan tandatangan").
**Variables:** name, date, program + optional kampus + optional reporting date.

### UA Diploma — UPSI
UPSI logo · SULTAN IDRIS EDUCATION UNIVERSITY · BAHAGIAN HAL EHWAL AKADEMIK ·
TAWARAN KEMASUKAN KE UNIVERSITI PENDIDIKAN SULTAN IDRIS (UPSI) · "Sukacita dimaklumkan bahawa" ·
Program · **Tarikh Mendaftar** ·
"Tawaran ini adalah muktamad dan saudara/i tidak dibenarkan menukar program pengajian"
(confirmed on #44: also Fakulti, Tempoh/Mod/Sesi, Masa Mendaftar, Tempat Mendaftar, Kolej Kediaman,
Yuran Pengajian, No. Matrik).
**Variables:** name, date, program + optional faculty + optional tarikh mendaftar.

### UA Diploma — UTeM
UTeM logo · UNIVERSITI TEKNIKAL MALAYSIA MELAKA · PEJABAT PENDAFTAR ·
TAWARAN KEMASUKAN KE UNIVERSITI TEKNIKAL MALAYSIA · "Tahniah, sukacita dimaklumkan" ·
Program Pengajian · Tarikh ·
"Tawaran akan ditarik balik sekiranya UTeM mendapati maklumat yang saudara/i berikan adalah tidak
benar."
**Variables:** name, NRIC, date, program + optional faculty + optional TARIKH PENDAFTARAN.

### UA Diploma — UMP (Al-Sultan Abdullah)
UMP logo · Pusat Pemasaran dan Kemasukan ·
TAWARAN KEMASUKAN KE PROGRAM DIPLOMA UNIVERSITI MALAYSIA PAHANG AL-SULTAN ABDULLAH ·
"Dimaklumkan bahawa" · PROGRAM PENGAJIAN · TARIKH PENDAFTARAN ·
"Program yang ditawarkan adalah MUKTAMAD dan sebarang pertukaran adalah TIDAK DIBENARKAN."
**Variables:** name, NRIC, date, program + optional faculty + optional TARIKH PENDAFTARAN.

### UA — UiTM (Bahagian Pengambilan Pelajar) — scored since MODEL_VERSION 1.8.1 (corpus-gaps C2)
The fixed printed wording of 7 real UiTM offers (sessions 2024/25–2026/27; PII-free, roadmap C0). One
machine-generated "SURAT TAWARAN" from online.uitm.edu.my; the newer ones add a contact footer.
UNIVERSITI TEKNOLOGI MARA (letterhead; OCR may split it — the footer repeats it) · BAHAGIAN
PENGAMBILAN PELAJAR (letterhead + signature title) · "Sukacita dimaklumkan bahawa anda ditawarkan
tempat untuk mengikuti program di UiTM" (**the offer line — UiTM never prints "Tawaran Kemasukan"**) ·
placement labels Program / Mod Pengajian / Fakulti / Tempoh Pengajian / Sesi Kemasukan / Kampus ·
"Sila hadir mendaftar pada tarikh, masa dan tempat yang ditetapkan" then Tarikh / Masa / Tempat ·
MAKLUMAT PENTING: "Program dan kampus yang ditawarkan adalah muktamad", "Sebarang permohonan pertukaran
tidak dibenarkan", "Tawaran ini adalah terbatal sekiranya terdapat maklumat yang salah", "Calon hanya
diterima sebagai pelajar UiTM setelah membuat pendaftaran secara dalam talian", "UiTM berhak menukarkan
calon ke mana-mana kampus" · fees block (Kemudahan dan Bayaran / Kolej Kediaman / Yuran Pengajian / Kos
Ditanggung oleh Kerajaan) · "Dokumen ini adalah janaan komputer dan tidak memerlukan tandatangan" ·
No Siri · Dicetak pada · "UiTM di hatiku".
**Scored by (`UA_OFFER_SIGNATURES`):** the UA name — or, on a digital PDF's text layer (no letterhead,
1.8.2), UiTM's own clauses that name it ("pelajar UiTM setelah membuat pendaftaran", "UiTM berhak
menukarkan calon"; never the offer line, which a private letter can copy); the offer line *with* "program di UiTM" (the bare
"ditawarkan tempat untuk mengikuti" also sits on the UM SATU pemakluman a31, which policy 1.1 keeps off
the offer line); BAHAGIAN PENGAMBILAN PELAJAR (not the shorter "Pengambilan Pelajar", which a12 also
carries); "hadir mendaftar pada tarikh"; the finality clause via "adalah muktamad". 0.90 on six
letters, 0.80 on one whose OCR garbled the office line. **Not used:** "Surat Tawaran" (policy 1.1);
"Mod Pengajian" (it sits on 29 of 95 other cached offers, and would let a UiTM-worded page with no
university name reach genuine). **Reporting date:** the bare "Tarikh" label inside the summons —
already allowed for `ua_offer` in `pathway_engine._REPORTING_LABELS`.
**Variables:** name, NRIC, No. Pelajar, programme, mode, faculty, campus, session, reporting date.

## Known public issuers NOT fingerprinted yet — "not checked" (MODEL_VERSION 1.8.0)

Owner rulings A, B, C (2026-10-26, `docs/decisions.md`; corpus-gaps roadmap C1): an offer that reads
SUSPECT (0.35–0.70), carries offer wording, and whose LETTERHEAD names one of these reads **not
checked** (`bands.NOT_CHECKED`) — no
genuineness penalty, no block, no official-document request; the officer is told plainly and checks
the letter by eye. TVET offers COUNT as supported official public offers (ruling B). The list is closed
and lives in `genuineness/offer_issuers.py` (`TVET_ISSUERS`); a family of its own is added only once we
hold ≥3 genuine letters (roadmap "Later").

| Ministry | Names matched (letterhead only) | Acronyms (whole word) |
|---|---|---|
| Kementerian Belia dan Sukan | Kementerian Belia dan Sukan · Institut Kemahiran Belia Negara · Institut Kemahiran Tinggi Belia Negara | ILKBS · IKBN · IKTBN |
| MARA | Majlis Amanah Rakyat · Institut Kemahiran MARA · Kolej Kemahiran Tinggi MARA · Kolej Profesional MARA · Kolej MARA | TVETMARA · IKM · KKTM |
| Jabatan Tenaga Manusia (KESUMA) | Jabatan Tenaga Manusia · Jabatan Pembangunan Kemahiran · Institut Latihan Perindustrian · Pusat Latihan Teknologi Tinggi | JTM · ADTEC · ILP · JPK · ILJTM |

- **Suspect band only:** a letter below 0.35 (a typed fake, a skills certificate, a loan letter) stays
  `not_offer_letter` whatever it names. **Offer wording required:** Tawaran / ditawarkan / surat
  tawaran / offer of admission ("tawaran pinjaman" is a loan, not an offer).
- **Letterhead only** (the first 600 characters of the normalised OCR text): a private college often
  cites JPK accreditation or MARA sponsorship in its body. A **sponsor line** (Tajaan / ditaja / Penaja /
  sponsored by) is never the issuer. A bare **3-letter acronym** (IKM, ILP, JTM, JPK) counts only beside
  offer wording on the letterhead.
- **MARA-owned but PRIVATE (ruling C):** KPTM (Kolej Poly-Tech MARA) and UniKL (Universiti Kuala
  Lumpur) — never "not checked", always the private-college reason.
- **Never over a fingerprinted family:** if any family's own issuer line is on the page (a UA name,
  Sektor Operasi Sekolah, …) the letter keeps that family's band — "Universiti Teknologi MARA" is a
  university letter.
- **Never over a private company:** "Sdn Bhd" is the private-arm veto (1.6.0); "Bhd" / "Berhad" /
  "Pusat Bertauliah" on the letterhead also keeps the net off.
- **A private college / university (IPTS)** — a letterhead naming an institution and no public body —
  keeps its band but now says so: "private college / university (IPTS) - not a supported public
  issuer", instead of the nearest public family's label. Never for a page naming a public university
  by full or short name (a UiTM PDF text layer says only "UiTM") or a listed public body.

## Notes for implementers

- The issuer-office lines above (Pejabat Pengurusan Akademik / Pusat Pengurusan Akademik / Bahagian
  Hal Ehwal Akademik / Pejabat Pendaftar / Pusat Pemasaran dan Kemasukan) are already weight-1
  signatures in `UA_OFFER_SIGNATURES` (`genuineness/results_doc.py`) — this catalogue confirms them.
- When building the per-issuer POSITIVE fingerprints (roadmap), each section above is a signature
  list: logo/letterhead → office → offer line → programme labels → reporting-date label → the
  finality/terbatal clause. Bump `MODEL_VERSION` when added.
- The extraction prompt (`vision.py`, offer_letter) hunts the reporting-date labels listed in the
  table; keep the two in sync when an institution changes wording.
- A document with NO reporting date that claims to be an offer deserves suspicion (interview slips,
  pemakluman and notices don't summon anyone to register) — but a cropped genuine letter also loses
  it, so it corroborates rather than decides.

## What the programme and institution LINES carry (offer realignment, 2026-10-31)

Read by the course matcher (`apps/scholarship/offer_course_match.py`), measured on the live letters:

- **The institution line is often a HOSTEL, not the university** — UMS ("Kolej Kediaman Tun Pengiran
  Ahmad Raffae", "Kolej Kediaman Tun Fuad"), UPM ("KOLEJ SRI RAJANG"), UNIMAS ("Kolej Cempaka",
  "Kolej Allamanda"), UTHM ("KOLEJ KEDIAMAN PERWIRA - DEWAN SULTAN IBRAHIM"), UKM ("Kolej Pendeta
  Za'ba (L), UKM, BANGI"). The university is then in the ISSUER (letterhead) line — though UMS and UiTM
  often print only an office there ("BAHAGIAN PERKHIDMATAN AKADEMIK", "Bahagian Pengambilan Pelajar").
- **UiTM** names the university only by acronym or in a college line: "UiTM CAWANGAN SABAH, KAMPUS
  KOTA KINABALU", "KOLEJ PERINDU, UNIVERSITI TEKNOLOGI MARA, 40450 SHAH ALAM"; its programme line starts
  with UiTM's own short code ("BA272 ", "SR241 ", "HS243 ") and may run on into the faculty ("…
  (KEPUJIAN) FAKULTI SAINS SUKAN DAN …").
- **UNIMAS** prints our own UPU course code after the name ("Sarjana Muda Ukur Bahan dengan Kepujian -
  UW6526001") — the same `[A-Z]{2}\d{7}` id both catalogues key by.
- The catalogue's side carries decorations no letter prints: UPU's trailing " #" and a campus
  parenthetical ("Diploma Pembangunan Manusia (Kampus Bintulu, Sarawak)").
