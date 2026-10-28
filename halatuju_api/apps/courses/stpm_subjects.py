"""THE STPM SUBJECT KEYS — every subject a student may enter on the STPM results form.

STPM CGPA sprint C1 (2026-10-28). The web's `STPM_SUBJECTS` (`halatuju-web/src/lib/subjects.ts`)
offers exactly these keys in exactly this order; `src/lib/__tests__/stpmSubjectsDrift.test.ts`
reads this file and fails on any difference, so the two lists cannot drift apart.

The list is every subject on the Majlis Peperiksaan Malaysia (MPM) STPM syllabus page, plus
`FURTHER_MATH` (Matematik Lanjutan T), which the current syllabus no longer offers but older
certificates carry — kept so a stored grade under it still reads. Keys never change once stored:
`stpm_grades` rows, the course requirement fixtures (`fixtures/stpm_requirements.json`, whose
`stpm_subject_group` lists already use `BAHASA_ARAB`, `LITERATURE_IN_ENGLISH`, `SAINS_SUKAN` and
`TAHFIZ_AL_QURAN`) and the report labels all key on them.

A leaf: no imports, so anything may read it.
"""

#: Pengajian Am — every candidate's compulsory subject, and half of the PNGK rule.
PENGAJIAN_AM = 'PA'

#: Every key the STPM results form offers, in the form's order (Pengajian Am first).
STPM_SUBJECT_KEYS = (
    'PA',
    'MATH_T',
    'PHYSICS',
    'CHEMISTRY',
    'BIOLOGY',
    'FURTHER_MATH',
    'SAINS_SUKAN',
    'ECONOMICS',
    'ACCOUNTING',
    'BUSINESS',
    'GEOGRAFI',
    'SEJARAH',
    'KESUSASTERAAN_MELAYU',
    'LITERATURE_IN_ENGLISH',
    'BAHASA_MELAYU',
    'BAHASA_CINA',
    'BAHASA_TAMIL',
    'BAHASA_ARAB',
    'SENI_VISUAL',
    'SYARIAH',
    'USULUDDIN',
    'TAHFIZ_AL_QURAN',
    'ICT',
    'MATH_M',
)
