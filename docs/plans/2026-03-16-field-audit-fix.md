# Field Audit Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 240 course-to-field_key misclassifications across both SPM and STPM classifiers, apply corrections to Supabase.

**Architecture:** Update two deterministic classifier scripts (`backfill_spm_field_key.py` and `classify_stpm_fields.py`) with audited rules from `docs/propose_audit.py`, update tests, apply to Supabase via `--save` flag.

**Tech Stack:** Django management commands, Supabase PostgreSQL, pytest

---

### Task 1: Fix STPM classifier — course name overrides

**Files:**
- Modify: `halatuju_api/apps/courses/management/commands/classify_stpm_fields.py:113-131`

**Step 1: Add course-name override rules at the top of `classify_stpm_course()`**

Insert these rules after the variable assignments (line 125) but BEFORE the SPM-matching delegation (line 130):

```python
    # ── COURSE NAME OVERRIDES (name trumps MOHE category) ──
    # Kejuruteraan Kimia misclassified under wrong category
    if 'kejuruteraan kimia' in n and 'bioteknologi' not in n and 'makanan' not in n:
        return 'kimia-proses'
    # Veterinary is a medical doctorate, not agriculture
    if 'veterinar' in n:
        return 'perubatan'
```

**Step 2: Verify dry run locally (no DB needed — just import the function)**

Run: `cd halatuju_api && python -c "from apps.courses.management.commands.classify_stpm_fields import classify_stpm_course; print(classify_stpm_course('Veterinar', 'Veterinar', 'Doktor Perubatan Veterinar'))"`
Expected: `perubatan` (was `pertanian`)

---

### Task 2: Fix STPM classifier — health field split

**Files:**
- Modify: `halatuju_api/apps/courses/management/commands/classify_stpm_fields.py:142-153`

**Step 1: Replace the single `perubatan` health block with split blocks**

Replace the current health block (lines 142-148) that maps everything to `perubatan`:

OLD:
```python
    # ── Health & Medical ──
    if match_any(c, ['perubatan', 'kejururawatan', 'pergigian', 'pengimejan',
                      'dietetik', 'nutrisi', 'optometri', 'audiologi',
                      'patologi', 'kesihatan', 'bioperubatan',
                      'pemakanan', 'fisioterapi', 'pemulihan cara kerja',
                      'teknologi makmal perubatan', 'biomolekul']):
        return 'perubatan'
```

NEW:
```python
    # ── Health & Medical (split into perubatan / kejururawatan / pergigian) ──
    # Pergigian
    if 'pergigian' in c:
        return 'pergigian'
    # Allied health → kejururawatan
    allied_health = [
        'kejururawatan', 'fisioterapi', 'optometri', 'audiologi',
        'dietetik', 'patologi', 'pengimejan', 'pemulihan cara kerja',
        'teknologi makmal perubatan',
    ]
    if match_any(c, allied_health):
        return 'kejururawatan'
    # Nutrition / food science → kulinari (NOT kejururawatan)
    if match_any(c, ['nutrisi', 'pemakanan', 'sains pemakanan']):
        return 'kulinari'
    # Remaining medical
    if match_any(c, ['perubatan', 'kesihatan', 'bioperubatan', 'biomolekul']):
        return 'perubatan'
```

**Step 2: Also add course-name checks for health in `_classify_spm_matching` or after SPM delegation**

After the SPM-matching delegation block but before other rules, add name-based health overrides:

```python
    # ── Course name health overrides (catch misclassified by category) ──
    if 'pergigian' in n:
        return 'pergigian'
    if 'farmasi' in n or 'farmaseutikal' in n:
        return 'farmasi'
    if match_any(n, ['kejururawatan', 'fisioterapi', 'optometri', 'audiologi',
                      'dietetik', 'terapi carakerja', 'pemulihan cara kerja',
                      'pengimejan perubatan', 'pengimejan diagnostik',
                      'sinaran perubatan', 'teknologi makmal perubatan']):
        return 'kejururawatan'
    # Nutrition / food science by name → kulinari
    if match_any(n, ['pemakanan', 'sains makanan', 'teknologi makanan',
                      'jaminan makanan', 'makanan halal']):
        return 'kulinari'
```

