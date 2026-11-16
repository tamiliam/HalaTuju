"""The "new note" email between an org admin and a reviewer (request #73, 2026-11-16).

Sent after the commit, by `staff_notifications.alert_by_email`, to the OTHER side of the conversation only:
the assigned reviewer when the org admin side wrote, the org admin side when the reviewer wrote.

⚠ NEVER THE NOTE'S TEXT. A note may name a family's circumstances; the email says only that there is a new
note and links to the student's page, where the reader must sign in to see it.

⚠ ALL THREE LANGUAGES, STACKED. A staff account has no language on the server (the web keeps it in the
browser), so the body is English, then Malay, then Tamil — every reader finds theirs. Same envelope as the
other reviewer mail (`_send_plain`: the interview@ sender with its working reply-to).
"""
from .reviewer_mail import _reviewer_subject
from .sending import _send_plain
from .shared import _P

#: Which side wrote → what the reader is told, per language.
_INTRO = {
    'reviewer': {
        'en': 'The reviewer added a new note about a student in your programme.',
        'ms': 'Penyemak telah menambah nota baharu tentang seorang pelajar dalam program anda.',
        'ta': 'மதிப்பாய்வாளர் உங்கள் திட்டத்தில் உள்ள ஒரு மாணவர் பற்றி புதிய குறிப்பைச் சேர்த்துள்ளார்.',
    },
    'org_admin': {
        'en': 'Your org admin added a new note about a student you are reviewing.',
        'ms': 'Pentadbir organisasi anda telah menambah nota baharu tentang pelajar yang anda semak.',
        'ta': 'உங்கள் நிறுவன நிர்வாகி நீங்கள் மதிப்பாய்வு செய்யும் ஒரு மாணவர் பற்றி புதிய குறிப்பைச் சேர்த்துள்ளார்.',
    },
}
_OPEN = {
    'en': "Open the student's page to read it and reply:",
    'ms': 'Buka halaman pelajar untuk membacanya dan membalas:',
    'ta': 'அதைப் படிக்கவும் பதிலளிக்கவும் மாணவரின் பக்கத்தைத் திறக்கவும்:',
}
_PRIVACY = {
    'en': 'For privacy, the note itself is not in this email.',
    'ms': 'Demi privasi, nota itu tidak disertakan dalam e-mel ini.',
    'ta': 'தனியுரிமைக்காக, அந்தக் குறிப்பு இந்த மின்னஞ்சலில் இல்லை.',
}
_THANKS = {'en': 'Thanks,', 'ms': 'Terima kasih,', 'ta': 'நன்றி,'}
_SUBJECT = 'New note / Nota baharu / புதிய குறிப்பு'
_LANGS = ('en', 'ms', 'ta')


def build_staff_note_email(*, from_side, ref='', application_id):
    """The wording → ``(subject, body)``. ``from_side``: 'reviewer' or 'org_admin' (who WROTE the note)."""
    intro = _INTRO['reviewer' if from_side == 'reviewer' else 'org_admin']
    link = f'{_P.frontend_url}/admin/scholarship/{application_id}'
    blocks = [
        f'{intro[lang]}\n\n{_OPEN[lang]}\n{link}\n\n{_PRIVACY[lang]}\n\n{_THANKS[lang]}\n{_P.team_signoff(lang)}'
        for lang in _LANGS
    ]
    return _reviewer_subject(_SUBJECT, ref), '\n\n————————\n\n'.join(blocks)


def send_staff_note_email(to_email, *, from_side, ref='', application_id):
    """Tell one person on the other side that there is a new note on a case. Never the text."""
    subject, body = build_staff_note_email(from_side=from_side, ref=ref, application_id=application_id)
    return _send_plain(to_email, subject, body)
