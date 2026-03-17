# SPM_CODE_MAP Expansion — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bridge all 93 unmapped SPM fixture subject keys to frontend engine keys so the STPM eligibility engine correctly evaluates `spm_subject_group` requirements.

**Architecture:** The `spm_subject_group` JSON in fixtures contains canonical keys (e.g. `SCIENCE_SPM`, `PENDIDIKAN_ISLAM_SPM`) from `subject_keys.py`. The engine translates these via `SPM_CODE_MAP` to frontend keys (e.g. `sci`, `islam`) that match what students enter. Currently only 8 of 93 keys map correctly — 85 fall through to a `.lower()` fallback that produces wrong keys. 101 courses have groups where ALL subjects are unmapped (guaranteed false negatives).

**Tech Stack:** Python/Django (backend), TypeScript/Next.js (frontend)

---

## Impact Summary

| Metric | Current | After Fix |
|--------|---------|-----------|
| Mapped fixture keys | 8 of 93 | 93 of 93 |
| Courses with fully-unmapped groups | 101 | 0 |
| Dead SPM_CODE_MAP entries | 5 | 0 |
| STPM golden master | 1976 | Will increase (more students qualify) |

## The Complete Mapping

### Tier 1: Already Working (8 keys — no change needed)

| Fixture Key | Frontend Key | Courses |
|-------------|-------------|---------|
| `MATH` | `math` | 349 |
| `ADD_MATH` | `addmath` | 285 |
| `BI` | `eng` | 200 |
| `PHYSICS_SPM` | `phy` | 132 |
| `BIOLOGY_SPM` | `bio` | 125 |
| `CHEMISTRY_SPM` | `chem` | 120 |
| `BM` | `bm` | 39 |
| `SEJARAH` | `hist` | 4 |

### Tier 2: Dead Entries to Remove (5 keys — in SPM_CODE_MAP but not in fixtures)

These map entries don't match any fixture key and should be removed:
- `SCIENCE` → `sci` (fixture uses `SCIENCE_SPM`)
- `ACCOUNTING_SPM` → `poa` (fixture uses `PRINSIP_PERAKAUNAN_SPM`)
- `ECONOMICS_SPM` → `ekonomi` (fixture uses `EKONOMI_SPM`)
- `COMMERCE` → `business` (fixture uses `PERNIAGAAN_SPM`)
- `GEOGRAPHY_SPM` → `geo` (fixture uses `GEOGRAFI_SPM`)

### Tier 3: New Mappings — Clear Frontend Match (39 keys)