---

### Task 3: Fix STPM classifier — sciences split + pendidikan protection

**Files:**
- Modify: `halatuju_api/apps/courses/management/commands/classify_stpm_fields.py:180-220`

**Step 1: Add pendidikan protection**

After the course name health overrides from Task 2, add:

```python
    # ── PENDIDIKAN protection: never reclassify education degrees ──
    if c == 'pendidikan':
        return 'pendidikan'
```

(This already exists at line 49 inside `_classify_spm_matching`, but we need it as a guard for the rules below too.)

**Step 2: Replace sciences blocks**

Replace the current Matematik/Fizik/Biology blocks that all map to `sains-hayat`:

OLD (lines 191-216):
```python
    # ── Mathematics & Statistics ──
    if match_any(c, ['matematik', 'statistik', 'aktuari']):
        if 'kewangan' in c:
            return 'perakaunan'
        return 'sains-hayat'

    # ── Physics ──
    if 'fizik' in c:
        if 'perubatan' in c:
            return 'perubatan'
        return 'sains-hayat'

    # ── Biology & Life Sciences ──
    ...
    # ── Geosciences ──
    ...
    # ── Materials Science ──
    ...
```

NEW:
```python
    # ── Sains Data: statistics, actuarial, data science ──
    if match_any(c, ['statistik', 'sains aktuari', 'sains data', 'analitik']):
        return 'sains-data'

    # ── Mathematics ──
    if match_any(c, ['matematik']):
        if 'kewangan' in c:
            return 'perakaunan'
        return 'sains-fizikal'

    # ── Physics ──
    if 'fizik' in c:
        if 'perubatan' in c:
            return 'perubatan'
        return 'sains-fizikal'

    # ── Geosciences & Materials ──
    if match_any(c, ['geologi', 'geosains', 'sains bumi', 'sains bahan']):
        return 'sains-fizikal'

    # ── Biology & Life Sciences ──
    if match_any(c, ['biologi', 'bioteknologi', 'bio-teknologi',
                      'mikrobiologi', 'biokimia', 'sains gunaan',
                      'sains kognitif']):
        return 'sains-hayat'
```

**Step 3: Replace Data Science block**

OLD (lines 217-219):
```python
    # ── Data Science / Analytics ──
    if match_any(c, ['data', 'analitik']):
        return 'it-rangkaian'
```

DELETE this block (now handled by the sains-data rule above).

---

### Task 4: Fix STPM classifier — bahasa, komunikasi, humanities extraction

**Files:**
- Modify: `halatuju_api/apps/courses/management/commands/classify_stpm_fields.py:180-190`

**Step 1: Replace the Language & Humanities block that maps everything to `umum`**

OLD (lines 180-185):
```python
    # ── Language & Humanities (before Communication, to catch 'Bahasa & Komunikasi') ──
    if match_any(c, ['bahasa', 'linguistik', 'kesusasteraan', 'kemanusiaan',
                      'persuratan', 'sejarah', 'tamadun', 'warisan',
                      'pengajian melayu', 'pengajian cina', 'pengajian india',
                      'pengajian asia']):
        return 'umum'
```

NEW:
```python
    # ── Bahasa & Kesusasteraan ──
    bahasa_cats = [
        'bahasa', 'linguistik', 'kesusasteraan', 'persuratan',
        'pengajian melayu', 'pengajian cina', 'pengajian india',
    ]
    if match_any(c, bahasa_cats):
        return 'bahasa'

    # ── Sains Sosial: history, heritage, area studies ──
    if match_any(c, ['sejarah', 'tamadun', 'warisan', 'pengajian asia',
                      'kemanusiaan', 'geografi']):
        # But Islamic humanities → pengajian-islam
        if match_any(n, ['islam', 'syariah', 'dakwah']):
            return 'pengajian-islam'
        return 'sains-sosial'
```

