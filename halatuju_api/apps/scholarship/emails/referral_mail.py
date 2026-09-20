"""The sponsor referral invitation.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.core.mail import EmailMessage
from .shared import _P, logger
from .student_decisions import normalise_lang


# ── F4: sponsor referral invite (sponsor → prospective sponsor) ──────────────
REFERRAL_INVITE_SUBJECTS = {
    'en': '{inviter} thinks you would make a wonderful sponsor',
    'ms': '{inviter} rasa anda boleh menjadi penaja yang hebat',
    'ta': 'நீங்கள் ஒரு சிறந்த ஆதரவாளராக இருப்பீர்கள் என {inviter} நினைக்கிறார்',
}
REFERRAL_INVITE_BODIES = {
    'en': ('Hello,\n\n{inviter} is supporting a student through HalaTuju and thought '
           'you might like to join them in changing a young life.\n\n{note}'
           'You can read how it works and sign up here:\n{link}\n\n'
           'Thank you,\nThe HalaTuju team'),
    'ms': ('Salam sejahtera,\n\n{inviter} sedang menaja seorang pelajar melalui HalaTuju '
           'dan berpendapat anda mungkin ingin menyertai mereka untuk mengubah kehidupan '
           'seorang anak muda.\n\n{note}Anda boleh membaca cara ia berfungsi dan mendaftar '
           'di sini:\n{link}\n\nTerima kasih,\nPasukan HalaTuju'),
    'ta': ('வணக்கம்,\n\n{inviter} HalaTuju மூலம் ஒரு மாணவருக்கு ஆதரவளித்து வருகிறார், '
           'ஒரு இளம் வாழ்க்கையை மாற்றுவதில் நீங்களும் இணையலாம் என நினைத்தார்.\n\n{note}'
           'இது எவ்வாறு செயல்படுகிறது என்பதைப் படித்து இங்கே பதிவு செய்யலாம்:\n{link}\n\n'
           'நன்றி,\nHalaTuju குழு'),
}
# The "they added a note" preamble, only when the inviter wrote one.
_REFERRAL_NOTE_PREFIX = {
    'en': 'They added a note for you:\n"{note}"\n\n',
    'ms': 'Mereka menulis nota untuk anda:\n"{note}"\n\n',
    'ta': 'அவர் உங்களுக்கு ஒரு குறிப்பு எழுதியுள்ளார்:\n"{note}"\n\n',
}


def send_sponsor_referral_invite(to_email, inviter_name, note, code, lang='en'):
    """Best-effort: email a prospective sponsor an invite from ``inviter_name`` with
    their optional ``note`` and the ``/sponsor?ref=<code>`` link. Swallows failures."""
    if not to_email:
        return False
    lang = normalise_lang(lang)
    inviter = inviter_name or 'A HalaTuju sponsor'
    frontend = _P.frontend_url
    link = f"{frontend}/sponsor?ref={code}"
    note_block = _REFERRAL_NOTE_PREFIX[lang].format(note=note) if (note or '').strip() else ''
    try:
        EmailMessage(
            subject=REFERRAL_INVITE_SUBJECTS[lang].format(inviter=inviter),
            body=REFERRAL_INVITE_BODIES[lang].format(inviter=inviter, note=note_block, link=link),
            from_email=_P.email_from,
            to=[to_email],
            reply_to=[_P.sponsor_reply_to],
        ).send()
        return True
    except Exception:
        logger.warning('Failed to send sponsor-referral invite to %s', to_email, exc_info=True)
        return False