| Fixture Key | Frontend Key | Courses | Frontend Subject Exists? |
|-------------|-------------|---------|------------------------|
| `SCIENCE_SPM` | `sci` | 81 | Yes (SPM_SUBJECTS) |
| `SAINS_TAMBAHAN_SPM` | `addsci` | 65 | Yes (SPM_SUBJECTS) |
| `PENDIDIKAN_MORAL_SPM` | `moral` | 60 | Yes (SPM_SUBJECTS) |
| `PENDIDIKAN_ISLAM_SPM` | `islam` | 104 | Yes (SPM_SUBJECTS) |
| `PRINSIP_PERAKAUNAN_SPM` | `poa` | 33 | Yes (SPM_SUBJECTS) |
| `PERNIAGAAN_SPM` | `business` | 27 | Yes (SPM_SUBJECTS) |
| `EKONOMI_SPM` | `ekonomi` | 26 | Yes (SPM_SUBJECTS) |
| `GEOGRAFI_SPM` | `geo` | 7 | Yes (SPM_SUBJECTS) |
| `PERTANIAN_SPM` | `pertanian` | 18 | Yes (SPM_SUBJECTS) |
| `SAINS_KOMPUTER_SPM` | `comp_sci` | 18 | Yes (SPM_SUBJECTS) |
| `LUKISAN_KEJURUTERAAN_SPM` | `eng_draw` | 18 | Yes (SPM_SUBJECTS) |
| `EKONOMI_ASAS_SPM` | `ekonomi` | 15 | Yes (alias — same as Ekonomi) |
| `PENGAJIAN_KEUSAHAWANAN_SPM` | `keusahawanan` | 14 | Yes (SPM_SUBJECTS) |
| `PERDAGANGAN_SPM` | `business` | 12 | Yes (alias — Commerce → Business) |
| `REKA_CIPTA_SPM` | `reka_cipta` | 12 | Yes (SPM_SUBJECTS) |
| `KEJURUTERAAN_MEKANIKAL_SPM` | `eng_mech` | 12 | Yes (SPM_SUBJECTS) |
| `KEJURUTERAAN_EE_SPM` | `eng_elec` | 12 | Yes (SPM_SUBJECTS) |
| `KEJURUTERAAN_AWAM_SPM` | `eng_civil` | 11 | Yes (SPM_SUBJECTS) |
| `PENGETAHUAN_SAINS_SUKAN_SPM` | `sports_sci` | 10 | Yes (SPM_SUBJECTS) |
| `SAINS_SUKAN_SPM` | `sports_sci` | 10 | Yes (alias — same subject) |
| `SAINS_PERTANIAN_SPM` | `pertanian` | 10 | Yes (alias — Agri Science → Agriculture) |
| `GRAFIK_KOMUNIKASI_TEKNIKAL_SPM` | `gkt` | 9 | Yes (SPM_SUBJECTS) |
| `SAINS_RUMAH_TANGGA_SPM` | `srt` | 2 | Yes (SPM_SUBJECTS) |
| `PENDIDIKAN_SENI_VISUAL_SPM` | `psv` | 2 | Yes (SPM_SUBJECTS) |
| `BAHASA_CINA_SPM` | `b_cina` | 1 | Yes (SPM_SUBJECTS) |
| `BAHASA_TAMIL_SPM` | `b_tamil` | 1 | Yes (SPM_SUBJECTS) |
| `KATERING_SPM` | `voc_catering` | 3 | Yes (SPM_SUBJECTS) |
| `REKAAN_JAHITAN_SPM` | `voc_tailoring` | 3 | Yes (SPM_SUBJECTS) |
| `KIMPALAN_SPM` | `voc_weld` | 2 | Yes (SPM_SUBJECTS) |
| `MENSERVIS_AUTOMOBIL_SPM` | `voc_auto` | 2 | Yes (SPM_SUBJECTS) |
| `PENDAWAIAN_DOMESTIK_SPM` | `voc_elec_serv` | 2 | Yes (alias — wiring → electrical) |
| `PEMPROSESAN_MAKANAN_SPM` | `voc_food` | 2 | Yes (SPM_SUBJECTS) |
| `PEMBINAAN_DOMESTIK_SPM` | `voc_construct` | 2 | Yes (SPM_SUBJECTS) |
| `LITERATURE_IN_ENGLISH_SPM` | `lit_eng` | 4 | Yes (SUBJECT_NAMES) |
| `KESUSASTERAAN_MELAYU_SPM` | `lit_bm` | in exclude | Yes (SUBJECT_NAMES) |
| `KESUSASTERAAN_CINA_SPM` | `lit_cina` | 1 | Yes (SUBJECT_NAMES) |
| `KESUSASTERAAN_TAMIL_SPM` | `lit_tamil` | 1 | Yes (SUBJECT_NAMES) |
| `KESUSASTERAAN_INGGERIS_SPM` | `lit_eng` | in exclude | Yes (SUBJECT_NAMES) |
| `LUKISAN_SPM` | `lukisan` | in exclude | Yes (SPM_SUBJECTS) |

### Tier 4: New Mappings — Need Frontend Subject Added (46 keys)

These fixture keys have no matching frontend engine key. The frontend `SUBJECT_NAMES` has display entries for some, but the `SPM_SUBJECTS` list (which drives what grades students can enter) doesn't include them. We need to add frontend subjects AND map them.

**Islamic studies (13 keys, ~105 courses each):**

| Fixture Key | New Frontend Key | Frontend Display Name |
|-------------|-----------------|----------------------|
| `PENDIDIKAN_SYARIAH_ISLAMIAH_SPM` | `psi` | Pendidikan Syariah Islamiah |
| `USUL_AL_DIN_SPM` | `usul_aldin` | Usul Al-Din |
| `PENDIDIKAN_AL_QURAN_SPM` | `pqs` | Pend. Al-Quran & Al-Sunnah |
| `AL_SYARIAH_SPM` | `al_syariah` | Al-Syariah |
| `TASAWWUR_ISLAM_SPM` | `tasawwur_islam` | Tasawwur Islam |
| `HIFZ_AL_QURAN_SPM` | `hifz_alquran` | Hifz Al-Quran |
| `MAHARAT_AL_QURAN_SPM` | `maharat_alquran` | Maharat Al-Quran |
| `MANAHIJ_SPM` | `manahij` | Manahij |
| `TURATH_DIRASAT_ISLAMIAH_SPM` | `turath_islamiah` | Turath Islamiah |
| `TURATH_AL_QURAN_SPM` | `turath_quran_sunnah` | Turath Quran & Sunnah |
| `AL_ADAB_SPM` | `adab_balaghah` | Adab & Balaghah |
| `BAHASA_ARAB_TINGGI_SPM` | `bahasa_arab_tinggi` | Bahasa Arab Tinggi |
| `BAHASA_ARAB_MUASIRAH_SPM` | `bahasa_arab` | Bahasa Arab |
| `TURATH_BAHASA_ARAB_SPM` | `turath_bahasa_arab` | Turath Bahasa Arab |
| `BAHASA_ARAB_SPM` | `bahasa_arab` | Bahasa Arab |

