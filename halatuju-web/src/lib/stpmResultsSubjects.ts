/**
 * THE STPM SUBJECT LIST (keys match backend `stpm_engine.py`) — the STPM results step
 * (`app/onboarding/stpm-grades`) and the STPM quiz read it. Its own module since 2026-10-28 (STPM
 * CGPA C1/C2): in `lib/subjects.ts` its three-language labels rode on every route importing an SPM
 * list and put `/scholarship/application` over its first-load budget.
 */
export interface StpmSubject {
  id: string
  /** The name MPM prints on the certificate (Malay) — also the Malay label. */
  name: string
  /** English label. */
  en: string
  /** Tamil label — first drafts (STPM CGPA sprint C1, 2026-10-28) for the owner to read. */
  ta: string
  stream: 'science' | 'arts' | 'both' | 'compulsory'
}

/**
 * Every subject on the MPM STPM syllabus (STPM CGPA sprint C1, 2026-10-28), plus Matematik
 * Lanjutan T, which only older certificates carry. Keys never change once stored. The server's
 * list is `halatuju_api/apps/courses/stpm_subjects.py`, kept in step by
 * drift-test: src/lib/__tests__/stpmSubjectsDrift.test.ts
 */
export const STPM_SUBJECTS: StpmSubject[] = [
  { id: 'PA', name: 'Pengajian Am', en: 'General Studies', ta: 'பொதுக் கல்வி', stream: 'compulsory' },
  { id: 'MATH_T', name: 'Matematik (T)', en: 'Mathematics (T)', ta: 'கணிதம் (T)', stream: 'science' },
  { id: 'PHYSICS', name: 'Fizik', en: 'Physics', ta: 'இயற்பியல்', stream: 'science' },
  { id: 'CHEMISTRY', name: 'Kimia', en: 'Chemistry', ta: 'வேதியியல்', stream: 'science' },
  { id: 'BIOLOGY', name: 'Biologi', en: 'Biology', ta: 'உயிரியல்', stream: 'science' },
  { id: 'FURTHER_MATH', name: 'Matematik Lanjutan (T)', en: 'Further Mathematics (T)', ta: 'மேம்பட்ட கணிதம் (T)', stream: 'science' },
  { id: 'SAINS_SUKAN', name: 'Sains Sukan', en: 'Sports Science', ta: 'விளையாட்டு அறிவியல்', stream: 'both' },
  { id: 'ECONOMICS', name: 'Ekonomi', en: 'Economics', ta: 'பொருளாதாரம்', stream: 'arts' },
  { id: 'ACCOUNTING', name: 'Perakaunan', en: 'Accounting', ta: 'கணக்கியல்', stream: 'arts' },
  { id: 'BUSINESS', name: 'Pengajian Perniagaan', en: 'Business Studies', ta: 'வணிகவியல்', stream: 'arts' },
  { id: 'GEOGRAFI', name: 'Geografi', en: 'Geography', ta: 'புவியியல்', stream: 'arts' },
  { id: 'SEJARAH', name: 'Sejarah', en: 'History', ta: 'வரலாறு', stream: 'arts' },
  { id: 'KESUSASTERAAN_MELAYU', name: 'Kesusasteraan Melayu Komunikatif', en: 'Communicative Malay Literature', ta: 'தொடர்பு மலாய் இலக்கியம்', stream: 'arts' },
  { id: 'LITERATURE_IN_ENGLISH', name: 'Literature in English', en: 'Literature in English', ta: 'ஆங்கில இலக்கியம்', stream: 'arts' },
  { id: 'BAHASA_MELAYU', name: 'Bahasa Melayu', en: 'Malay Language', ta: 'மலாய் மொழி', stream: 'arts' },
  { id: 'BAHASA_CINA', name: 'Bahasa Cina', en: 'Chinese Language', ta: 'சீன மொழி', stream: 'arts' },
  { id: 'BAHASA_TAMIL', name: 'Bahasa Tamil', en: 'Tamil Language', ta: 'தமிழ் மொழி', stream: 'arts' },
  { id: 'BAHASA_ARAB', name: 'Bahasa Arab', en: 'Arabic Language', ta: 'அரபு மொழி', stream: 'arts' },
  { id: 'SENI_VISUAL', name: 'Seni Visual', en: 'Visual Arts', ta: 'காட்சிக் கலை', stream: 'arts' },
  { id: 'SYARIAH', name: 'Syariah', en: 'Syariah', ta: 'ஷரீஆ', stream: 'arts' },
  { id: 'USULUDDIN', name: 'Usuluddin', en: 'Usuluddin', ta: 'உசுலுதீன்', stream: 'arts' },
  { id: 'TAHFIZ_AL_QURAN', name: 'Tahfiz Al-Quran', en: 'Tahfiz Al-Quran', ta: 'தஹ்ஃபிஸ் அல்-குர்ஆன்', stream: 'arts' },
  { id: 'ICT', name: 'Teknologi Maklumat dan Komunikasi', en: 'Information and Communications Technology', ta: 'தகவல் தொடர்பு தொழில்நுட்பம்', stream: 'arts' },
  { id: 'MATH_M', name: 'Matematik (M)', en: 'Mathematics (M)', ta: 'கணிதம் (M)', stream: 'arts' },
]

/** A subject's label in the reader's language (Malay is the certificate's own name). */
export function stpmSubjectLabel(s: StpmSubject, locale: string): string {
  return locale === 'en' ? s.en : locale === 'ta' ? s.ta : s.name
}

export const STPM_GRADES = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'F']

/** Map frontend subject IDs (localStorage) to backend API keys (stpm_quiz_engine). */
export const STPM_SUBJECT_TO_API_KEY: Record<string, string> = {
  MATH_T: 'mathematics_t',
  MATH_M: 'mathematics_m',
  PHYSICS: 'physics',
  CHEMISTRY: 'chemistry',
  BIOLOGY: 'biology',
  FURTHER_MATH: 'further_mathematics',
  ECONOMICS: 'economics',
  ACCOUNTING: 'accounting',
  BUSINESS: 'business_studies',
  GEOGRAFI: 'geography',
  SEJARAH: 'history',
  KESUSASTERAAN_MELAYU: 'kesusasteraan_melayu',
  BAHASA_MELAYU: 'bahasa_melayu',
  BAHASA_CINA: 'bahasa_cina',
  BAHASA_TAMIL: 'bahasa_tamil',
  SENI_VISUAL: 'visual_arts',
  SYARIAH: 'syariah',
  USULUDDIN: 'usuluddin',
  ICT: 'ict',
  PA: 'pengajian_am',
  // STPM CGPA sprint C1: the rest of the MPM list. `literature_english` is the quiz's existing key;
  // the other three have no quiz weighting yet and are ignored by the quiz engine (`.get`).
  LITERATURE_IN_ENGLISH: 'literature_english',
  BAHASA_ARAB: 'bahasa_arab',
  TAHFIZ_AL_QURAN: 'tahfiz_al_quran',
  SAINS_SUKAN: 'sports_science',
}
