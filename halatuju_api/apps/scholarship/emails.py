"""
Trilingual acknowledgement email for B40 Assistance Programme applications.

Phase 1 uses email (every HalaTuju account has a verified Google address).
WhatsApp is a Phase 2 enhancement.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

ACK_SUBJECTS = {
    'en': 'We received your {programme} application',
    'ms': 'Kami telah menerima permohonan {programme} anda',
    'ta': 'உங்கள் {programme} விண்ணப்பத்தைப் பெற்றோம்',
}

ACK_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "Thank you for applying to the {programme}. We have received your "
        "application and will review it against this round's criteria.\n\n"
        "If you are shortlisted, we will invite you to complete your profile. "
        "Either way, we will let you know the outcome.\n\n"
        "Warm regards,\nThe {programme} Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Terima kasih kerana memohon {programme}. Kami telah menerima "
        "permohonan anda dan akan menyemaknya berdasarkan kriteria pusingan "
        "ini.\n\n"
        "Jika anda disenarai pendek, kami akan menjemput anda melengkapkan "
        "profil anda. Walau apa pun, kami akan memaklumkan keputusannya.\n\n"
        "Salam hormat,\nPasukan {programme}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "{programme}-க்கு விண்ணப்பித்ததற்கு நன்றி. உங்கள் விண்ணப்பத்தைப் "
        "பெற்றோம்; இந்தச் சுற்றின் தகுதிகளுடன் ஒப்பிட்டு பரிசீலிப்போம்.\n\n"
        "நீங்கள் தேர்வுசெய்யப்பட்டால், உங்கள் சுயவிவரத்தை நிறைவுசெய்ய அழைப்போம். "
        "எவ்வாறாயினும், முடிவை உங்களுக்குத் தெரிவிப்போம்.\n\n"
        "அன்புடன்,\n{programme} குழு"
    ),
}


def normalise_lang(lang):
    return lang if lang in ('en', 'ms', 'ta') else 'en'


def send_acknowledgement_email(to_email, applicant_name, programme_name, lang='en'):
    """
    Send the application acknowledgement.

    Best-effort: a mail failure is logged and swallowed so it never blocks the
    application from being recorded. Returns True if the send succeeded.
    """
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or {'en': 'applicant', 'ms': 'pemohon', 'ta': 'விண்ணப்பதாரர்'}[lang]
    try:
        send_mail(
            subject=ACK_SUBJECTS[lang].format(programme=programme_name),
            message=ACK_BODIES[lang].format(name=name, programme=programme_name),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning(
            'Failed to send acknowledgement email to %s', to_email, exc_info=True
        )
        return False