Note: `BAHASA_ARAB_SPM` and `BAHASA_ARAB_MUASIRAH_SPM` both map to `bahasa_arab` (same subject, different names).

**Languages (3 keys):**

| Fixture Key | New Frontend Key | Note |
|-------------|-----------------|------|
| `BAHASA_IBAN_SPM` | `bahasa_iban` | Already in SUBJECT_NAMES |
| `BAHASA_KADAZANDUSUN_SPM` | `bahasa_kadazandusun` | Already in SUBJECT_NAMES |
| `BAHASA_SEMAI_SPM` | `bahasa_semai` | Already in SUBJECT_NAMES |

**Vocational/Technical (21 keys):**

| Fixture Key | New Frontend Key | Frontend Display Name |
|-------------|-----------------|----------------------|
| `TEKNOLOGI_KEJURUTERAAN_SPM` | `teknologi_kej` | Teknologi Kejuruteraan |
| `EKONOMI_RUMAH_TANGGA_SPM` | `srt` | Sains Rumah Tangga (alias) |
| `TANAMAN_MAKANAN_SPM` | `tanaman_makanan` | Tanaman Makanan |
| `AKUAKULTUR_SPM` | `akuakultur` | Akuakultur |
| `ASAS_KELESTARIAN_SPM` | `kelestarian` | Sains Kelestarian |
| `APPLIED_SCIENCE_SPM` | `sci` | Sains (alias) |
| `LANDSKAP_DAN_NURSERI_SPM` | `landskap_nurseri` | Landskap & Nurseri |
| `ICT_SPM` | `comp_sci` | Sains Komputer (alias) |
| `PRODUKSI_MULTIMEDIA_SPM` | `produksi_multimedia` | Produksi Multimedia |
| `GRAFIK_BERKOMPUTER_SPM` | `digital_gfx` | Grafik Digital (alias) |
| `UNKNOWN:Teknologi  Binaan` | `teknologi_binaan` | Teknologi Binaan |
| `PRINSIP_ELEKTRIK_SPM` | `prinsip_elektrik` | Prinsip Elektrik & Elektronik |
| `APLIKASI_ELEKTRIK_SPM` | `aplikasi_elektrik` | Aplikasi Elektrik & Elektronik |
| `PEMESINAN_BERKOMPUTER_SPM` | `pemesinan_berkomputer` | Pemesinan Berkomputer |
| `APLIKASI_KOMPUTER_PERNIAGAAN_SPM` | `aplikasi_komputer` | Aplikasi Komputer dlm Perniagaan |
| `KOMUNIKASI_VISUAL_SPM` | `komunikasi_visual` | Komunikasi Visual |
| `BAHAN_BINAAN_SPM` | `bahan_binaan` | Bahan Binaan |
| `TEKNOLOGI_BINAAN_BANGUNAN_SPM` | `teknologi_binaan` | Teknologi Binaan (alias) |
| `REKA_BENTUK_GRAFIK_DIGITAL_SPM` | `digital_gfx` | Grafik Digital (alias) |
| `MENSERVIS_ELEKTRIK_SPM` | `menservis_elektrik` | Menservis Peralatan Elektrik |
| `SENI_REKA_TANDA_SPM` | `produksi_reka_tanda` | Produksi Reka Tanda (alias) |

**Arts/Performance (appearing only in exclude lists — 10 keys):**

| Fixture Key | New Frontend Key | Note |
|-------------|-----------------|------|
| `PENJAGAAN_MUKA_SPM` | `penjagaan_muka` | Already in SUBJECT_NAMES |
| `HIASAN_DALAMAN_SPM` | `hiasan_dalaman` | Already in SUBJECT_NAMES |
| `KERJA_PAIP_SPM` | `kerja_paip` | Already in SUBJECT_NAMES |
| `PEMBUATAN_PERABOT_SPM` | `pembuatan_perabot` | Already in SUBJECT_NAMES |
| `ASUHAN_KANAK_KANAK_SPM` | `asuhan_kanak` | Already in SUBJECT_NAMES |
| `GERONTOLOGI_SPM` | `gerontologi` | Already in SUBJECT_NAMES |
| `MENSERVIS_MOTOSIKAL_SPM` | `menservis_motosikal` | Already in SUBJECT_NAMES |
| `MENSERVIS_PENYEJUKAN_SPM` | `penyejukan` | Already in SUBJECT_NAMES |
| `PRODUKSI_REKA_TANDA_SPM` | `produksi_reka_tanda` | Already in SUBJECT_NAMES |
| Various arts/performance keys | Existing keys | Already in SUBJECT_NAMES |

