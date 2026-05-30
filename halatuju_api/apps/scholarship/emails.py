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

# ── Invitation / shortlisted (sent at +success_delay_hours, ~2h, by the scheduler) ──
PASS_SUBJECTS = {
    'en': 'Good news about your {programme} application',
    'ms': 'Berita baik tentang permohonan {programme} anda',
    'ta': 'உங்கள் {programme} விண்ணப்பம் குறித்த நற்செய்தி',
}
PASS_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "Congratulations — you have been shortlisted for the {programme}.\n\n"
        "The next step is to complete your profile so that sponsors can get to "
        "know you. You'll share a few more details and upload a few supporting "
        "documents (your IC, results slip, and proof of household income) — "
        "we'll show you exactly what's needed.\n\n"
        "Complete your profile here:\n{link}\n\n"
        "Warm regards,\nThe {programme} Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Tahniah — anda telah disenarai pendek untuk {programme}.\n\n"
        "Langkah seterusnya ialah melengkapkan profil anda supaya penaja dapat "
        "mengenali anda. Anda akan berkongsi beberapa butiran tambahan dan memuat "
        "naik beberapa dokumen sokongan (KP anda, slip keputusan, dan bukti "
        "pendapatan isi rumah) — kami akan tunjukkan dengan tepat apa yang "
        "diperlukan.\n\n"
        "Lengkapkan profil anda di sini:\n{link}\n\n"
        "Salam hormat,\nPasukan {programme}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "வாழ்த்துகள் — {programme}-க்கு நீங்கள் தேர்வுசெய்யப்பட்டுள்ளீர்கள்.\n\n"
        "அடுத்த படியாக, ஆதரவாளர்கள் உங்களை அறிந்துகொள்ள உங்கள் சுயவிவரத்தை "
        "நிறைவுசெய்யவும். சில கூடுதல் விவரங்களைப் பகிர்ந்து, சில ஆதார ஆவணங்களை "
        "(உங்கள் அடையாள அட்டை, முடிவுச் சீட்டு, மற்றும் குடும்ப வருமானச் சான்று) "
        "பதிவேற்றுவீர்கள் — என்ன தேவை என்பதைச் சரியாகக் காட்டுவோம்.\n\n"
        "உங்கள் சுயவிவரத்தை இங்கே நிறைவுசெய்யவும்:\n{link}\n\n"
        "அன்புடன்,\n{programme} குழு"
    ),
}