**Step 2: Replace Communication & Media block**

OLD (lines 187-189):
```python
    # ── Communication & Media ──
    if match_any(c, ['komunikasi', 'media']):
        return 'multimedia'
```

NEW:
```python
    # ── Komunikasi & Media ──
    if match_any(c, ['komunikasi', 'media']):
        return 'komunikasi'
```

---

### Task 5: Fix STPM classifier — pertanian cleanup + senireka + umum

**Files:**
- Modify: `halatuju_api/apps/courses/management/commands/classify_stpm_fields.py:253-290`

**Step 1: Add pertanian course-name overrides in the SPM-matching handler**

In `_classify_spm_matching()`, replace the pertanian handler:

OLD (lines 78-81):
```python
    if c == 'pertanian & bio-industri':
        if 'alam sekitar' in n:
            return 'alam-sekitar'
        return 'pertanian'
```

NEW:
```python
    if c == 'pertanian & bio-industri':
        if match_any(n, ['alam sekitar', 'sekitaran', 'persekitaran',
                          'biodiversiti', 'sains laut', 'biologi marin']):
            return 'alam-sekitar'
        if match_any(n, ['sains makanan', 'teknologi makanan', 'jaminan makanan',
                          'produk agro', 'perkhidmatan makanan']):
            return 'kulinari'
        # Pure biology/biotech without agricultural context → sains-hayat
        if match_any(n, ['biologi', 'biokimia', 'mikrobiologi', 'genetik',
                          'bioteknologi', 'bioinformatik']):
            if not match_any(n, ['pertanian', 'agro', 'tumbuhan', 'tanaman',
                                  'perladangan', 'hortikultur', 'penternakan',
                                  'ternakan', 'haiwan']):
                return 'sains-hayat'
        if 'kimia industri' in n:
            return 'kimia-proses'
        return 'pertanian'
```

**Step 2: Add seni reka course-name overrides**

In `_classify_spm_matching()`, replace the seni reka handler:

OLD (lines 89-92):
```python
    if c == 'seni reka & kreatif':
        if match_any(n, ['animasi', 'multimedia', 'permainan', 'games']):
            return 'multimedia'
        return 'senireka'
```

NEW:
```python
    if c == 'seni reka & kreatif':
        if match_any(n, ['animasi', 'multimedia', 'permainan', 'games',
                          'sinematografi', 'filem']):
            return 'multimedia'
        if 'sejarah' in n:
            return 'sains-sosial'
        if 'kesusasteraan' in n:
            return 'bahasa'
        return 'senireka'
```

**Step 3: Fix veterinar in catch-all section**

OLD (lines 258-261):
```python
    # ── Agriculture & Biodiversity ──
    if match_any(c, ['perikanan', 'akuakultur', 'biodiversiti', 'veterinar',
                      'pengurusan taman']):
        return 'pertanian'
```

NEW:
```python
    # ── Agriculture & Biodiversity ──
    if match_any(c, ['perikanan', 'akuakultur', 'pengurusan taman']):
        return 'pertanian'
    if 'biodiversiti' in c:
        return 'alam-sekitar'
```

(Veterinar already handled by course-name override in Task 1.)

**Step 4: Fix sains-hayat chemistry extraction**

After the course-name health overrides area, add a sains-hayat chemistry check:

```python
    # ── Sains-hayat: pure chemistry → kimia-proses ──
    # (After SPM-matching delegation, catches courses in sains-hayat that are really chemistry)
```

This will be done in the SPM-matching handler by adding chemistry name checks.

---

### Task 6: Fix SPM classifier — UA course corrections

**Files:**
- Modify: `halatuju_api/apps/courses/management/commands/backfill_spm_field_key.py:250-276`

**Step 1: Add UA-specific overrides before the `umum` catch-all**

Before the `# ── UMUM catch-all ──` section (line 254), add:

```python
    # ── UA (UiTM) course-name overrides ──
    if match_any(c, ['muzik', 'tari', 'teater']):
        return 'senireka'
    if 'pendidikan awal kanak-kanak' in c:
        return 'pendidikan'
    if 'teknologi makmal' in c and 'perubatan' not in c:
        return 'sains-hayat'
    if c == 'diploma sains' or (match_any(c, ['diploma sains']) and 'sukan' not in c):
        return 'sains-hayat'
    if 'sains (matematik)' in c:
        return 'sains-fizikal'
    if 'sains sukan' in c or 'kejurulatihan' in c:
        return 'sains-sosial'
    if match_any(c, ['bahasa etnik', 'bahasa inggeris']):
        return 'bahasa'
    if 'turath islami' in c:
        return 'pengajian-islam'
```

**Step 2: Fix the SPM keyword matching for komunikasi false positive**

In the `# Humanities` keyword section (line 251), update to avoid false positives:

OLD:
```python
    # Humanities
    if match_any(f, ['bahasa', 'pengajian islam', 'sains sosial', 'kesetiausahaan']):
        return 'umum'
```

NEW:
```python
    # Humanities
    if match_any(f, ['pengajian islam']):
        return 'pengajian-islam'
    if match_any(f, ['bahasa']):
        return 'bahasa'
    if match_any(f, ['sains sosial', 'kesetiausahaan']):
        return 'sains-sosial'
```

---

### Task 7: Fix SPM classifier — food science and other name-based corrections

**Files:**
- Modify: `halatuju_api/apps/courses/management/commands/backfill_spm_field_key.py`

**Step 1: Add course-name overrides near the top of `classify_course()`**

After the variable assignments (line 30-32), before the `# ── PENDIDIKAN ──` block, add:

```python
    # ── COURSE NAME OVERRIDES (name trumps frontend_label) ──
    # Food science / nutrition → kulinari
    if match_any(c, ['sains makanan', 'teknologi makanan', 'pemakanan']):
        return 'kulinari'
    # Farmasi
    if 'farmasi' in c or 'farmaseutikal' in c:
        return 'farmasi'
    # Kejururawatan
    if 'kejururawatan' in c:
        return 'kejururawatan'
    # Pergigian
    if 'pergigian' in c:
        return 'pergigian'
    # Kejuruteraan Kimia in wrong category
    if 'kejuruteraan kimia' in c and 'bioteknologi' not in c and 'makanan' not in c:
        return 'kimia-proses'
```

---

### Task 8: Update tests for new classifications

**Files:**
- Modify: `halatuju_api/apps/courses/tests/test_field_taxonomy.py`

**Step 1: Update existing tests whose expected values change**

```python
    # test_stpm_kejururawatan: perubatan → kejururawatan
    def test_stpm_kejururawatan(self):
        self.assertEqual(
            classify_stpm_course('Kejururawatan', 'Kejururawatan', 'Sarjana Muda Sains Kejururawatan'),
            'kejururawatan'  # was 'perubatan'
        )

    # test_stpm_bahasa_linguistik: umum → bahasa
    def test_stpm_bahasa_linguistik(self):
        self.assertEqual(
            classify_stpm_course('Bahasa & Linguistik', 'Bahasa', 'Sarjana Muda Linguistik'),
            'bahasa'  # was 'umum'
        )

    # test_stpm_matematik: sains-hayat → sains-fizikal
    def test_stpm_matematik(self):
        self.assertEqual(
            classify_stpm_course('Matematik', 'Matematik', 'Sarjana Muda Matematik'),
            'sains-fizikal'  # was 'sains-hayat'
        )

    # test_stpm_fizik: sains-hayat → sains-fizikal
    def test_stpm_fizik(self):
        self.assertEqual(
            classify_stpm_course('Fizik', 'Fizik', 'Sarjana Muda Fizik'),
            'sains-fizikal'  # was 'sains-hayat'
        )

    # test_stpm_geologi: sains-hayat → sains-fizikal
    def test_stpm_geologi(self):
        self.assertEqual(
            classify_stpm_course('Geologi', 'Geologi', 'Sarjana Muda Geologi'),
            'sains-fizikal'  # was 'sains-hayat'
        )

    # test_stpm_sains_bahan: sains-hayat → sains-fizikal
    def test_stpm_sains_bahan(self):
        self.assertEqual(
            classify_stpm_course('Sains Bahan', 'Sains Bahan', 'Sarjana Muda Sains Bahan'),
            'sains-fizikal'  # was 'sains-hayat'
        )

    # test_stpm_komunikasi_media: multimedia → komunikasi
    def test_stpm_komunikasi_media(self):
        self.assertEqual(
            classify_stpm_course('Komunikasi & Media', 'Komunikasi', 'Sarjana Muda Komunikasi'),
            'komunikasi'  # was 'multimedia'
        )

    # test_stpm_sains_data: it-rangkaian → sains-data
    def test_stpm_sains_data(self):
        self.assertEqual(
            classify_stpm_course('Sains Data', 'Sains Data', 'Sarjana Muda Sains Data'),
            'sains-data'  # was 'it-rangkaian'
        )

    # test_stpm_veterinar: pertanian → perubatan
    def test_stpm_veterinar(self):
        self.assertEqual(
            classify_stpm_course('Veterinar', 'Veterinar', 'Doktor Perubatan Veterinar'),
            'perubatan'  # was 'pertanian'
        )
```