**Exclude-only keys (already have SUBJECT_NAMES entries):**
- `MULTIMEDIA_KREATIF_SPM` → `multimedia_kreatif`
- `REKA_BENTUK_INDUSTRI_SPM` → `reka_bentuk_industri`
- `REKA_BENTUK_KRAF_SPM` → `reka_bentuk_kraf`
- `REKA_BENTUK_GRAFIK_SPM` → `reka_bentuk_grafik`
- `SEJARAH_PENGURUSAN_SENI_SPM` → `sejarah_seni`
- `SENI_HALUS_2D_SPM` → `seni_halus_2d`
- `SENI_HALUS_3D_SPM` → `seni_halus_3d`
- `AURAL_TEORI_MUZIK_SPM` → `aural_teori_muzik`
- `ALAT_MUZIK_UTAMA_SPM` → `alat_muzik`
- `MUZIK_KOMPUTER_SPM` → `muzik_komputer`
- `TARIAN_SPM` → `tarian`
- `KOREOGRAFI_TARI_SPM` → `koreografi`
- `APRESIASI_TARI_SPM` → `apresiasi_tari`
- `LAKONAN_SPM` → `lakonan`
- `SINOGRAFI_SPM` → `sinografi`
- `PENULISAN_SKRIP_SPM` → `penulisan_skrip`
- `PRODUKSI_SENI_PERSEMBAHAN_SPM` → `produksi_seni`
- `PENDIDIKAN_MUZIK_SPM` → `music`

---

## Tasks

### Task 1: Fix the UNKNOWN Bug in subject_keys.py

**Files:**
- Modify: `Settings/_tools/stpm_requirements/subject_keys.py:190`

**What:** The display name `"Teknologi  Binaan"` (double space) in the HTML source produces `UNKNOWN:Teknologi  Binaan` in fixtures. Add the double-space variant to SPM_SUBJECT_MAP so it maps to `TEKNOLOGI_BINAAN_SPM`.

**Step 1: Add the mapping**

In `subject_keys.py`, add after the existing `"Teknologi Binaan"` entry:

```python
"Teknologi  Binaan": "TEKNOLOGI_BINAAN_SPM",  # double space in MOHE HTML
```

**Step 2: Verify existing tests pass**

Run: `cd Settings/_tools && python -m pytest stpm_requirements/tests/ -v`

**Step 3: Commit**

```bash
git add Settings/_tools/stpm_requirements/subject_keys.py
git commit -m "fix: handle double-space in Teknologi Binaan subject name"
```

---

### Task 2: Expand SPM_CODE_MAP in stpm_engine.py

**Files:**
- Modify: `halatuju_api/apps/courses/stpm_engine.py:86-91`

**What:** Replace the 13-entry SPM_CODE_MAP with the complete mapping (~95 entries). Remove dead entries. Keep the 8 working entries. Add all Tier 3 and Tier 4 mappings.

**Step 1: Write the failing test**

Create test in `halatuju_api/apps/courses/tests/test_stpm_engine.py`:

```python
def test_spm_code_map_covers_all_fixture_keys(self):
    """Every SPM subject key in fixtures must have an SPM_CODE_MAP entry."""
    import json
    from pathlib import Path
    from apps.courses.stpm_engine import SPM_CODE_MAP

    fixture_path = Path(__file__).parent.parent / 'fixtures' / 'stpm_requirements.json'
    with open(fixture_path, 'r', encoding='utf-8') as f:
        fixtures = json.load(f)

    all_keys = set()
    for fix in fixtures:
        sg = fix['fields'].get('spm_subject_group')
        if sg:
            groups = sg if isinstance(sg, list) else [sg]
            for g in groups:
                for s in g.get('subjects', []):
                    all_keys.add(s)
                for s in g.get('exclude', []):
                    all_keys.add(s)

    unmapped = []
    for key in sorted(all_keys):
        if key not in SPM_CODE_MAP and not key.startswith('UNKNOWN:'):
            unmapped.append(key)

    assert unmapped == [], f"Unmapped fixture keys: {unmapped}"
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_engine.py::TestStpmEngine::test_spm_code_map_covers_all_fixture_keys -v`
Expected: FAIL (85 unmapped keys)

**Step 3: Replace SPM_CODE_MAP**

Replace lines 86-91 in `stpm_engine.py` with:

