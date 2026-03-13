/**
 * Subject code → display name mapping.
 * Covers all codes used in complex_requirements and subject_group_req.
 */

const SUBJECT_NAMES: Record<string, { bm: string; en: string }> = {
  // Core subjects
  bm: { bm: 'Bahasa Melayu', en: 'Bahasa Melayu' },
  eng: { bm: 'Bahasa Inggeris', en: 'English' },
  math: { bm: 'Matematik', en: 'Mathematics' },
  addmath: { bm: 'Matematik Tambahan', en: 'Additional Mathematics' },
  hist: { bm: 'Sejarah', en: 'History' },
  sci: { bm: 'Sains', en: 'Science' },
  addsci: { bm: 'Sains Tambahan', en: 'Additional Science' },
  islam: { bm: 'Pendidikan Islam', en: 'Islamic Studies' },
  moral: { bm: 'Pendidikan Moral', en: 'Moral Education' },

  // Science stream
  phy: { bm: 'Fizik', en: 'Physics' },
  chem: { bm: 'Kimia', en: 'Chemistry' },
  bio: { bm: 'Biologi', en: 'Biology' },

  // Arts / humanities
  geo: { bm: 'Geografi', en: 'Geography' },
  ekonomi: { bm: 'Ekonomi', en: 'Economics' },
  poa: { bm: 'Prinsip Perakaunan', en: 'Principles of Accounting' },
  business: { bm: 'Perniagaan', en: 'Business Studies' },
  keusahawanan: { bm: 'Keusahawanan', en: 'Entrepreneurship' },
  psv: { bm: 'Pendidikan Seni Visual', en: 'Visual Arts' },
  music: { bm: 'Muzik', en: 'Music' },
  sports_sci: { bm: 'Sains Sukan', en: 'Sports Science' },

  // Technical / engineering
  eng_civil: { bm: 'Kejuruteraan Awam', en: 'Civil Engineering' },
  eng_mech: { bm: 'Kejuruteraan Mekanikal', en: 'Mechanical Engineering' },
  eng_elec: { bm: 'Kejuruteraan Elektrik', en: 'Electrical Engineering' },
  eng_draw: { bm: 'Lukisan Kejuruteraan', en: 'Engineering Drawing' },
  lukisan_kejuruteraan: { bm: 'Lukisan Kejuruteraan', en: 'Engineering Drawing' },
  gkt: { bm: 'Grafik Komunikasi Teknikal', en: 'Technical Graphics' },
  kelestarian: { bm: 'Sains Kelestarian', en: 'Sustainability Science' },
  reka_cipta: { bm: 'Reka Cipta', en: 'Inventions' },
  srt: { bm: 'Sains Rumah Tangga', en: 'Home Science' },
  pertanian: { bm: 'Pertanian', en: 'Agriculture' },

  // IT / computing
  comp_sci: { bm: 'Sains Komputer', en: 'Computer Science' },
  multimedia: { bm: 'Multimedia', en: 'Multimedia' },
  digital_gfx: { bm: 'Grafik Digital', en: 'Digital Graphics' },

  // Literature
  lit_bm: { bm: 'Kesusasteraan Melayu', en: 'Malay Literature' },
  lit_eng: { bm: 'Kesusasteraan Inggeris', en: 'English Literature' },
  lit_cina: { bm: 'Kesusasteraan Cina', en: 'Chinese Literature' },
  lit_tamil: { bm: 'Kesusasteraan Tamil', en: 'Tamil Literature' },
  lukisan: { bm: 'Lukisan', en: 'Drawing' },
  sejarah_seni: { bm: 'Sejarah Seni', en: 'Art History' },

  // Languages
  bahasa_arab: { bm: 'Bahasa Arab', en: 'Arabic' },
  bahasa_arab_tinggi: { bm: 'Bahasa Arab Tinggi', en: 'Advanced Arabic' },
  bahasa_cina: { bm: 'Bahasa Cina', en: 'Chinese Language' },
  bahasa_tamil: { bm: 'Bahasa Tamil', en: 'Tamil Language' },
  bahasa_iban: { bm: 'Bahasa Iban', en: 'Iban Language' },
  bahasa_kadazandusun: { bm: 'Bahasa Kadazandusun', en: 'Kadazandusun Language' },
  bahasa_semai: { bm: 'Bahasa Semai', en: 'Semai Language' },
  bahasa_perancis: { bm: 'Bahasa Perancis', en: 'French' },
  bahasa_jepun: { bm: 'Bahasa Jepun', en: 'Japanese' },
  bahasa_jerman: { bm: 'Bahasa Jerman', en: 'German' },
  b_cina: { bm: 'Bahasa Cina', en: 'Chinese' },
  b_tamil: { bm: 'Bahasa Tamil', en: 'Tamil' },

  // Islamic studies (extended)
  pqs: { bm: 'Pendidikan Al-Quran & Al-Sunnah', en: 'Quran & Sunnah Studies' },
  psi: { bm: 'Pendidikan Syariah Islamiah', en: 'Islamic Syariah' },
  tasawwur_islam: { bm: 'Tasawwur Islam', en: 'Islamic Worldview' },
  usul_aldin: { bm: 'Usul Al-Din', en: 'Islamic Theology' },
  al_syariah: { bm: 'Al-Syariah', en: 'Islamic Law' },
  manahij: { bm: 'Manahij', en: 'Islamic Methodology' },
  lughah_arabiah: { bm: 'Lughah Arabiah', en: 'Arabic Language Studies' },
  adab_balaghah: { bm: 'Adab & Balaghah', en: 'Arabic Rhetoric' },
  hifz_alquran: { bm: 'Hifz Al-Quran', en: 'Quran Memorisation' },
  maharat_alquran: { bm: 'Maharat Al-Quran', en: 'Quran Skills' },
  turath_islamiah: { bm: 'Turath Islamiah', en: 'Islamic Heritage' },
  turath_quran_sunnah: { bm: 'Turath Quran & Sunnah', en: 'Quran & Sunnah Heritage' },
  turath_bahasa_arab: { bm: 'Turath Bahasa Arab', en: 'Arabic Language Heritage' },

  // Arts & performance
  reka_bentuk_grafik: { bm: 'Reka Bentuk Grafik', en: 'Graphic Design' },
  reka_bentuk_industri: { bm: 'Reka Bentuk Industri', en: 'Industrial Design' },
  reka_bentuk_kraf: { bm: 'Reka Bentuk Kraf', en: 'Craft Design' },
  multimedia_kreatif: { bm: 'Multimedia Kreatif', en: 'Creative Multimedia' },
  produksi_reka_tanda: { bm: 'Produksi Reka Tanda', en: 'Signage Production' },
  produksi_multimedia: { bm: 'Produksi Multimedia', en: 'Multimedia Production' },
  produksi_seni: { bm: 'Produksi Seni', en: 'Arts Production' },
  seni_halus_2d: { bm: 'Seni Halus 2D', en: '2D Fine Art' },
  seni_halus_3d: { bm: 'Seni Halus 3D', en: '3D Fine Art' },
  aural_teori_muzik: { bm: 'Aural & Teori Muzik', en: 'Music Theory & Aural' },
  alat_muzik: { bm: 'Alat Muzik', en: 'Musical Instruments' },
  muzik_komputer: { bm: 'Muzik Komputer', en: 'Computer Music' },
  tarian: { bm: 'Tarian', en: 'Dance' },
  koreografi: { bm: 'Koreografi', en: 'Choreography' },
  apresiasi_tari: { bm: 'Apresiasi Tari', en: 'Dance Appreciation' },
  lakonan: { bm: 'Lakonan', en: 'Acting' },
  sinografi: { bm: 'Sinografi', en: 'Scenography' },
  penulisan_skrip: { bm: 'Penulisan Skrip', en: 'Script Writing' },

  // Vocational / MPV
  hiasan_dalaman: { bm: 'Hiasan Dalaman', en: 'Interior Design' },
  kerja_paip: { bm: 'Kerja Paip', en: 'Plumbing' },
  pembinaan_domestik: { bm: 'Pembinaan Domestik', en: 'Domestic Construction' },
  pembuatan_perabot: { bm: 'Pembuatan Perabot', en: 'Furniture Making' },
  katering: { bm: 'Katering', en: 'Catering' },
  pemprosesan_makanan: { bm: 'Pemprosesan Makanan', en: 'Food Processing' },
  rekaan_jahitan: { bm: 'Rekaan & Jahitan', en: 'Fashion & Sewing' },
  penjagaan_muka: { bm: 'Penjagaan Muka & Badan', en: 'Beauty & Wellness' },
  asuhan_kanak: { bm: 'Asuhan Kanak-Kanak', en: 'Childcare' },
  gerontologi: { bm: 'Gerontologi', en: 'Gerontology' },
  pendawaian_domestik: { bm: 'Pendawaian Domestik', en: 'Domestic Wiring' },
  menservis_automobil: { bm: 'Menservis Automobil', en: 'Auto Service' },
  kimpalan: { bm: 'Kimpalan', en: 'Welding' },
  menservis_motosikal: { bm: 'Menservis Motosikal', en: 'Motorcycle Service' },
  penyejukan: { bm: 'Penyejukan & Penyamanan Udara', en: 'Refrigeration & AC' },
  landskap_nurseri: { bm: 'Landskap & Nurseri', en: 'Landscaping & Nursery' },
  tanaman_makanan: { bm: 'Tanaman Makanan', en: 'Food Crops' },
  akuakultur: { bm: 'Akuakultur', en: 'Aquaculture' },
  menservis_elektrik: { bm: 'Menservis Peralatan Elektrik', en: 'Electrical Servicing' },
  voc_food: { bm: 'Vokasional Makanan', en: 'Vocational Food' },
  voc_landscape: { bm: 'Vokasional Landskap', en: 'Vocational Landscaping' },
}