**Step 2: Add new tests for audit-specific rules**

```python
    # ── New audit tests ──

    def test_stpm_pergigian(self):
        self.assertEqual(
            classify_stpm_course('Pergigian', 'Pergigian', 'Sarjana Muda Pergigian'),
            'pergigian'
        )

    def test_stpm_allied_health_fisioterapi(self):
        self.assertEqual(
            classify_stpm_course('Fisioterapi', 'Fisioterapi', 'Sarjana Muda Fisioterapi'),
            'kejururawatan'
        )

    def test_stpm_nutrition_not_kejururawatan(self):
        """Nutrition → kulinari, NOT kejururawatan."""
        self.assertEqual(
            classify_stpm_course('Pemakanan', 'Sains Kesihatan', 'Sarjana Muda Sains Pemakanan'),
            'kulinari'
        )

    def test_stpm_statistik_sains_data(self):
        self.assertEqual(
            classify_stpm_course('Statistik', 'Statistik', 'Sarjana Muda Statistik'),
            'sains-data'
        )

    def test_stpm_pendidikan_fizik_stays(self):
        """Education degrees stay as pendidikan regardless of subject."""
        self.assertEqual(
            classify_stpm_course('Pendidikan', 'Pendidikan', 'Sarjana Muda Pendidikan (Fizik)'),
            'pendidikan'
        )

    def test_stpm_pertanian_food_science_kulinari(self):
        """Food science under pertanian → kulinari."""
        self.assertEqual(
            classify_stpm_course('Pertanian & Bio-Industri', 'Pertanian & Bio-Industri',
                                 'Sarjana Muda Sains Makanan'),
            'kulinari'
        )

    def test_stpm_pertanian_biotech_sains_hayat(self):
        """Pure biotech under pertanian → sains-hayat."""
        self.assertEqual(
            classify_stpm_course('Pertanian & Bio-Industri', 'Pertanian & Bio-Industri',
                                 'Sarjana Muda Bioteknologi'),
            'sains-hayat'
        )

    def test_stpm_pertanian_agro_stays(self):
        """Agricultural biotech stays as pertanian."""
        self.assertEqual(
            classify_stpm_course('Pertanian & Bio-Industri', 'Pertanian & Bio-Industri',
                                 'Sarjana Muda Bioteknologi Pertanian'),
            'pertanian'
        )

    def test_stpm_komunikasi_perhubungan_awam(self):
        """Perhubungan awam → komunikasi."""
        self.assertEqual(
            classify_stpm_course('Sains Sosial', 'Sains Sosial',
                                 'Sarjana Muda Perhubungan Awam'),
            'komunikasi'  # name override catches this
        )

    def test_spm_ua_muzik_senireka(self):
        """UA Diploma Muzik → senireka."""
        self.assertEqual(
            classify_course('Seni Reka & Kreatif', 'Seni Reka', 'Diploma Muzik'),
            'senireka'
        )

    def test_spm_ua_pendidikan_kanak(self):
        """UA Diploma Pendidikan Awal Kanak-Kanak → pendidikan."""
        self.assertEqual(
            classify_course('Perniagaan & Perdagangan', 'Perniagaan', 'Diploma Pendidikan Awal Kanak-Kanak'),
            'pendidikan'
        )

    def test_spm_ua_bahasa_etnik(self):
        """UA Diploma Bahasa Etnik → bahasa."""
        self.assertEqual(
            classify_course('Seni Reka & Kreatif', 'Seni Reka', 'Diploma Bahasa Etnik'),
            'bahasa'
        )

    def test_spm_ua_turath_islami(self):
        """UA Diploma Pengajian Turath Islami → pengajian-islam."""
        self.assertEqual(
            classify_course('Seni Reka & Kreatif', 'Seni Reka', 'Diploma Pengajian Turath Islami'),
            'pengajian-islam'
        )
```

