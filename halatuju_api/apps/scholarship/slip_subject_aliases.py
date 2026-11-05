"""Other printed names of an SPM subject → today's grade-form name.

``OLD_NAMES`` feed the slip READERS (``academic_engine._CANONICAL``); ``ENGLISH_NAMES`` feed the
COMPARISON only (``academic_compare._compare_key``) and must never reach a reader (lead, 2026-11-06).

A LEAF: no imports. It moved out of ``academic_engine.py`` (request #62, 2026-11-06), which is on
the oversize ledger with no room, so the English names below could be added without growing it.

⚠ AN ALIAS IS ONLY EVER THE SAME SUBJECT UNDER ANOTHER NAME. Two names are folded ONLY when
UPU Online's own SPM subject list shows them as one subject (one is an older or translated form of
the other). UPU lists these as SEPARATE subjects, so they must NEVER be folded here (lead's check of
online.mohe.gov.my/epanduan, 2026-11-06; owner ruling the same day for the first pair):
Lukisan / Pendidikan Seni Visual / Lukisan Kejuruteraan; Reka Bentuk Grafik / Reka Bentuk Grafik
Digital / Grafik Komunikasi Teknikal; Reka Bentuk Kraf / Reka Cipta. ``test_slip_extra_subjects``
pins them as distinct.
"""

#: The names Sprint C replaced (Bumi coverage, 2026-10-29) → today's name. Reads stored before
#: MODEL_VERSION 1.18.0 hold the old ones ("Manahij"), and are never re-read, so they stay readable.
OLD_NAMES = {
    'Manahij': "Manahij Al-'Ulum Al-Islamiah", 'Lughah Arabiah': "Al-Lughah Al-'Arabiah Al-Mu'asirah",
    'Adab & Balaghah': 'Al-Adab Wa Al-Balaghah', 'Turath Islamiah': 'Turath Dirasat Islamiah',
    'Turath Quran & Sunnah': 'Turath Al-Quran dan Al-Sunnah',
    'Pendidikan Al-Quran & Al-Sunnah': 'Pendidikan Al-Quran dan Al-Sunnah',
}

#: Request #62 (owner 2026-11-06): some slips print the science and mathematics subjects in
#: English. Without these an English row never matched the student's Malay subject, so it read as
#: "missing" AND the typed subject as "not on the slip".
ENGLISH_NAMES = {
    'Mathematics': 'Matematik', 'Additional Mathematics': 'Matematik Tambahan',
    'Science': 'Sains', 'Physics': 'Fizik', 'Chemistry': 'Kimia', 'Biology': 'Biologi',
}