```python
# Map fixture subject codes (used in spm_subject_group JSON) to frontend engine keys.
# Frontend keys come from halatuju-web/src/lib/subjects.ts (SPM_SUBJECTS + SUBJECT_NAMES).
# Fixture keys come from Settings/_tools/stpm_requirements/subject_keys.py (SPM_SUBJECT_MAP).
SPM_CODE_MAP = {
    # --- Core subjects (always mapped) ---
    'BM': 'bm',
    'BI': 'eng',
    'MATH': 'math',
    'ADD_MATH': 'addmath',
    'SEJARAH': 'hist',

    # --- Science subjects ---
    'PHYSICS_SPM': 'phy',
    'CHEMISTRY_SPM': 'chem',
    'BIOLOGY_SPM': 'bio',
    'SCIENCE_SPM': 'sci',
    'SAINS_TAMBAHAN_SPM': 'addsci',
    'APPLIED_SCIENCE_SPM': 'sci',

    # --- Arts / humanities ---
    'EKONOMI_SPM': 'ekonomi',
    'EKONOMI_ASAS_SPM': 'ekonomi',
    'PRINSIP_PERAKAUNAN_SPM': 'poa',
    'PERNIAGAAN_SPM': 'business',
    'PERDAGANGAN_SPM': 'business',
    'GEOGRAFI_SPM': 'geo',
    'PENDIDIKAN_MORAL_SPM': 'moral',
    'PENDIDIKAN_ISLAM_SPM': 'islam',
    'PENDIDIKAN_SENI_VISUAL_SPM': 'psv',
    'PENGAJIAN_KEUSAHAWANAN_SPM': 'keusahawanan',
    'LUKISAN_SPM': 'lukisan',
    'BAHASA_CINA_SPM': 'b_cina',
    'BAHASA_TAMIL_SPM': 'b_tamil',
    'SAINS_RUMAH_TANGGA_SPM': 'srt',
    'EKONOMI_RUMAH_TANGGA_SPM': 'srt',

    # --- Islamic studies ---
    'PENDIDIKAN_SYARIAH_ISLAMIAH_SPM': 'psi',
    'USUL_AL_DIN_SPM': 'usul_aldin',
    'PENDIDIKAN_AL_QURAN_SPM': 'pqs',
    'AL_SYARIAH_SPM': 'al_syariah',
    'TASAWWUR_ISLAM_SPM': 'tasawwur_islam',
    'HIFZ_AL_QURAN_SPM': 'hifz_alquran',
    'MAHARAT_AL_QURAN_SPM': 'maharat_alquran',
    'MANAHIJ_SPM': 'manahij',
    'TURATH_DIRASAT_ISLAMIAH_SPM': 'turath_islamiah',
    'TURATH_AL_QURAN_SPM': 'turath_quran_sunnah',
    'AL_ADAB_SPM': 'adab_balaghah',
    'TURATH_BAHASA_ARAB_SPM': 'turath_bahasa_arab',
    'BAHASA_ARAB_SPM': 'bahasa_arab',
    'BAHASA_ARAB_TINGGI_SPM': 'bahasa_arab_tinggi',
    'BAHASA_ARAB_MUASIRAH_SPM': 'bahasa_arab',

    # --- Languages ---
    'BAHASA_IBAN_SPM': 'bahasa_iban',
    'BAHASA_KADAZANDUSUN_SPM': 'bahasa_kadazandusun',
    'BAHASA_SEMAI_SPM': 'bahasa_semai',

    # --- Literature ---
    'LITERATURE_IN_ENGLISH_SPM': 'lit_eng',
    'KESUSASTERAAN_MELAYU_SPM': 'lit_bm',
    'KESUSASTERAAN_CINA_SPM': 'lit_cina',
    'KESUSASTERAAN_TAMIL_SPM': 'lit_tamil',
    'KESUSASTERAAN_INGGERIS_SPM': 'lit_eng',

    # --- Technical / engineering ---
    'LUKISAN_KEJURUTERAAN_SPM': 'eng_draw',
    'KEJURUTERAAN_AWAM_SPM': 'eng_civil',
    'KEJURUTERAAN_MEKANIKAL_SPM': 'eng_mech',
    'KEJURUTERAAN_EE_SPM': 'eng_elec',
    'GRAFIK_KOMUNIKASI_TEKNIKAL_SPM': 'gkt',
    'SAINS_KOMPUTER_SPM': 'comp_sci',
    'ICT_SPM': 'comp_sci',
    'REKA_CIPTA_SPM': 'reka_cipta',
    'TEKNOLOGI_KEJURUTERAAN_SPM': 'teknologi_kej',
    'ASAS_KELESTARIAN_SPM': 'kelestarian',
    'GRAFIK_BERKOMPUTER_SPM': 'digital_gfx',
    'REKA_BENTUK_GRAFIK_DIGITAL_SPM': 'digital_gfx',
    'PRINSIP_ELEKTRIK_SPM': 'prinsip_elektrik',
    'APLIKASI_ELEKTRIK_SPM': 'aplikasi_elektrik',
    'PEMESINAN_BERKOMPUTER_SPM': 'pemesinan_berkomputer',
    'APLIKASI_KOMPUTER_PERNIAGAAN_SPM': 'aplikasi_komputer',
    'KOMUNIKASI_VISUAL_SPM': 'komunikasi_visual',
    'BAHAN_BINAAN_SPM': 'bahan_binaan',
    'TEKNOLOGI_BINAAN_SPM': 'teknologi_binaan',
    'TEKNOLOGI_BINAAN_BANGUNAN_SPM': 'teknologi_binaan',
    'PRODUKSI_MULTIMEDIA_SPM': 'produksi_multimedia',
    'SENI_REKA_TANDA_SPM': 'produksi_reka_tanda',

    # --- Sports ---
    'PENGETAHUAN_SAINS_SUKAN_SPM': 'sports_sci',
    'SAINS_SUKAN_SPM': 'sports_sci',

    # --- Agriculture ---
    'PERTANIAN_SPM': 'pertanian',
    'SAINS_PERTANIAN_SPM': 'pertanian',
    'TANAMAN_MAKANAN_SPM': 'tanaman_makanan',
    'AKUAKULTUR_SPM': 'akuakultur',
    'LANDSKAP_DAN_NURSERI_SPM': 'landskap_nurseri',

    # --- Vocational / MPV ---
    'KATERING_SPM': 'katering',
    'REKAAN_JAHITAN_SPM': 'rekaan_jahitan',
    'KIMPALAN_SPM': 'kimpalan',
    'MENSERVIS_AUTOMOBIL_SPM': 'menservis_automobil',
    'PENDAWAIAN_DOMESTIK_SPM': 'pendawaian_domestik',
    'PEMPROSESAN_MAKANAN_SPM': 'pemprosesan_makanan',
    'PEMBINAAN_DOMESTIK_SPM': 'pembinaan_domestik',
    'PENJAGAAN_MUKA_SPM': 'penjagaan_muka',
    'HIASAN_DALAMAN_SPM': 'hiasan_dalaman',
    'KERJA_PAIP_SPM': 'kerja_paip',
    'PEMBUATAN_PERABOT_SPM': 'pembuatan_perabot',
    'ASUHAN_KANAK_KANAK_SPM': 'asuhan_kanak',
    'GERONTOLOGI_SPM': 'gerontologi',
    'MENSERVIS_MOTOSIKAL_SPM': 'menservis_motosikal',
    'MENSERVIS_PENYEJUKAN_SPM': 'penyejukan',
    'MENSERVIS_ELEKTRIK_SPM': 'menservis_elektrik',

    # --- Arts / performance (mostly in exclude lists) ---
    'MULTIMEDIA_KREATIF_SPM': 'multimedia_kreatif',
    'REKA_BENTUK_GRAFIK_SPM': 'reka_bentuk_grafik',
    'REKA_BENTUK_INDUSTRI_SPM': 'reka_bentuk_industri',
    'REKA_BENTUK_KRAF_SPM': 'reka_bentuk_kraf',
    'SEJARAH_PENGURUSAN_SENI_SPM': 'sejarah_seni',
    'SENI_HALUS_2D_SPM': 'seni_halus_2d',
    'SENI_HALUS_3D_SPM': 'seni_halus_3d',
    'AURAL_TEORI_MUZIK_SPM': 'aural_teori_muzik',
    'ALAT_MUZIK_UTAMA_SPM': 'alat_muzik',
    'MUZIK_KOMPUTER_SPM': 'muzik_komputer',
    'TARIAN_SPM': 'tarian',
    'KOREOGRAFI_TARI_SPM': 'koreografi',
    'APRESIASI_TARI_SPM': 'apresiasi_tari',
    'LAKONAN_SPM': 'lakonan',
    'SINOGRAFI_SPM': 'sinografi',
    'PENULISAN_SKRIP_SPM': 'penulisan_skrip',
    'PRODUKSI_SENI_PERSEMBAHAN_SPM': 'produksi_seni',
    'PRODUKSI_REKA_TANDA_SPM': 'produksi_reka_tanda',
    'PENDIDIKAN_MUZIK_SPM': 'music',
}
```

