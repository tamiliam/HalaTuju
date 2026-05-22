"""
Trilingual emails for the B40 Assistance Programme.

Phase 1 uses email (every HalaTuju account has a verified Google address).
WhatsApp is a Phase 2 enhancement.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

_DEFAULT_NAME = {'en': 'applicant', 'ms': 'pemohon', 'ta': 'விண்ணப்பதாரர்'}

# ── Acknowledgement (on submit) ──────────────────────────────────────────
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

# ── Pass / shortlisted (sent immediately) ────────────────────────────────
PASS_SUBJECTS = {
    'en': 'Good news about your {programme} application',
    'ms': 'Berita baik tentang permohonan {programme} anda',
    'ta': 'உங்கள் {programme} விண்ணப்பம் குறித்த நற்செய்தி',
}
PASS_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "Congratulations — you have been shortlisted for the {programme}. "
        "The next step is to complete your profile so that sponsors can get to "
        "know you. We will be in touch shortly with what to do next.\n\n"
        "Warm regards,\nThe {programme} Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Tahniah — anda telah disenarai pendek untuk {programme}. Langkah "
        "seterusnya ialah melengkapkan profil anda supaya penaja dapat "
        "mengenali anda. Kami akan menghubungi anda tidak lama lagi dengan "
        "langkah seterusnya.\n\n"
        "Salam hormat,\nPasukan {programme}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "வாழ்த்துகள் — {programme}-க்கு நீங்கள் தேர்வுசெய்யப்பட்டுள்ளீர்கள். "
        "அடுத்த படியாக, ஆதரவாளர்கள் உங்களை அறிந்துகொள்ள உங்கள் சுயவிவரத்தை "
        "நிறைவுசெய்யவும். அடுத்த படிகள் குறித்து விரைவில் உங்களைத் "
        "தொடர்புகொள்வோம்.\n\n"
        "அன்புடன்,\n{programme} குழு"
    ),
}

# ── Fail / not this round (sent after the cohort delay) ──────────────────
FAIL_SUBJECTS = {
    'en': 'Update on your {programme} application',
    'ms': 'Maklumat terkini permohonan {programme} anda',
    'ta': 'உங்கள் {programme} விண்ணப்பம் குறித்த புதுப்பிப்பு',
}
FAIL_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "Thank you for applying to the {programme}. After reviewing this "
        "round's applications, we are unable to offer you assistance at this "
        "time. We will keep your details on file and will reach out if a "
        "suitable opportunity opens up.\n\n"
        "We wish you all the very best in your studies.\n\n"
        "Warm regards,\nThe {programme} Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Terima kasih kerana memohon {programme}. Setelah menyemak permohonan "
        "pusingan ini, kami tidak dapat menawarkan bantuan kepada anda pada "
        "masa ini. Kami akan menyimpan maklumat anda dan akan menghubungi anda "
        "jika peluang yang sesuai terbuka.\n\n"
        "Kami mengucapkan selamat maju jaya dalam pengajian anda.\n\n"
        "Salam hormat,\nPasukan {programme}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "{programme}-க்கு விண்ணப்பித்ததற்கு நன்றி. இந்தச் சுற்றின் "
        "விண்ணப்பங்களைப் பரிசீலித்த பிறகு, இந்த நேரத்தில் உங்களுக்கு உதவி வழங்க "
        "முடியவில்லை. உங்கள் விவரங்களை வைத்திருப்போம்; பொருத்தமான வாய்ப்பு "
        "ஏற்பட்டால் உங்களைத் தொடர்புகொள்வோம்.\n\n"
        "உங்கள் படிப்பில் சிறந்த வெற்றியை வாழ்த்துகிறோம்.\n\n"
        "அன்புடன்,\n{programme} குழு"
    ),
}


def normalise_lang(lang):
    return lang if lang in ('en', 'ms', 'ta') else 'en'


def _send(to_email, subjects, bodies, applicant_name, programme_name, lang):
    """
    Best-effort send: a mail failure is logged and swallowed so it never blocks
    the surrounding workflow. Returns True if the send succeeded.
    """
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    try:
        send_mail(
            subject=subjects[lang].format(programme=programme_name),
            message=bodies[lang].format(name=name, programme=programme_name),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning(
            'Failed to send scholarship email to %s', to_email, exc_info=True
        )
        return False


def send_acknowledgement_email(to_email, applicant_name, programme_name, lang='en'):
    return _send(to_email, ACK_SUBJECTS, ACK_BODIES, applicant_name, programme_name, lang)


def send_pass_email(to_email, applicant_name, programme_name, lang='en'):
    return _send(to_email, PASS_SUBJECTS, PASS_BODIES, applicant_name, programme_name, lang)


def send_fail_email(to_email, applicant_name, programme_name, lang='en'):
    return _send(to_email, FAIL_SUBJECTS, FAIL_BODIES, applicant_name, programme_name, lang)
