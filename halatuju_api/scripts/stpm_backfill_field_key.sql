-- Field Taxonomy Sprint 2: STPM field_key backfill
-- Classifies 1,113 STPM courses into 37 taxonomy keys
-- Generated from classify_stpm_fields.py deterministic classifier

BEGIN;

-- === Simple categories (field_key depends only on category) ===

UPDATE stpm_courses SET field_key_id = 'pendidikan' WHERE category = 'Pendidikan';
UPDATE stpm_courses SET field_key_id = 'elektrik' WHERE category = 'Elektrik & Elektronik';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Sains Sosial';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Bahasa & Linguistik';
UPDATE stpm_courses SET field_key_id = 'kimia-proses' WHERE category = 'Kejuruteraan Kimia';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Matematik';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Lain-lain';
UPDATE stpm_courses SET field_key_id = 'kimia-proses' WHERE category = 'Kimia';
UPDATE stpm_courses SET field_key_id = 'pengajian-islam' WHERE category = 'Pengajian Islam';
UPDATE stpm_courses SET field_key_id = 'alam-sekitar' WHERE category = 'Sains Alam Sekitar';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Fizik';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Sains Kemasyarakatan';
UPDATE stpm_courses SET field_key_id = 'multimedia' WHERE category = 'Komunikasi & Media';
UPDATE stpm_courses SET field_key_id = 'undang-undang' WHERE category = 'Undang-Undang';
UPDATE stpm_courses SET field_key_id = 'perniagaan' WHERE category = 'Ekonomi';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Bahasa & Komunikasi';
UPDATE stpm_courses SET field_key_id = 'pengajian-islam' WHERE category = 'Pengajian Agama';
UPDATE stpm_courses SET field_key_id = 'perakaunan' WHERE category = 'Kewangan';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Sains Sukan';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Kemanusiaan';
UPDATE stpm_courses SET field_key_id = 'perakaunan' WHERE category = 'Perakaunan';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Perubatan';
UPDATE stpm_courses SET field_key_id = 'multimedia' WHERE category = 'Komunikasi';
UPDATE stpm_courses SET field_key_id = 'farmasi' WHERE category = 'Farmasi';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Sains Bioperubatan';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Kejururawatan';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Bahasa, Linguistik & Geografi';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Sains Fizikal';
UPDATE stpm_courses SET field_key_id = 'multimedia' WHERE category = 'Linguistik & Media';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Sains Bahan';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Psikologi';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Sains Perubatan';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Sains Politik & Kajian Keselamatan';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Dietetik';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Statistik';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Pergigian';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Pengimejan Perubatan';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Kesusasteraan';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Sains Politik';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Geologi';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Nutrisi & Dietetik';
UPDATE stpm_courses SET field_key_id = 'pengurusan' WHERE category = 'Hartanah & Pengurusan Tanah';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Sejarah';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Sains Aktuari';
UPDATE stpm_courses SET field_key_id = 'kimia-proses' WHERE category = 'Sains Kimia';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Pengurusan Sukan';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Linguistik';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Sains Biologi';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Penjagaan Kesihatan';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Matematik & Statistik';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Bahasa & Kesusasteraan Islam';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Optometri';
UPDATE stpm_courses SET field_key_id = 'mekanikal' WHERE category = 'Kejuruteraan Bahan';
UPDATE stpm_courses SET field_key_id = 'marin' WHERE category = 'Teknologi Maritim';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Keselamatan & Kesihatan Pekerjaan';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Kejuruteraan Bioperubatan';
UPDATE stpm_courses SET field_key_id = 'pengurusan' WHERE category = 'Pengurusan Sumber Manusia';
UPDATE stpm_courses SET field_key_id = 'kulinari' WHERE category = 'Sains Makanan';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Geografi';
UPDATE stpm_courses SET field_key_id = 'marin' WHERE category = 'Pengurusan Maritim';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Kaunseling';
UPDATE stpm_courses SET field_key_id = 'alam-sekitar' WHERE category = 'Sains Alam Sekitar & Kesihatan Pekerjaan';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Sosiologi & Antropologi';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Sukan & Rekreasi';
UPDATE stpm_courses SET field_key_id = 'alam-sekitar' WHERE category = 'Teknologi Alam Sekitar';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Sains Kesihatan';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Teknologi Penjagaan Kesihatan';
UPDATE stpm_courses SET field_key_id = 'pertanian' WHERE category = 'Perikanan';
UPDATE stpm_courses SET field_key_id = 'minyak-gas' WHERE category = 'Minyak & Gas';
UPDATE stpm_courses SET field_key_id = 'senibina' WHERE category = 'Landskap';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Sains Pemakanan';
UPDATE stpm_courses SET field_key_id = 'alam-sekitar' WHERE category = 'Teknologi Persekitaran';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Mikrobiologi Gunaan';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Pengajian Asia Timur';
UPDATE stpm_courses SET field_key_id = 'pertanian' WHERE category = 'Lain-lain (Pengurusan Taman dan Ameniti)';
UPDATE stpm_courses SET field_key_id = 'pertanian' WHERE category = 'Akuakultur';
UPDATE stpm_courses SET field_key_id = 'senireka' WHERE category = 'Tekstil & Fesyen';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Bahasa & Keusahawanan';
UPDATE stpm_courses SET field_key_id = 'perniagaan' WHERE category = 'Keusahawanan Sosial & Pengurusan Komuniti';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Kerja Sosial';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Sains Gunaan';
UPDATE stpm_courses SET field_key_id = 'kulinari' WHERE category = 'Teknologi Makanan';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Kriminologi';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Fizik & Instrumentasi';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Kajian Pembangunan';
UPDATE stpm_courses SET field_key_id = 'kimia-proses' WHERE category = 'Kimia Analisis & Persekitaran';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Lain-lain (Kejururawatan)';
UPDATE stpm_courses SET field_key_id = 'kimia-proses' WHERE category = 'Lain-lain (Kimia Gunaan)';
UPDATE stpm_courses SET field_key_id = 'mekanikal' WHERE category = 'Teknologi Higiene Industri & Keselamatan';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'GeoSains';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Fizik Perubatan';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Perubatan & Farmasi';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Sains Bahan & Teknologi';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Nanofizik';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Biokimia';
UPDATE stpm_courses SET field_key_id = 'elektrik' WHERE category = 'Teknologi Tenaga';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Persuratan & Kebudayaan Melayu';
UPDATE stpm_courses SET field_key_id = 'mekanikal' WHERE category = 'Kejuruteraan Pembuatan';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Patologi Pertuturan';
UPDATE stpm_courses SET field_key_id = 'marin' WHERE category = 'Sains Marin';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Lain-lain (Perubatan)';
UPDATE stpm_courses SET field_key_id = 'multimedia' WHERE category = 'Pengajian Media';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Kesihatan & Kejururawatan';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Sains Biomolekul';
UPDATE stpm_courses SET field_key_id = 'perniagaan' WHERE category = 'Perniagaan & Pengurusan Industri Halal';
UPDATE stpm_courses SET field_key_id = 'pertanian' WHERE category = 'Pengurusan Biodiversiti';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Hubungan Industri';
UPDATE stpm_courses SET field_key_id = 'multimedia' WHERE category = 'Seni Persembahan';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Pengajian Melayu';
UPDATE stpm_courses SET field_key_id = 'marin' WHERE category = 'Biologi Marin';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Sejarah & Tamadun';
UPDATE stpm_courses SET field_key_id = 'kimia-proses' WHERE category = 'Kimia Forensik';
UPDATE stpm_courses SET field_key_id = 'mekanikal' WHERE category = 'Teknologi Mineral';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Lain-lain (Dietetik)';
UPDATE stpm_courses SET field_key_id = 'mekanikal' WHERE category = 'Kejuruteraan Perlombongan & Sumber Mineral';
UPDATE stpm_courses SET field_key_id = 'perniagaan' WHERE category = 'Pengurusan Industri Halal';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Pengajian Bahasa Melayu';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Bahasa & Linguistik Inggeris';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Matematik Pemodelan dan Analitik';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Lain-lain (Pemulihan Cara Kerja)';
UPDATE stpm_courses SET field_key_id = 'kimia-proses' WHERE category = 'Kejuruteraan Pemprosesan Makanan';
UPDATE stpm_courses SET field_key_id = 'pertanian' WHERE category = 'Pemuliharaan & Pengurusan Biodiversiti';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Lain-lain (Fizik)';
UPDATE stpm_courses SET field_key_id = 'kimia-proses' WHERE category = 'Kejuruteraan Nuklear';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Sains Forensik';
UPDATE stpm_courses SET field_key_id = 'elektrik' WHERE category = 'Teknologi Tenaga Boleh Diperbaharui';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Kesihatan & Keselamatan Persekitaran';
UPDATE stpm_courses SET field_key_id = 'pertanian' WHERE category = 'Veterinar';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Pengajian Pengguna';
UPDATE stpm_courses SET field_key_id = 'pengurusan' WHERE category = 'Sumber Manusia';
UPDATE stpm_courses SET field_key_id = 'mekanikal' WHERE category = 'Lain-lain (Kejuruteraan Polimer)';
UPDATE stpm_courses SET field_key_id = 'kimia-proses' WHERE category = 'Kimia & Proses';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Perubatan & Pembedahan';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Kesihatan dan Kecergasan';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Pengajian Cina';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Antropologi & Sosiologi';
UPDATE stpm_courses SET field_key_id = 'perakaunan' WHERE category = 'Matematik Kewangan';
UPDATE stpm_courses SET field_key_id = 'sivil' WHERE category = 'Ukur Bahan';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Keselamatan dan Kesihatan Pekerjaan';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Lain-lain (Pengimejan Perubatan)';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Bahasa & Kesusasteraan Inggeris';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Pengajian Warisan';
UPDATE stpm_courses SET field_key_id = 'kimia-proses' WHERE category = 'Teknologi Kejuruteraan Bio-proses';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Biologi';
UPDATE stpm_courses SET field_key_id = 'pengurusan' WHERE category = 'Harta Tanah';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Sains Bumi';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Audiologi';
UPDATE stpm_courses SET field_key_id = 'mekanikal' WHERE category = 'Pembuatan';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Matematik Pengurusan';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Bio-Teknologi';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Bahasa & Linguistik Cina';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Biologi Molekul & Sel';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Matematik & Ekonomi';
UPDATE stpm_courses SET field_key_id = 'it-rangkaian' WHERE category = 'Analitik Data';
UPDATE stpm_courses SET field_key_id = 'pengajian-islam' WHERE category = 'Undang-Undang Islam';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Sains Kognitif';
UPDATE stpm_courses SET field_key_id = 'alam-sekitar' WHERE category = 'Kejuruteraan Alam Sekitar';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Geosains';
UPDATE stpm_courses SET field_key_id = 'perniagaan' WHERE category = 'Keusahawanan Kesejahteraan';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Pengajian Asia Tenggara';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Pengajian Bahasa Inggeris';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Bahasa & Linguistik Arab';
UPDATE stpm_courses SET field_key_id = 'alam-sekitar' WHERE category = 'Pengajian Alam Sekitar';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Kesusasteraan Melayu';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Pengajian India';
UPDATE stpm_courses SET field_key_id = 'sains-hayat' WHERE category = 'Mikrobiologi';
UPDATE stpm_courses SET field_key_id = 'sivil' WHERE category = 'Sains Ukur Bahan';
UPDATE stpm_courses SET field_key_id = 'mekanikal' WHERE category = 'Kejuruteraan Bahan & Polimer';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Lain-lain (Teknologi Makmal Perubatan)';
UPDATE stpm_courses SET field_key_id = 'kulinari' WHERE category = 'Sains Makanan & Teknologi';
UPDATE stpm_courses SET field_key_id = 'umum' WHERE category = 'Bahasa & Kesusasteraan';
UPDATE stpm_courses SET field_key_id = 'pengajian-islam' WHERE category = 'Pengurusan Muamalat';
UPDATE stpm_courses SET field_key_id = 'sains-sosial' WHERE category = 'Pengajian Antarabangsa & Strategik';
UPDATE stpm_courses SET field_key_id = 'alam-sekitar' WHERE category = 'Pengurusan Alam Sekitar';
UPDATE stpm_courses SET field_key_id = 'it-rangkaian' WHERE category = 'Sains Data';
UPDATE stpm_courses SET field_key_id = 'it-rangkaian' WHERE category = 'Statistik Analitik Data';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Lain-lain (Fisioterapi)';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Lain-lain (Pergigian)';
UPDATE stpm_courses SET field_key_id = 'multimedia' WHERE category = 'Media & Komunikasi';
UPDATE stpm_courses SET field_key_id = 'perubatan' WHERE category = 'Fisioterapi';