**Step 4: Run test to verify it passes**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_engine.py::TestStpmEngine::test_spm_code_map_covers_all_fixture_keys -v`
Expected: PASS

**Step 5: Run existing STPM engine tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_engine.py -v`
Expected: All 15 pass

**Step 6: Commit**

```bash
git add halatuju_api/apps/courses/stpm_engine.py halatuju_api/apps/courses/tests/test_stpm_engine.py
git commit -m "feat: expand SPM_CODE_MAP from 13 to 95 entries for complete subject coverage"
```

---

### Task 3: Add Missing SPM Subjects to Frontend subjects.ts

**Files:**
- Modify: `halatuju-web/src/lib/subjects.ts`

**What:** Add new SPM subjects to `SPM_SUBJECTS` array so students who took these subjects can enter grades. Currently the frontend only has 46 subjects — students who took Islamic studies, vocational, or niche technical subjects can't enter their SPM grades.

**New subjects to add to SPM_SUBJECTS** (grouped by category):

```typescript
// Islamic studies (add to 'elective' category)
{ id: 'psi', category: 'elective' },
{ id: 'pqs', category: 'elective' },
{ id: 'tasawwur_islam', category: 'elective' },
{ id: 'usul_aldin', category: 'elective' },
{ id: 'al_syariah', category: 'elective' },
{ id: 'manahij', category: 'elective' },
{ id: 'hifz_alquran', category: 'elective' },
{ id: 'maharat_alquran', category: 'elective' },
{ id: 'turath_islamiah', category: 'elective' },
{ id: 'turath_quran_sunnah', category: 'elective' },
{ id: 'turath_bahasa_arab', category: 'elective' },
{ id: 'adab_balaghah', category: 'elective' },

// Languages (add to 'elective' category)
{ id: 'bahasa_arab', category: 'elective' },
{ id: 'bahasa_arab_tinggi', category: 'elective' },
{ id: 'bahasa_iban', category: 'elective' },
{ id: 'bahasa_kadazandusun', category: 'elective' },
{ id: 'bahasa_semai', category: 'elective' },

// Literature (add to 'arts' category)
{ id: 'lit_bm', category: 'arts' },
{ id: 'lit_eng', category: 'arts' },
{ id: 'lit_cina', category: 'arts' },
{ id: 'lit_tamil', category: 'arts' },

// Technical (add to 'technical' category)
{ id: 'teknologi_kej', category: 'technical' },
{ id: 'kelestarian', category: 'technical' },
{ id: 'digital_gfx', category: 'technical' },
{ id: 'prinsip_elektrik', category: 'technical' },
{ id: 'aplikasi_elektrik', category: 'technical' },
{ id: 'pemesinan_berkomputer', category: 'technical' },
{ id: 'aplikasi_komputer', category: 'technical' },
{ id: 'komunikasi_visual', category: 'technical' },
{ id: 'bahan_binaan', category: 'technical' },
{ id: 'teknologi_binaan', category: 'technical' },
{ id: 'produksi_multimedia', category: 'technical' },
{ id: 'produksi_reka_tanda', category: 'technical' },

// Sports / agriculture (add to 'elective' category)
{ id: 'addsci', category: 'elective' },   // already exists, skip
{ id: 'tanaman_makanan', category: 'elective' },
{ id: 'akuakultur', category: 'elective' },
{ id: 'landskap_nurseri', category: 'elective' },

// Vocational (add to 'elective' category)
{ id: 'katering', category: 'elective' },
{ id: 'rekaan_jahitan', category: 'elective' },
{ id: 'kimpalan', category: 'elective' },
{ id: 'menservis_automobil', category: 'elective' },
{ id: 'pendawaian_domestik', category: 'elective' },
{ id: 'pemprosesan_makanan', category: 'elective' },
{ id: 'pembinaan_domestik', category: 'elective' },
{ id: 'penjagaan_muka', category: 'elective' },
{ id: 'hiasan_dalaman', category: 'elective' },
{ id: 'kerja_paip', category: 'elective' },
{ id: 'pembuatan_perabot', category: 'elective' },
{ id: 'asuhan_kanak', category: 'elective' },
{ id: 'gerontologi', category: 'elective' },
{ id: 'menservis_motosikal', category: 'elective' },
{ id: 'penyejukan', category: 'elective' },
{ id: 'menservis_elektrik', category: 'elective' },

// Arts / performance (add to 'arts' category)
{ id: 'multimedia_kreatif', category: 'arts' },
{ id: 'reka_bentuk_grafik', category: 'arts' },
{ id: 'reka_bentuk_industri', category: 'arts' },
{ id: 'reka_bentuk_kraf', category: 'arts' },
{ id: 'sejarah_seni', category: 'arts' },
{ id: 'seni_halus_2d', category: 'arts' },
{ id: 'seni_halus_3d', category: 'arts' },
{ id: 'aural_teori_muzik', category: 'arts' },
{ id: 'alat_muzik', category: 'arts' },
{ id: 'muzik_komputer', category: 'arts' },
{ id: 'tarian', category: 'arts' },
{ id: 'koreografi', category: 'arts' },
{ id: 'apresiasi_tari', category: 'arts' },
{ id: 'lakonan', category: 'arts' },
{ id: 'sinografi', category: 'arts' },
{ id: 'penulisan_skrip', category: 'arts' },
{ id: 'produksi_seni', category: 'arts' },
```