export function getSubjectName(code: string, locale: string): string {
  const entry = SUBJECT_NAMES[code]
  if (!entry) {
    // Fallback: humanise the code
    return code.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  }
  return locale === 'en' ? entry.en : entry.bm
}

// ---------------------------------------------------------------------------
// STPM subject definitions (keys match backend stpm_engine.py)
// ---------------------------------------------------------------------------

export interface StpmSubject {
  id: string
  name: string
  stream: 'science' | 'arts' | 'both' | 'compulsory'
}

export const STPM_SUBJECTS: StpmSubject[] = [
  { id: 'PA', name: 'Pengajian Am', stream: 'compulsory' },
  { id: 'MATH_T', name: 'Matematik T', stream: 'science' },
  { id: 'PHYSICS', name: 'Fizik', stream: 'science' },
  { id: 'CHEMISTRY', name: 'Kimia', stream: 'science' },
  { id: 'BIOLOGY', name: 'Biologi', stream: 'science' },
  { id: 'FURTHER_MATH', name: 'Matematik Lanjutan T', stream: 'science' },
  { id: 'ECONOMICS', name: 'Ekonomi', stream: 'arts' },
  { id: 'ACCOUNTING', name: 'Perakaunan', stream: 'arts' },
  { id: 'BUSINESS', name: 'Pengajian Perniagaan', stream: 'arts' },
  { id: 'GEOGRAFI', name: 'Geografi', stream: 'arts' },
  { id: 'SEJARAH', name: 'Sejarah', stream: 'arts' },
  { id: 'KESUSASTERAAN_MELAYU', name: 'Kesusasteraan Melayu', stream: 'arts' },
  { id: 'BAHASA_MELAYU', name: 'Bahasa Melayu', stream: 'arts' },
  { id: 'BAHASA_CINA', name: 'Bahasa Cina', stream: 'arts' },
  { id: 'BAHASA_TAMIL', name: 'Bahasa Tamil', stream: 'arts' },
  { id: 'SENI_VISUAL', name: 'Seni Visual', stream: 'arts' },
  { id: 'SYARIAH', name: 'Syariah Islamiah', stream: 'arts' },
  { id: 'USULUDDIN', name: 'Usuluddin', stream: 'arts' },
  { id: 'ICT', name: 'Sains Komputer / ICT', stream: 'both' },
  { id: 'MATH_M', name: 'Matematik M', stream: 'arts' },
]

export const STPM_GRADES = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'F']

export const MUET_BANDS = [1, 2, 3, 4, 5, 6]

// SPM prerequisite subjects for STPM students
// 4 compulsory (all streams), 2 optional (stream-specific)
export const SPM_PREREQ_COMPULSORY = [
  { id: 'bm', name: 'Bahasa Melayu' },
  { id: 'eng', name: 'Bahasa Inggeris' },
  { id: 'hist', name: 'Sejarah' },
  { id: 'math', name: 'Matematik' },
]

export const SPM_PREREQ_OPTIONAL = [
  { id: 'addmath', name: 'Matematik Tambahan' },
  { id: 'sci', name: 'Sains' },
]

// Combined for backward compatibility
export const SPM_PREREQ_SUBJECTS = [...SPM_PREREQ_COMPULSORY, ...SPM_PREREQ_OPTIONAL]

export const SPM_GRADE_OPTIONS = ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G']
