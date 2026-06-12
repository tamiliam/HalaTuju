# Course-Data Source Inventory

**Compiled 2026-06-12** from (a) URLs hardcoded in HalaTuju, (b) URLs actually in the
production DB, (c) confirmed official portals. Feeds the course-data pipeline roadmap.

## A. Central portals — the pipeline data sources

| Portal | URL | Covers | HalaTuju use today |
|---|---|---|---|
| **MOHE e-Panduan** | `https://online.mohe.gov.my/epanduan/` | **Course guide for ALL UPU pathways** — foundation/Asasi, diploma, degree, STPM — incl. **entry requirements** & merit. Parameterised by `jenprog` + candidate category. | ✅ STPM scraper (`jenprog=stpm`); **98** offering links |
| **UPU Online** | `https://upu.mohe.gov.my/` | The **application system** for UA, Politeknik, Kolej Komuniti, ILKA, MARA BPT (not a course catalogue — e-Panduan is the catalogue) | reference |
| **UP_TVET** | `https://mohon.tvet.gov.my/` | Central **TVET admission** (ILJTM / ILKBS). UP_TVET Perdana (Jan + Jul intake) + Flexi (year-round) | **180** offering links |
| **TVET Madani** | `https://www.tvet.gov.my/` | TVET info / institution directory | — |

> **Key insight:** e-Panduan is the single structured source for the UPU course listings +
> requirements. The STPM scraper already parses it; extending to the SPM-track programme
> types (other `jenprog` values) is **incremental, not greenfield**. Confirm the `jenprog`
> values in the Sprint 3 spike — this is the cheapest path to the post-SPM catalogue.

## B. Pathway → umbrella portal (institution intake sites)

| Pathway | Umbrella portal | Pattern in DB |
|---|---|---|
| **Politeknik + Kolej Komuniti** | **MyPolyCC** — info `mypolycc.edu.my`, intake `https://ambilan.mypolycc.edu.my/` | `*.mypolycc.edu.my` — **546** offering links |
| **Matrikulasi** | **Bahagian Matrikulasi** — `https://www.matrik.edu.my/` (info: `https://www.moe.gov.my/pengenalan-matrikulasi`) | `*.matrik.edu.my` (e.g. kmj, kmkk, kmkj) |
| **PISMP** (teacher training) | **IPG** — `https://pismp.moe.gov.my/` ; institutes `*.moe.edu.my` | `ipg*.moe.edu.my` |
| **STPM** (pre-U schools) | **MOE SST** — `https://sst6.moe.gov.my/` | (schools list is local data) |
| **ILKBS** (youth & sports skills) | **Kemahiran KBS** — `https://kemahiran.kbs.gov.my/` | `kemahiran.kbs.gov.my` — **21** institutions |
| **ILJTM** (ILP / ADTEC, manpower dept) | via **UP_TVET**; sites `ilp*.gov.my`, `adtec*.gov.my` | individual gov.my sites |
| **UA** (20 public universities) | individual university sites | `um.edu.my`, `usim.edu.my`, `ump.edu.my`, `unimap.edu.my`, … |

## C. "More Info" links already hardcoded in the app

- Matriculation → `https://www.moe.gov.my/pengenalan-matrikulasi`  ([course/[id]/page.tsx])
- STPM → `https://sst6.moe.gov.my/index.cfm`
- PISMP → `https://pismp.moe.gov.my/iklan_permohonan.cfm`

## D. Institution metadata (address / phone / ranking modifiers) — **MANUAL tier**

No central structured source. Gathered per-institution via the umbrella sites above +
web search. **Deliberately not automated** (see `docs/decisions.md` / roadmap non-goals).

## E. Refresh cadence (for the annual reminder)

UPU 2026/2027 windows (illustrative): **SPM** grads ~29 Jan – 23 Mar; **STPM** phase 2 ~13 Apr – 15 May.
TVET (UP_TVET Perdana): **Jan + Jul** intakes. → Refresh the catalogue **before each main UPU
window opens** (≈ Dec–Jan), and a TVET pass before the July intake.

## Sources
- UPU Online — https://upu.mohe.gov.my/
- MOHE e-Panduan — https://online.mohe.gov.my/epanduan/
- UP_TVET — https://mohon.tvet.gov.my/  ·  TVET Madani — https://www.tvet.gov.my/
- MoHE UPUOnline media statement (2026/2027 intake; 20 UA, 36 polytechnics, 106 community colleges)