# ── Decline / not this round (warm; sent at +decline_delay_hours, ~48h, by the scheduler) ──
FAIL_SUBJECTS = {
    'en': 'Update on your {programme} application',
    'ms': 'Maklumat terkini permohonan {programme} anda',
    'ta': 'உங்கள் {programme} விண்ணப்பம் குறித்த புதுப்பிப்பு',
}
FAIL_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "Thank you for applying to the {programme}. We are not able to offer you "
        "this particular scholarship this round — please don't be discouraged.\n\n"
        "We wish you all the very best in your studies. You are warmly welcome to "
        "join the higher-education seminars we run, online and in person — we will "
        "send you the invitations.\n\n"
        "Warm regards,\nThe {programme} Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Terima kasih kerana memohon {programme}. Kami tidak dapat menawarkan "
        "biasiswa ini kepada anda pada pusingan ini — namun janganlah berkecil "
        "hati.\n\n"
        "Kami mengucapkan selamat maju jaya dalam pengajian anda. Anda dialu-alukan "
        "untuk menyertai seminar pendidikan tinggi yang kami anjurkan, dalam talian "
        "dan secara bersemuka — kami akan menghantar jemputan kepada anda.\n\n"
        "Salam hormat,\nPasukan {programme}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "{programme}-க்கு விண்ணப்பித்ததற்கு நன்றி. இந்தச் சுற்றில் இந்தக் "
        "குறிப்பிட்ட உதவித்தொகையை உங்களுக்கு வழங்க முடியவில்லை — ஆனால் மனம் "
        "தளராதீர்கள்.\n\n"
        "உங்கள் படிப்பில் சிறந்த வெற்றியை வாழ்த்துகிறோம். நாங்கள் நடத்தும் உயர்கல்வி "
        "கருத்தரங்குகளில் — இணையவழியிலும் நேரிலும் — கலந்துகொள்ள உங்களை அன்புடன் "
        "வரவேற்கிறோம்; அழைப்புகளை உங்களுக்கு அனுப்புவோம்.\n\n"
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
    # Link to the complete-your-profile page (the shortlist body uses {link}; the
    # ack/decline bodies don't reference it, so the kwarg is harmlessly ignored).
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    link = f"{frontend}/scholarship/application"
    try:
        send_mail(
            subject=subjects[lang].format(programme=programme_name),
            message=bodies[lang].format(name=name, programme=programme_name, link=link),
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


REQUEST_INFO_SUBJECTS = {
    'en': 'Action needed on your {programme} application',
    'ms': 'Tindakan diperlukan untuk permohonan {programme} anda',
    'ta': 'உங்கள் {programme} விண்ணப்பத்திற்கு நடவடிக்கை தேவை',
}
REQUEST_INFO_BODIES = {
    'en': ('Dear {name},\n\nWe are reviewing your {programme} application and need a '
           'little more from you:\n\n{note}\n\nPlease sign in and add it to your '
           'application here: {link}\n\nThank you.'),
    'ms': ('Salam {name},\n\nKami sedang menyemak permohonan {programme} anda dan '
           'memerlukan sedikit maklumat tambahan:\n\n{note}\n\nSila log masuk dan '
           'tambahkannya pada permohonan anda di sini: {link}\n\nTerima kasih.'),
    'ta': ('அன்புள்ள {name},\n\nஉங்கள் {programme} விண்ணப்பத்தை மதிப்பாய்வு செய்கிறோம், '
           'சிறிது கூடுதல் தகவல் தேவை:\n\n{note}\n\nதயவுசெய்து உள்நுழைந்து உங்கள் '
           'விண்ணப்பத்தில் இதைச் சேர்க்கவும்: {link}\n\nநன்றி.'),
}


def send_request_info_email(to_email, applicant_name, programme_name, note, lang='en'):
    """Phase C: ask the student for more documentation. Trilingual; best-effort."""
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    link = f'{frontend}/scholarship/application'
    try:
        send_mail(
            subject=REQUEST_INFO_SUBJECTS[lang].format(programme=programme_name),
            message=REQUEST_INFO_BODIES[lang].format(
                name=name, programme=programme_name, note=note, link=link),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send request-info email to %s', to_email, exc_info=True)
        return False


def send_sponsor_interest_admin_email(name, email, organisation, message):
    """Notify the admin that someone registered interest in sponsoring. English,
    to ``settings.ADMIN_NOTIFY_EMAIL``; skipped silently if unset. Best-effort."""
    to_email = getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or ''
    if not to_email:
        return False
    try:
        send_mail(
            subject='New sponsor interest registered',
            message=(
                f'{name} ({email}) has registered interest in sponsoring.\n'
                f'Organisation: {organisation or "—"}\n\n'
                f'Message:\n{message or "—"}'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send sponsor-interest email for %s', email, exc_info=True)
        return False


def send_profile_complete_admin_email(application_id, applicant_name, programme_name):
    """Phase C: notify the admin that an applicant has confirmed a complete Step-4
    profile and is ready for review. English-only (internal). Sent to
    ``settings.ADMIN_NOTIFY_EMAIL``; skipped silently if that's unset so it never
    blocks the student's confirm. Best-effort — swallows send failures."""
    to_email = getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or ''
    if not to_email:
        return False
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    name = applicant_name or 'An applicant'
    try:
        send_mail(
            subject=f'[{programme_name}] Application #{application_id} ready for review',
            message=(
                f'{name} has confirmed a complete profile for {programme_name} '
                f'(application #{application_id}) and is ready for review.\n\n'
                f'Review it: {frontend}/admin/scholarship/{application_id}'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send admin-notify email for application #%s',
                       application_id, exc_info=True)
        return False