-- === SPM-matching categories (course_name sub-classification) ===

-- Mekanikal & Automotif (54)
UPDATE stpm_courses SET field_key_id = CASE
    WHEN LOWER(course_name) LIKE '%automotif%' OR LOWER(course_name) LIKE '%kenderaan%' THEN 'automotif'
    WHEN LOWER(course_name) LIKE '%mekatronik%' THEN 'mekatronik'
    ELSE 'mekanikal'
END WHERE category = 'Mekanikal & Automotif';

-- Komputer, IT & Multimedia (99)
UPDATE stpm_courses SET field_key_id = CASE
    WHEN LOWER(course_name) LIKE '%rangkaian%' OR LOWER(course_name) LIKE '%networking%'
         OR LOWER(course_name) LIKE '%keselamatan komputer%' OR LOWER(course_name) LIKE '%security%'
         OR LOWER(course_name) LIKE '%pangkalan data%' OR LOWER(course_name) LIKE '%data%' THEN 'it-rangkaian'
    WHEN LOWER(course_name) LIKE '%multimedia%' OR LOWER(course_name) LIKE '%animasi%'
         OR LOWER(course_name) LIKE '%permainan digital%' OR LOWER(course_name) LIKE '%media interaktif%'
         OR LOWER(course_name) LIKE '%games%' THEN 'multimedia'
    ELSE 'it-perisian'
