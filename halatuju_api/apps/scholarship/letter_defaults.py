"""The platform's default wording for the five letters, in the two PDF languages (S6b, 2026-10-31).

An organisation that edits a letter on Organisation → Settings → Student communications gets its own
`LetterTemplate` row for that (kind, language); "Use the default" deletes it and this applies again.
English and Malay only — the PDF stack cannot shape Tamil (owner ruling, 2026-10-30).

Tokens: {name} {programme} {organisation} {clause} {date} {response_due} {note}. Blank lines are
paragraph breaks. A letter whose wording names {clause} refuses to issue without one.
"""

PLACEHOLDERS = ('name', 'programme', 'organisation', 'clause', 'date', 'response_due', 'note')

_SIGN_EN = 'Yours sincerely,\n{organisation}'
_SIGN_MS = 'Yang benar,\n{organisation}'

DEFAULTS = {
    'general': {
        'en': ('A letter about your bursary',
               'Dear {name},\n\n{note}\n\nThis letter concerns your {programme} bursary with {organisation} and '
               'was issued on {date}.\n\nPlease confirm you have received it by {response_due}.\n\n' + _SIGN_EN),
        'ms': ('Surat mengenai bursari anda',
               'Salam {name},\n\n{note}\n\nSurat ini berkaitan bursari {programme} anda bersama {organisation} '
               'dan dikeluarkan pada {date}.\n\nSila sahkan anda telah menerimanya sebelum {response_due}.\n\n'
               + _SIGN_MS),
    },
    'discipline': {
        'en': ('A formal warning about your bursary (clause {clause})',
               'Dear {name},\n\nThis is a formal warning under clause {clause} of your bursary agreement for '
               '{programme}.\n\n{note}\n\nPlease put this right, and confirm you have received this letter by '
               '{response_due}. If you need help, contact us before then.\n\n' + _SIGN_EN),
        'ms': ('Amaran rasmi mengenai bursari anda (fasal {clause})',
               'Salam {name},\n\nIni ialah amaran rasmi di bawah fasal {clause} perjanjian bursari anda untuk '
               '{programme}.\n\n{note}\n\nSila perbetulkan perkara ini dan sahkan anda telah menerima surat ini '
               'sebelum {response_due}. Jika anda memerlukan bantuan, hubungi kami sebelum tarikh itu.\n\n'
               + _SIGN_MS),
    },
    'suspension': {
        'en': ('Suspension of your bursary (clause {clause})',
               'Dear {name},\n\nUnder clause {clause} of your bursary agreement for {programme}, {organisation} '
               'suspends your bursary from {date}.\n\n{note}\n\nPlease confirm you have received this letter by '
               '{response_due}.\n\n' + _SIGN_EN),
        'ms': ('Penggantungan bursari anda (fasal {clause})',
               'Salam {name},\n\nDi bawah fasal {clause} perjanjian bursari anda untuk {programme}, '
               '{organisation} menggantung bursari anda mulai {date}.\n\n{note}\n\nSila sahkan anda telah '
               'menerima surat ini sebelum {response_due}.\n\n' + _SIGN_MS),
    },
    'termination': {
        'en': ('Termination of your bursary (clause {clause})',
               'Dear {name},\n\nUnder clause {clause} of your bursary agreement, {organisation} ends your '
               'bursary for {programme} from {date}.\n\n{note}\n\nPlease confirm you have received this letter '
               'by {response_due}.\n\n' + _SIGN_EN),
        'ms': ('Penamatan bursari anda (fasal {clause})',
               'Salam {name},\n\nDi bawah fasal {clause} perjanjian bursari anda, {organisation} menamatkan '
               'bursari anda untuk {programme} mulai {date}.\n\n{note}\n\nSila sahkan anda telah menerima surat '
               'ini sebelum {response_due}.\n\n' + _SIGN_MS),
    },
    'close_out': {
        'en': ('Your bursary file is closed',
               'Dear {name},\n\nYour {programme} bursary file with {organisation} is closed from {date}.\n\n'
               '{note}\n\nThank you for the work you have put in. Please confirm you have received this letter '
               'by {response_due}.\n\n' + _SIGN_EN),
        'ms': ('Fail bursari anda telah ditutup',
               'Salam {name},\n\nFail bursari {programme} anda bersama {organisation} ditutup mulai {date}.\n\n'
               '{note}\n\nTerima kasih atas usaha anda. Sila sahkan anda telah menerima surat ini sebelum '
               '{response_due}.\n\n' + _SIGN_MS),
    },
}

#: Month names for a date printed in a letter ("13 November 2026" / "13 November 2026").
MONTHS = {
    'en': ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
           'October', 'November', 'December'),
    'ms': ('Januari', 'Februari', 'Mac', 'April', 'Mei', 'Jun', 'Julai', 'Ogos', 'September',
           'Oktober', 'November', 'Disember'),
}