Also add SUBJECT_NAMES entries for any new keys that don't already have display names (e.g. `teknologi_kej`, `prinsip_elektrik`, `aplikasi_elektrik`, `pemesinan_berkomputer`, `aplikasi_komputer`, `komunikasi_visual`, `bahan_binaan`, `teknologi_binaan`).

**Also update SPM_PREREQ_OPTIONAL** to include subjects commonly required as STPM SPM prerequisites:

```typescript
export const SPM_PREREQ_OPTIONAL = [
  { id: 'addmath', name: 'Matematik Tambahan' },
  { id: 'sci', name: 'Sains' },
  { id: 'phy', name: 'Fizik' },
  { id: 'chem', name: 'Kimia' },
  { id: 'bio', name: 'Biologi' },
  { id: 'poa', name: 'Prinsip Perakaunan' },
  { id: 'ekonomi', name: 'Ekonomi' },
  { id: 'islam', name: 'Pendidikan Islam' },
  { id: 'moral', name: 'Pendidikan Moral' },
]
```

**Step 1: Add all new SUBJECT_NAMES entries**

**Step 2: Add all new SPM_SUBJECTS entries**

**Step 3: Update SPM_PREREQ_OPTIONAL**

**Step 4: Run frontend tests**

Run: `cd halatuju-web && npm test`