END WHERE category = 'Komputer, IT & Multimedia';

-- Perniagaan & Perdagangan (112)
UPDATE stpm_courses SET field_key_id = CASE
    WHEN LOWER(course_name) LIKE '%perakaunan%' OR LOWER(course_name) LIKE '%kewangan%'
         OR LOWER(course_name) LIKE '%insurans%' OR LOWER(course_name) LIKE '%aktuari%' THEN 'perakaunan'
    WHEN LOWER(course_name) LIKE '%pengurusan%' OR LOWER(course_name) LIKE '%logistik%' THEN 'pengurusan'
    ELSE 'perniagaan'
END WHERE category = 'Perniagaan & Perdagangan';

-- Pertanian & Bio-Industri (94)
UPDATE stpm_courses SET field_key_id = CASE
    WHEN LOWER(course_name) LIKE '%alam sekitar%' THEN 'alam-sekitar'
    ELSE 'pertanian'
END WHERE category = 'Pertanian & Bio-Industri';

-- Sivil, Seni Bina & Pembinaan (63)
UPDATE stpm_courses SET field_key_id = CASE
    WHEN LOWER(course_name) LIKE '%seni bina%' OR LOWER(course_name) LIKE '%senibina%'
         OR LOWER(course_name) LIKE '%landskap%' OR LOWER(course_name) LIKE '%perancangan%'
         OR LOWER(course_name) LIKE '%rekabentuk dalaman%' THEN 'senibina'
    ELSE 'sivil'