**Step 3: Run tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_field_taxonomy.py -v`
Expected: All tests pass (118 existing + ~14 new = ~132)

---

### Task 9: Run full test suite

**Step 1: Run all backend tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: 568+ tests pass, 0 failures. Golden masters unchanged (5319 SPM, 1811 STPM).

---

### Task 10: Apply corrections to Supabase

**Step 1: Dry-run STPM classifier against live DB**

Run: `cd halatuju_api && python manage.py classify_stpm_fields`
Expected: Distribution shows all 37 fields populated, ~219 changes vs current.

**Step 2: Apply STPM corrections**

Run: `cd halatuju_api && python manage.py classify_stpm_fields --save`
Expected: `[SAVED] 1113/1113 courses classified`

**Step 3: Dry-run SPM classifier against live DB**

Run: `cd halatuju_api && python manage.py backfill_spm_field_key`
Expected: Distribution shows corrections for ~21 courses.

**Step 4: Apply SPM corrections**

Run: `cd halatuju_api && python manage.py backfill_spm_field_key --save`
Expected: `[SAVED] 390/390 courses classified`

**Step 5: Verify in Supabase**

```sql
-- Check STPM distribution
SELECT field_key_id, COUNT(*) FROM stpm_courses GROUP BY 1 ORDER BY 2 DESC;

-- Check SPM distribution
SELECT field_key_id, COUNT(*) FROM courses GROUP BY 1 ORDER BY 2 DESC;

-- Verify no empty fields (except kejuruteraan-am, kecantikan which are SPM/TVET only)
SELECT ft.key,
  COALESCE(s.cnt, 0) + COALESCE(c.cnt, 0) as total
FROM field_taxonomy ft
LEFT JOIN (SELECT field_key_id, COUNT(*) cnt FROM stpm_courses GROUP BY 1) s ON s.field_key_id = ft.key
LEFT JOIN (SELECT field_key_id, COUNT(*) cnt FROM courses GROUP BY 1) c ON c.field_key_id = ft.key
WHERE ft.parent_key IS NOT NULL
ORDER BY total;
```

---

### Task 11: Clean up temp files and commit

**Step 1: Delete audit scripts**

```bash
rm docs/propose_audit.py docs/audit_spm.py docs/stpm_field_audit.csv
```

**Step 2: Commit**

```bash
git add -A
git commit -m "fix: correct 240 field_key misclassifications in SPM+STPM classifiers

- STPM: split perubatan→kejururawatan/pergigian/farmasi, split sains-hayat→sains-fizikal/sains-data
- STPM: extract bahasa/komunikasi from umum, pertanian cleanup (food→kulinari, biotech→sains-hayat)
- STPM: veterinar→perubatan, kejuruteraan kimia override, pendidikan protection
- SPM: fix 11 UA (UiTM) courses, add course-name overrides for food/pharma/nursing/dental
- 14 new tests, 9 test expectations updated

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

**Step 3: Do NOT push** — verify distribution looks correct first, then push manually.