**Step 5: Commit**

```bash
git add halatuju-web/src/lib/subjects.ts
git commit -m "feat: add 70+ SPM subjects to frontend for complete STPM prerequisite coverage"
```

---

### Task 4: Regenerate Fixtures (fix UNKNOWN bug)

**Files:**
- Modify: `halatuju_api/apps/courses/fixtures/stpm_requirements.json`

**What:** After Task 1 (fixing the double-space bug), regenerate fixtures so the 3 courses with `UNKNOWN:Teknologi  Binaan` get the correct `TEKNOLOGI_BINAAN_SPM` key.

**Step 1: Regenerate fixtures**

Run the pipeline (parse → fixture) for the affected courses. The exact command depends on having the source HTML/JSON still available.

Alternative: Manual fix — find-and-replace `UNKNOWN:Teknologi  Binaan` with `TEKNOLOGI_BINAAN_SPM` in the fixture file.

**Step 2: Verify fixture integrity**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_data_loading.py -v`

**Step 3: Commit**

```bash
git add halatuju_api/apps/courses/fixtures/stpm_requirements.json
git commit -m "fix: replace UNKNOWN:Teknologi Binaan with correct key in fixtures"
```

---

### Task 5: Update Golden Master Baseline

**Files:**
- Modify: `halatuju_api/apps/courses/tests/test_stpm_golden_master.py:77`

**What:** With SPM_CODE_MAP expanded, more students will qualify for more courses. The golden master baseline (currently 1976) must be updated.

**Step 1: Run golden master with baseline set to None**

Temporarily set `GOLDEN_BASELINE = None` and run:
```bash
cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_golden_master.py -v -s
```

This prints the new per-student counts and total.

**Step 2: Verify the new count is HIGHER than 1976**

The count must increase because we fixed false negatives (students who should qualify but didn't due to unmapped keys). If it decreases, something is wrong.

**Step 3: Update the baseline**

Replace `GOLDEN_BASELINE = 1976` with the new number.

**Step 4: Run golden master to confirm it passes**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_golden_master.py -v`

**Step 5: Run ALL tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: 645+ tests pass, 0 failures

**Step 6: Commit**

```bash
git add halatuju_api/apps/courses/tests/test_stpm_golden_master.py
git commit -m "test: update STPM golden master baseline after SPM_CODE_MAP expansion"
```

---

### Task 6: Update Documentation

**Files:**
- Modify: `halatuju_api/CLAUDE.md` — update STPM golden master number
- Modify: `Settings/_workflows/stpm-requirements-update.md` — update stale golden master reference

**Step 1: Update CLAUDE.md**

Replace old golden master number with new one in the testing section.

**Step 2: Update workflow doc**

The workflow doc `stpm-requirements-update.md` references golden master 2103 (stale). Update to the new number.

**Step 3: Commit**

```bash
git add halatuju_api/CLAUDE.md Settings/_workflows/stpm-requirements-update.md
git commit -m "docs: update STPM golden master baseline in docs"
```

---

## Execution Order

Tasks 1-2 are backend-only and can be done first. Task 3 is frontend-only. Task 4 depends on Task 1. Task 5 depends on Tasks 2+4. Task 6 depends on Task 5.

```
Task 1 (fix UNKNOWN bug) ──→ Task 4 (regenerate fixtures) ──┐
Task 2 (expand SPM_CODE_MAP) ──────────────────────────────→ Task 5 (golden master) → Task 6 (docs)
Task 3 (frontend subjects) ────────────────────────────────→ (independent)
```

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Golden master changes | Expected — more matches is correct. Verify direction (up, not down). |
| Frontend UI overwhelmed by 100+ subjects | Group by category + collapsible sections (future UI work, not in scope). |
| Alias collisions (two fixture keys → same frontend key) | Intentional — e.g. EKONOMI_SPM and EKONOMI_ASAS_SPM both → ekonomi. This is correct. |
| Students don't see niche subjects in grade entry | Task 3 adds them to SPM_SUBJECTS. If UI is too long, that's a separate UI task. |