END WHERE category = 'Sivil, Seni Bina & Pembinaan';

-- Seni Reka & Kreatif (65)
UPDATE stpm_courses SET field_key_id = CASE
    WHEN LOWER(course_name) LIKE '%animasi%' OR LOWER(course_name) LIKE '%multimedia%'
         OR LOWER(course_name) LIKE '%permainan%' OR LOWER(course_name) LIKE '%games%' THEN 'multimedia'
    ELSE 'senireka'
END WHERE category = 'Seni Reka & Kreatif';

-- Aero, Marin, Minyak & Gas (21)
UPDATE stpm_courses SET field_key_id = CASE
    WHEN LOWER(course_name) LIKE '%minyak%' OR LOWER(course_name) LIKE '%petro%' THEN 'minyak-gas'
    WHEN LOWER(course_name) LIKE '%marin%' OR LOWER(course_name) LIKE '%kapal%'
         OR LOWER(course_name) LIKE '%perkapalan%' OR LOWER(course_name) LIKE '%maritim%' THEN 'marin'
    ELSE 'aero'
END WHERE category = 'Aero, Marin, Minyak & Gas';

-- Hospitaliti, Kulinari & Pelancongan (20)
UPDATE stpm_courses SET field_key_id = CASE
    WHEN LOWER(course_name) LIKE '%kulinari%' OR LOWER(course_name) LIKE '%culinary%'
         OR LOWER(course_name) LIKE '%makanan%' OR LOWER(course_name) LIKE '%pastri%'
         OR LOWER(course_name) LIKE '%food%' THEN 'kulinari'
    WHEN LOWER(course_name) LIKE '%kecantikan%' OR LOWER(course_name) LIKE '%spa%'
         OR LOWER(course_name) LIKE '%dandanan%' THEN 'kecantikan'
    ELSE 'hospitaliti'
END WHERE category = 'Hospitaliti, Kulinari & Pelancongan';

COMMIT;
