"""
Trilingual emails for the BrightPath Bursary Programme.

Phase 1 uses email (every HalaTuju account has a verified Google address).
WhatsApp is a Phase 2 enhancement.
"""
import logging
import os

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives, send_mail

from . import branding as _branding

# Per-org branding is read ONLY through the branding seam (decision D1). Sender identity,
# sign-off, programme name, persona, support/reply-to, topical aliases (interview@ / sponsor@)
# and the display domain all resolve there. ``_P`` is the platform branding (BrightPath / today's
# constants) — the default for internal/ops mail and the byte-identical fallback for every
# student-facing send that isn't handed a tenant ``branding``.
_P = _branding.platform()

# Back-compat alias for the platform support address (derived from the seam, not a literal).
# Kept because it is a documented public name of this module (imported by tests / callers).
SUPPORT_EMAIL = _P.email_support

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

# ── Invitation / shortlisted (sent at +success_delay_hours by the scheduler; per-cohort,
#    currently 55 min for b40-2026 — fast internal release; public criteria still say "within 2 days") ──
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

# ── Award confirmed (F8a) — sent when a student/guardian ACCEPTS an award. NO ──
# sponsor identity anywhere (B4 two-way anonymity); points to onboarding. ─────────
AWARD_CONFIRMED_SUBJECTS = {
    'en': 'Your {programme} funding is confirmed 🎉',
    'ms': 'Pembiayaan {programme} anda disahkan 🎉',
    'ta': 'உங்கள் {programme} நிதியுதவி உறுதிசெய்யப்பட்டது 🎉',
}
AWARD_CONFIRMED_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "Wonderful news — your funding for the {programme} has been confirmed. A "
        "supporter has chosen to fund your studies.\n\n"
        "There's one short step left before we begin: please complete your "
        "onboarding. It takes a few minutes — a short welcome, a few details to "
        "confirm, and a couple of questions so we can support you well.\n\n"
        "Complete your onboarding here:\n{link}\n\n"
        "Your supporter's details are kept private, just as yours are kept private "
        "from them. You'll be able to send an anonymous thank-you note later.\n\n"
        "Warm regards,\nThe {programme} Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Berita baik — pembiayaan anda untuk {programme} telah disahkan. Seorang "
        "penyokong telah memilih untuk membiayai pengajian anda.\n\n"
        "Tinggal satu langkah pendek sebelum kita bermula: sila lengkapkan proses "
        "onboarding anda. Ia mengambil masa beberapa minit — aluan ringkas, beberapa "
        "butiran untuk disahkan, dan beberapa soalan supaya kami dapat menyokong anda "
        "dengan baik.\n\n"
        "Lengkapkan onboarding anda di sini:\n{link}\n\n"
        "Butiran penyokong anda dirahsiakan, sama seperti butiran anda dirahsiakan "
        "daripada mereka. Anda boleh menghantar nota terima kasih tanpa nama kemudian.\n\n"
        "Salam hormat,\nPasukan {programme}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "மகிழ்ச்சியான செய்தி — {programme}-க்கான உங்கள் நிதியுதவி உறுதிசெய்யப்பட்டது. ஒரு "
        "ஆதரவாளர் உங்கள் படிப்புக்கு நிதியளிக்கத் தேர்ந்தெடுத்துள்ளார்.\n\n"
        "நாம் தொடங்குவதற்கு முன் ஒரே ஒரு சிறிய படி உள்ளது: உங்கள் onboarding-ஐ "
        "நிறைவுசெய்யவும். இதற்கு சில நிமிடங்களே ஆகும் — ஒரு குறுகிய வரவேற்பு, உறுதிப்படுத்த "
        "சில விவரங்கள், மற்றும் நாங்கள் உங்களை நன்றாக ஆதரிக்க சில கேள்விகள்.\n\n"
        "உங்கள் onboarding-ஐ இங்கே நிறைவுசெய்யவும்:\n{link}\n\n"
        "உங்கள் விவரங்கள் ஆதரவாளரிடமிருந்து ரகசியமாக வைக்கப்படுவதைப் போலவே, ஆதரவாளரின் "
        "விவரங்களும் ரகசியமாக வைக்கப்படுகின்றன. பின்னர் நீங்கள் அடையாளம் தெரியாத நன்றிக் "
        "குறிப்பை அனுப்பலாம்.\n\n"
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


# Bucket-specific decline copy. Tone is SUGGESTIVE of the reason (the user's call —
# a fully generic note is more frustrating than a gentle hint), never blunt. The
# generic FAIL_* above covers the 'ineligible' and 'contractual' buckets.

# 1) MERIT — did not meet the academic floor. Hints at "competitive on results".
MERIT_SUBJECTS = dict(FAIL_SUBJECTS)
MERIT_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "Thank you for applying to the {programme}, and for the effort behind your "
        "application.\n\n"
        "After careful review, we are not able to offer you a place this round. "
        "Selection this round was especially competitive on academic results, and we "
        "could not take every strong application forward.\n\n"
        "Please don't be discouraged — we warmly encourage you to keep building on "
        "your studies and to apply again. You are also very welcome to join the "
        "higher-education seminars we run, online and in person.\n\n"
        "Warm regards,\nThe {programme} Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Terima kasih kerana memohon {programme}, dan atas usaha di sebalik "
        "permohonan anda.\n\n"
        "Setelah penilaian teliti, kami tidak dapat menawarkan tempat kepada anda "
        "pada pusingan ini. Persaingan pada pusingan ini amat sengit dari segi "
        "keputusan akademik, dan kami tidak dapat meneruskan setiap permohonan yang "
        "cemerlang.\n\n"
        "Janganlah berkecil hati — kami menggalakkan anda terus mengukuhkan "
        "pelajaran anda dan memohon semula. Anda juga dialu-alukan menyertai seminar "
        "pendidikan tinggi yang kami anjurkan, dalam talian dan secara bersemuka.\n\n"
        "Salam hormat,\nPasukan {programme}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "{programme}-க்கு விண்ணப்பித்ததற்கும், உங்கள் விண்ணப்பத்தின் பின்னணியில் "
        "உள்ள முயற்சிக்கும் நன்றி.\n\n"
        "கவனமான மதிப்பாய்வுக்குப் பிறகு, இந்தச் சுற்றில் உங்களுக்கு இடம் வழங்க "
        "முடியவில்லை. இந்தச் சுற்று கல்வி முடிவுகளில் மிகவும் போட்டி நிறைந்ததாக "
        "இருந்தது; ஒவ்வொரு சிறந்த விண்ணப்பத்தையும் முன்னெடுக்க முடியவில்லை.\n\n"
        "மனம் தளராதீர்கள் — உங்கள் படிப்பைத் தொடர்ந்து வலுப்படுத்தி மீண்டும் "
        "விண்ணப்பிக்க அன்புடன் ஊக்குவிக்கிறோம். நாங்கள் நடத்தும் உயர்கல்விக் "
        "கருத்தரங்குகளில் — இணையவழியிலும் நேரிலும் — கலந்துகொள்ளவும் வரவேற்கிறோம்.\n\n"
        "அன்புடன்,\n{programme} குழு"
    ),
}

# 2) NEED — did not meet the financial-need criteria. Hints at "greatest need".
NEED_SUBJECTS = dict(FAIL_SUBJECTS)
NEED_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "Thank you for applying to the {programme}.\n\n"
        "This programme is directed to students facing the greatest financial need. "
        "After careful review, we are not able to offer you a place this round — "
        "places this round were prioritised on that basis.\n\n"
        "Please don't be discouraged. If your circumstances change you are warmly "
        "welcome to apply again, and to join the higher-education seminars we run, "
        "online and in person.\n\n"
        "Warm regards,\nThe {programme} Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Terima kasih kerana memohon {programme}.\n\n"
        "Program ini ditujukan kepada pelajar yang menghadapi keperluan kewangan "
        "yang paling mendesak. Setelah penilaian teliti, kami tidak dapat menawarkan "
        "tempat kepada anda pada pusingan ini — tempat pada pusingan ini diutamakan "
        "atas dasar tersebut.\n\n"
        "Janganlah berkecil hati. Sekiranya keadaan anda berubah, anda dialu-alukan "
        "untuk memohon semula, dan menyertai seminar pendidikan tinggi yang kami "
        "anjurkan, dalam talian dan secara bersemuka.\n\n"
        "Salam hormat,\nPasukan {programme}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "{programme}-க்கு விண்ணப்பித்ததற்கு நன்றி.\n\n"
        "இந்தத் திட்டம் மிகக் கடுமையான நிதித் தேவை உள்ள மாணவர்களுக்காக "
        "வடிவமைக்கப்பட்டுள்ளது. கவனமான மதிப்பாய்வுக்குப் பிறகு, இந்தச் சுற்றில் "
        "உங்களுக்கு இடம் வழங்க முடியவில்லை — இந்தச் சுற்றில் இடங்கள் அந்த "
        "அடிப்படையில் முன்னுரிமை வழங்கப்பட்டன.\n\n"
        "மனம் தளராதீர்கள். உங்கள் சூழ்நிலை மாறினால், மீண்டும் விண்ணப்பிக்கவும், "
        "நாங்கள் நடத்தும் உயர்கல்விக் கருத்தரங்குகளில் — இணையவழியிலும் நேரிலும் — "
        "கலந்துகொள்ளவும் அன்புடன் வரவேற்கிறோம்.\n\n"
        "அன்புடன்,\n{programme} குழு"
    ),
}

# 3) INTERVIEW — reviewed (docs/interview) but not selected. Extra-thankful; limited
# budget; only those who most strongly met BOTH need (primarily) and merit.
INTERVIEW_SUBJECTS = {
    'en': 'Thank you for your {programme} application',
    'ms': 'Terima kasih atas permohonan {programme} anda',
    'ta': 'உங்கள் {programme} விண்ணப்பத்திற்கு நன்றி',
}
INTERVIEW_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "Thank you for completing your {programme} application and for taking the "
        "time to submit your documents for our review — we genuinely appreciate the "
        "effort you put in.\n\n"
        "With the limited funding available this round, we were only able to support "
        "the students who most closely met both our financial-need and academic "
        "criteria. After careful consideration, we are not able to offer you a place "
        "this time.\n\n"
        "This is in no way a reflection of your ability or potential, and we warmly "
        "encourage you to apply again in future. You are also very welcome to join "
        "the higher-education seminars we run, online and in person.\n\n"
        "With our sincere thanks and very best wishes,\nThe {programme} Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Terima kasih kerana melengkapkan permohonan {programme} anda dan kerana "
        "meluangkan masa menghantar dokumen untuk semakan kami — kami amat "
        "menghargai usaha anda.\n\n"
        "Dengan dana yang terhad pada pusingan ini, kami hanya mampu membantu pelajar "
        "yang paling hampir memenuhi kedua-dua kriteria keperluan kewangan dan "
        "akademik. Setelah pertimbangan yang teliti, kami tidak dapat menawarkan "
        "tempat kepada anda pada kali ini.\n\n"
        "Ini sama sekali bukan gambaran tentang kebolehan atau potensi anda, dan kami "
        "menggalakkan anda memohon semula pada masa hadapan. Anda juga dialu-alukan "
        "menyertai seminar pendidikan tinggi yang kami anjurkan, dalam talian dan "
        "secara bersemuka.\n\n"
        "Dengan ucapan terima kasih yang ikhlas dan salam sejahtera,\nPasukan {programme}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "உங்கள் {programme} விண்ணப்பத்தை நிறைவு செய்ததற்கும், எங்கள் "
        "மதிப்பாய்வுக்காக உங்கள் ஆவணங்களைச் சமர்ப்பிக்க நேரம் ஒதுக்கியதற்கும் "
        "நன்றி — உங்கள் முயற்சியை நாங்கள் உண்மையாகவே பாராட்டுகிறோம்.\n\n"
        "இந்தச் சுற்றில் கிடைத்த வரையறுக்கப்பட்ட நிதியுடன், நிதித் தேவை மற்றும் "
        "கல்வி ஆகிய இரண்டு அளவுகோல்களையும் மிக நெருக்கமாகப் பூர்த்திசெய்த "
        "மாணவர்களுக்கு மட்டுமே உதவ முடிந்தது. கவனமான பரிசீலனைக்குப் பிறகு, இந்த "
        "முறை உங்களுக்கு இடம் வழங்க முடியவில்லை.\n\n"
        "இது உங்கள் திறமை அல்லது ஆற்றலின் பிரதிபலிப்பு அல்ல; எதிர்காலத்தில் "
        "மீண்டும் விண்ணப்பிக்க அன்புடன் ஊக்குவிக்கிறோம். நாங்கள் நடத்தும் "
        "உயர்கல்விக் கருத்தரங்குகளில் — இணையவழியிலும் நேரிலும் — கலந்துகொள்ளவும் "
        "வரவேற்கிறோம்.\n\n"
        "எங்கள் உளமார்ந்த நன்றியுடனும் வாழ்த்துகளுடனும்,\n{programme} குழு"
    ),
}

# category → (subjects, bodies). Anything not listed (ineligible, contractual, '') → generic FAIL.
_DECLINE_TEMPLATES = {
    'merit': (MERIT_SUBJECTS, MERIT_BODIES),
    'need': (NEED_SUBJECTS, NEED_BODIES),
    'interview': (INTERVIEW_SUBJECTS, INTERVIEW_BODIES),
}


def normalise_lang(lang):
    return lang if lang in ('en', 'ms', 'ta') else 'en'


def _send(to_email, subjects, bodies, applicant_name, programme_name, lang, extra=None):
    """
    Best-effort send: a mail failure is logged and swallowed so it never blocks
    the surrounding workflow. Returns True if the send succeeded. ``extra`` supplies
    any additional, already-language-resolved body placeholders (e.g. {help}); a
    template that doesn't reference them ignores the extras harmlessly.
    """
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    # Link to the complete-your-profile page (the shortlist body uses {link}; the
    # ack/decline bodies don't reference it, so the kwarg is harmlessly ignored).
    frontend = _P.frontend_url
    link = f"{frontend}/scholarship/application"
    fmt = {'name': name, 'programme': programme_name, 'link': link, **(extra or {})}
    try:
        send_mail(
            subject=subjects[lang].format(programme=programme_name),
            message=bodies[lang].format(**fmt),
            from_email=_P.email_from,
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


# Sent the moment a SHORTLISTED student submits their completed profile (Check 2). A warm
# "we've got it, we'll review and revert" — NOT the questions (those follow ~2h later, so
# they read as a human review rather than an instant bot reply).
SUBMISSION_ACK_SUBJECTS = {
    'en': "We've received your completed {programme} application",
    'ms': 'Kami telah menerima permohonan {programme} anda yang lengkap',
    'ta': 'உங்கள் நிறைவு செய்யப்பட்ட {programme} விண்ணப்பத்தைப் பெற்றோம்',
}
SUBMISSION_ACK_BODIES = {
    'en': ("Dear {name},\n\nThank you for submitting your {programme} application. Our team "
           "will review it and get back to you. If we need any additional information or "
           "documents, we'll be in touch.\n\nWarm regards,\nThe {programme} Team"),
    'ms': ("Salam {name},\n\nTerima kasih kerana menghantar permohonan {programme} anda. "
           "Pasukan kami akan menyemaknya dan menghubungi anda semula. Jika kami memerlukan "
           "sebarang maklumat atau dokumen tambahan, kami akan memaklumkan anda.\n\n"
           "Salam hormat,\nPasukan {programme}"),
    'ta': ("அன்புள்ள {name},\n\nஉங்கள் {programme} விண்ணப்பத்தைச் சமர்ப்பித்ததற்கு நன்றி. "
           "எங்கள் குழு அதைப் பரிசீலித்து உங்களைத் தொடர்புகொள்ளும். கூடுதல் தகவல் அல்லது "
           "ஆவணங்கள் தேவைப்பட்டால், நாங்கள் தொடர்புகொள்வோம்.\n\nஅன்புடன்,\n{programme} குழு"),
}


def send_submission_received_email(to_email, applicant_name, programme_name, lang='en'):
    """Check 2: acknowledge a completed-profile submission (we'll review and revert)."""
    return _send(to_email, SUBMISSION_ACK_SUBJECTS, SUBMISSION_ACK_BODIES,
                 applicant_name, programme_name, lang)


def send_pass_email(to_email, applicant_name, programme_name, lang='en'):
    return _send(to_email, PASS_SUBJECTS, PASS_BODIES, applicant_name, programme_name, lang)


def send_award_confirmed_email(to_email, applicant_name, programme_name, lang='en'):
    """F8a: sent when a student/guardian ACCEPTS an award. Carries NO sponsor identity
    (B4 two-way anonymity) — only that funding is confirmed + the onboarding link."""
    return _send(to_email, AWARD_CONFIRMED_SUBJECTS, AWARD_CONFIRMED_BODIES,
                 applicant_name, programme_name, lang)


# Sent when a student is AWARDED (a sponsor committed → status 'awarded'), BEFORE the formal
# offer/acceptance.
#
# MERGED 2026-07-12 (owner): this now carries the GOOD NEWS **and** the Vircle setup in ONE email.
# It used to end "there's nothing you need to do right now — look out for our next message", and a
# second email followed with the Vircle instructions. That seam is gone: a student awarded from now
# on is told the news and the one thing to do, in the same breath. (The standalone Vircle email is
# KEPT — the 22 students already awarded got the old good-news email, and it's still the tool for a
# re-send or a manual case.)
#
# UNCHANGED and deliberate: NO amount (the formal offer carries the figure), NO sponsor identity
# (two-way anonymity), NO bank-details ask (money moves through Vircle now). The formal offer +
# bursary contract still follow as their own step — the contract is being finalised.
# From info@, reply-to help@. Guide PDF attached. Good-news wording owner-cleared 2026-06-30.
AWARD_OFFER_SUBJECTS = {
    'en': 'Good news about your BrightPath Bursary application 🎓',
    'ms': 'Berita baik tentang permohonan Bursari BrightPath anda 🎓',
    'ta': 'உங்கள் BrightPath Bursary விண்ணப்பம் பற்றிய நல்ல செய்தி 🎓',
}
AWARD_OFFER_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "We're delighted to share some good news. Your application to the BrightPath Bursary "
        "Programme has been successful — you have been selected to receive financial support for "
        "your studies.\n\n"
        "Your support is paid monthly through Vircle, a Malaysian eWallet app. There are TWO "
        "steps to start receiving it, and your payments can only begin once BOTH are done.\n\n"
        "STEP 1 — Install Vircle and activate your account.\n"
        "Install the Vircle app from the Apple App Store, Google Play Store or Huawei AppGallery "
        "(you'll need iOS 16 or above, or Android 10 or above — a very old phone can fail during "
        "registration even if it meets this; if it stalls, try again on a newer phone). When you "
        "sign up, the app asks you to register a Parent account: that is simply Vircle's name for "
        "the main adult account, and it is the correct one for you. Have your MyKad in your hand "
        "before you start — the app photographs the actual card, so a photocopy, a scan, or an "
        "image on another screen will be rejected. The step-by-step guide is attached to this "
        "email.\n\n"
        "{guardian_note}"
        "STEP 2 — Tell us in the Action Centre.\n"
        "Once your account is active, sign in at halatuju.xyz and open your application page. In "
        "the Action Centre, enter the mobile number you registered with Vircle AND your "
        "eWallet ID. To find your eWallet ID: open the Vircle app, tap the gear icon at the top "
        "right of the home screen, then scroll to the bottom of the Settings page — it reads "
        "\"Your eWallet ID\" followed by a 13-digit number.\n\n"
        "Step 2 is not optional: we can only arrange your monthly payments after you have told us "
        "these details. (The attached guide may ask you to message Vircle on WhatsApp — you may, "
        "but telling us in the Action Centre is what starts your payments.)\n\n"
        "A formal offer and bursary contract will follow separately, along with the simple steps to "
        "accept it.\n\n"
        "If you faced any trouble during registration or activation, or have any questions, reply "
        "to this email or contact us at {support}.\n\n"
        "Warm congratulations,\nThe BrightPath Bursary Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Kami gembira berkongsi berita baik. Permohonan anda ke Program Bursari BrightPath telah "
        "berjaya — anda telah dipilih untuk menerima bantuan kewangan bagi pengajian anda.\n\n"
        "Bantuan anda dibayar setiap bulan melalui Vircle, sebuah aplikasi eWallet Malaysia. "
        "Terdapat DUA langkah untuk mula menerimanya, dan pembayaran hanya boleh bermula setelah "
        "KEDUA-DUA langkah selesai.\n\n"
        "LANGKAH 1 — Pasang Vircle dan aktifkan akaun anda.\n"
        "Pasang aplikasi Vircle dari Apple App Store, Google Play Store atau Huawei AppGallery "
        "(anda memerlukan iOS 16 ke atas, atau Android 10 ke atas — telefon yang terlalu lama "
        "boleh gagal semasa pendaftaran walaupun memenuhi syarat ini; jika ia tersekat, cuba "
        "semula dengan telefon yang lebih baharu). Semasa mendaftar, aplikasi akan meminta anda "
        "mendaftar Akaun Parent: itu hanyalah nama Vircle bagi akaun dewasa utama, dan ia adalah "
        "akaun yang betul untuk anda. Pastikan MyKad anda ada di tangan sebelum mula — aplikasi "
        "akan memotret kad sebenar, jadi gambar salinan fotostat, imbasan, atau imej pada skrin "
        "lain akan ditolak. Panduan langkah demi langkah disertakan bersama e-mel ini.\n\n"
        "{guardian_note}"
        "LANGKAH 2 — Beritahu kami di Pusat Tindakan.\n"
        "Sebaik sahaja akaun anda aktif, log masuk di halatuju.xyz dan buka halaman permohonan "
        "anda. Di Pusat Tindakan, masukkan nombor telefon bimbit yang anda daftarkan dengan "
        "Vircle DAN ID eWallet anda. Untuk mencari ID eWallet anda: buka aplikasi Vircle, tekan "
        "ikon gear di penjuru kanan atas skrin utama, kemudian skrol ke bahagian bawah halaman "
        "Settings — tertera \"Your eWallet ID\" diikuti nombor 13 digit.\n\n"
        "Langkah 2 bukan pilihan: kami hanya dapat mengaturkan pembayaran bulanan anda selepas "
        "anda memberitahu kami butiran ini. (Panduan yang disertakan mungkin meminta anda "
        "menghantar mesej WhatsApp kepada Vircle — anda boleh berbuat demikian, tetapi "
        "memberitahu kami di Pusat Tindakan itulah yang memulakan pembayaran anda.)\n\n"
        "Tawaran rasmi dan kontrak biasiswa akan menyusul secara berasingan, berserta langkah mudah "
        "untuk menerimanya.\n\n"
        "Jika anda menghadapi sebarang masalah semasa pendaftaran atau pengaktifan, atau ada "
        "pertanyaan, balas e-mel ini atau hubungi kami di {support}.\n\n"
        "Tahniah,\nPasukan Program Bursari BrightPath"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "ஒரு நல்ல செய்தியைப் பகிர்வதில் மகிழ்ச்சி அடைகிறோம். BrightPath Bursary திட்டத்திற்கான உங்கள் "
        "விண்ணப்பம் வெற்றிபெற்றுள்ளது — உங்கள் படிப்பிற்கான நிதியுதவியைப் பெற நீங்கள் தேர்ந்தெடுக்கப்பட்டுள்ளீர்கள்.\n\n"
        "உங்கள் உதவி Vircle என்ற மலேசிய eWallet செயலி வழியாக மாதந்தோறும் வழங்கப்படும். அதைப் பெறத் "
        "தொடங்க இரண்டு படிகள் உள்ளன; இரண்டையும் முடித்த பிறகே கட்டணங்கள் தொடங்க முடியும்.\n\n"
        "படி 1 — Vircle-ஐ நிறுவி உங்கள் கணக்கைச் செயல்படுத்துங்கள்.\n"
        "Apple App Store, Google Play Store அல்லது Huawei AppGallery-இலிருந்து Vircle செயலியை "
        "நிறுவவும் (iOS 16 அல்லது அதற்கு மேல், அல்லது Android 10 அல்லது அதற்கு மேல் தேவை — மிகவும் "
        "பழைய தொலைபேசி இதைப் பூர்த்தி செய்தாலும் பதிவின்போது தோல்வியடையலாம்; நின்றுவிட்டால், புதிய "
        "தொலைபேசியில் மீண்டும் முயற்சிக்கவும்). பதிவு செய்யும்போது, ஒரு Parent கணக்கைப் பதிவு செய்யுமாறு "
        "செயலி கேட்கும்: அது Vircle நிறுவனம் முதன்மை வயதுவந்தோர் கணக்கிற்கு வைத்துள்ள பெயர் மட்டுமே; "
        "அதுவே உங்களுக்கான சரியான கணக்கு. தொடங்கும் முன் உங்கள் MyKad-ஐ கையில் வைத்திருங்கள் — செயலி "
        "உண்மையான அட்டையைப் புகைப்படம் எடுக்கிறது; நகல், ஸ்கேன், அல்லது மற்றொரு திரையில் உள்ள படம் "
        "நிராகரிக்கப்படும். படிப்படியான வழிகாட்டி இந்த மின்னஞ்சலுடன் இணைக்கப்பட்டுள்ளது.\n\n"
        "{guardian_note}"
        "படி 2 — Action Centre-இல் எங்களிடம் தெரிவியுங்கள்.\n"
        "உங்கள் கணக்கு செயல்பட்டவுடன், halatuju.xyz-இல் உள்நுழைந்து உங்கள் விண்ணப்பப் பக்கத்தைத் "
        "திறக்கவும். Action Centre-இல், Vircle-இல் நீங்கள் பதிவு செய்த கைபேசி எண்ணையும் உங்கள் "
        "eWallet ID-யையும் உள்ளிடவும். உங்கள் eWallet ID-ஐக் கண்டறிய: Vircle செயலியைத் திறந்து, "
        "முகப்புத் திரையின் மேல் வலது மூலையில் உள்ள gear ஐகானை அழுத்தி, Settings பக்கத்தின் "
        "கீழ்ப்பகுதிக்கு உருட்டவும் — அங்கு \"Your eWallet ID\" என்பதற்குப் பின் 13 இலக்க எண் இருக்கும்.\n\n"
        "படி 2 விருப்பத்தேர்வு அல்ல: இந்த விவரங்களை நீங்கள் தெரிவித்த பிறகே உங்கள் மாதாந்திரக் "
        "கட்டணங்களை நாங்கள் ஏற்பாடு செய்ய முடியும். (இணைக்கப்பட்ட வழிகாட்டி Vircle-க்கு WhatsApp "
        "அனுப்பச் சொல்லலாம் — நீங்கள் அனுப்பலாம்; ஆனால் Action Centre-இல் எங்களிடம் தெரிவிப்பதே உங்கள் "
        "கட்டணங்களைத் தொடங்கும்.)\n\n"
        "முறையான வழங்கல் (offer) மற்றும் உதவித்தொகை ஒப்பந்தம் (bursary contract), அதை ஏற்கும் எளிய "
        "படிகளுடன், தனியாக அனுப்பப்படும்.\n\n"
        "பதிவு அல்லது செயல்படுத்தும் போது ஏதேனும் சிக்கல் ஏற்பட்டால், அல்லது ஏதேனும் கேள்விகள் இருந்தால், "
        "இந்த மின்னஞ்சலுக்குப் பதிலளிக்கவும் அல்லது {support} இல் எங்களைத் தொடர்புகொள்ளவும்.\n\n"
        "இதயப்பூர்வ வாழ்த்துகள்,\nBrightPath Bursary குழு"
    ),
}

# The parent/guardian route (owner 2026-07-17): shown ONLY to a student born after 2008
# (``not vircle.can_register(app)``) — everyone else never sees it. {support} is pre-formatted
# by the sender before insertion.
AWARD_OFFER_GUARDIAN_NOTES = {
    'en': (
        "If you were born after 2008, you cannot open your own Vircle account yet. Ask a parent "
        "or guardian to register their own Vircle account instead, then email us at {support} "
        "and we'll arrange for you to be added to it."
    ),
    'ms': (
        "Jika anda lahir selepas tahun 2008, anda belum boleh membuka akaun Vircle anda sendiri. "
        "Sebaliknya, minta ibu bapa atau penjaga anda mendaftar akaun Vircle mereka sendiri, "
        "kemudian e-mel kami di {support} dan kami akan uruskan supaya anda ditambah ke dalam "
        "akaun tersebut."
    ),
    'ta': (
        "நீங்கள் 2008-க்குப் பிறகு பிறந்திருந்தால், உங்கள் சொந்த Vircle கணக்கை இப்போது திறக்க முடியாது. "
        "அதற்குப் பதிலாக, உங்கள் பெற்றோர் அல்லது பாதுகாவலரை அவர்களின் சொந்த Vircle கணக்கைப் பதிவு "
        "செய்யச் சொல்லுங்கள்; பிறகு {support} இல் எங்களுக்கு மின்னஞ்சல் அனுப்புங்கள் — அந்தக் கணக்கில் "
        "உங்களைச் சேர்ப்பதற்கு நாங்கள் ஏற்பாடு செய்வோம்."
    ),
}


# The key phrases rendered BOLD in the HTML, per language. Each must be an exact substring of the
# body above — a phrase that isn't found is silently left un-bolded. Since the merge these cover
# BOTH halves: how support is paid, and the Vircle facts a student must not miss (the "Parent"
# account, the birth-year rule, the physical-MyKad rule) plus the contract still to come.
_BOLD_PHRASES = {
    'en': ['TWO steps', 'STEP 1 — Install Vircle and activate your account.',
           'STEP 2 — Tell us in the Action Centre.', 'register a Parent account',
           'photographs the actual card', 'eWallet ID', 'Step 2 is not optional',
           'formal offer and bursary contract'],
    'ms': ['DUA langkah', 'LANGKAH 1 — Pasang Vircle dan aktifkan akaun anda.',
           'LANGKAH 2 — Beritahu kami di Pusat Tindakan.', 'mendaftar Akaun Parent',
           'memotret kad sebenar', 'ID eWallet', 'Langkah 2 bukan pilihan',
           'Tawaran rasmi dan kontrak biasiswa'],
    'ta': ['இரண்டு படிகள்', 'படி 1 — Vircle-ஐ நிறுவி உங்கள் கணக்கைச் செயல்படுத்துங்கள்.',
           'படி 2 — Action Centre-இல் எங்களிடம் தெரிவியுங்கள்.', 'Parent கணக்கைப் பதிவு செய்யுமாறு',
           'உண்மையான அட்டையைப் புகைப்படம் எடுக்கிறது', 'eWallet ID',
           'படி 2 விருப்பத்தேர்வு அல்ல'],
}


def _award_offer_html(text_body, lang):
    """HTML for the award email: paragraphs, key phrases BOLD, the sign-off team name bolded,
    "the Action Centre" as an inline LINK where the ask is made, and a call-to-action button under
    the sign-off. Since the merge this email DOES ask something of the student (set up Vircle), so
    it carries both routes to /scholarship/application. Falls back gracefully: a phrase that isn't
    found is left un-bolded/un-linked."""
    import html as _h
    frontend = _P.frontend_url
    link_phrase = _VIRCLE_LINK_PHRASES.get(lang, _VIRCLE_LINK_PHRASES['en'])
    phrases = _BOLD_PHRASES.get(lang, [])

    def _emphasise(escaped):
        for ph in phrases:
            if ph:
                escaped = escaped.replace(_h.escape(ph), f'<strong>{_h.escape(ph)}</strong>')
        if link_phrase:
            esc_link = _h.escape(link_phrase)
            anchor = (f'<a href="{frontend}/scholarship/application" '
                      f'style="color:#2563eb;font-weight:600;">{esc_link}</a>')
            escaped = escaped.replace(esc_link, anchor, 1)
        return escaped

    def _bold_team(escaped):
        # Bold the team-name line (after the salutation) of the sign-off paragraph.
        head, sep, team = escaped.rpartition('\n')
        return f'{head}\n<strong>{team}</strong>' if sep else f'<strong>{escaped}</strong>'

    paras = [p.strip() for p in (text_body or '').split('\n\n') if p.strip()]
    blocks = []
    for idx, para in enumerate(paras):
        esc = _emphasise(_h.escape(para))
        if idx == len(paras) - 1 and '\n' in para:   # final paragraph = the sign-off
            esc = _bold_team(esc)
        blocks.append(f'<p style="margin:0 0 14px;">{esc.replace(chr(10), "<br>")}</p>')

    button = _email_button(f'{frontend}/scholarship/application',
                           VIRCLE_CTA_LABELS.get(lang, VIRCLE_CTA_LABELS['en']))
    blocks.append(f'<p style="margin:22px 0 6px;">{button}</p>')
    return _html_email_shell(''.join(blocks))


def send_award_offer_email(to_email, applicant_name, lang='en', guardian_note=False):
    """Award email: a sponsor has committed (status 'awarded'). Since the 2026-07-12 merge this is
    ONE email carrying the good news AND the Vircle setup, restructured 2026-07-17 (owner) as TWO
    explicit steps — STEP 1 install/activate, STEP 2 confirm in the Action Centre (students were
    skipping step 2). The installation guide is attached. The formal offer + bursary contract still
    follow separately. NO amount, NO sponsor identity, NO bank-details ask. HTML (key phrases BOLD,
    inline Action-Centre link + CTA button) + plain-text fallback, from info@, reply-to help@.

    ``guardian_note=True`` (a student born after 2008, ``not vircle.can_register(app)``) inserts
    the parent/guardian-account paragraph after step 1; everyone else never sees it.

    The CALLER raises the Action-Centre task on a successful send (see sponsorship.py) — the task
    must never appear for a student who didn't get the email."""
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    note = (AWARD_OFFER_GUARDIAN_NOTES[lang].format(support=_P.email_support) + '\n\n'
            if guardian_note else '')
    fmt = {'name': name, 'support': _P.email_support, 'guardian_note': note}
    subject = AWARD_OFFER_SUBJECTS[lang]
    text_body = AWARD_OFFER_BODIES[lang].format(**fmt)
    guide = vircle_guide_attachment()
    return _send_html(
        to_email, subject, text_body, _award_offer_html(text_body, lang),
        from_email=_P.email_from,
        reply_to=[_P.email_support],
        attachments=[guide] if guide else None,
    )


# ── Award email, CONTRACT-MODE variant (BURSARY_AGREEMENT_ENABLED) ────────────
# The go-live transition (2026-07-19) splits the award email in two. When the bursary
# agreement flag is ON, the good-news email's next step is to REVIEW AND SIGN the
# agreement — NOT to set up Vircle. Vircle setup now follows automatically once the
# agreement is fully executed (bursary.distribute_executed_agreement). So this variant
# carries NO Vircle content and NO guide attachment, and its caller raises NO setup task.
# Still: NO amount, NO sponsor identity. First-draft trilingual copy — owner to review.
AWARD_OFFER_SIGN_SUBJECTS = {
    'en': 'Good news about your BrightPath Bursary application 🎓',
    'ms': 'Berita baik tentang permohonan Bursari BrightPath anda 🎓',
    'ta': 'உங்கள் BrightPath Bursary விண்ணப்பம் பற்றிய நல்ல செய்தி 🎓',
}
AWARD_OFFER_SIGN_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "We're delighted to share some good news. Your application to the BrightPath Bursary "
        "Programme has been successful — you have been selected to receive financial support for "
        "your studies.\n\n"
        "The next step is to review and sign your bursary agreement. Please log in and open your "
        "application page, where you'll first go through a short, friendly check to make sure the "
        "terms are clear, and then sign the agreement together with your parent or guardian — all "
        "on the same device.\n{link}\n\n"
        "Please have your parent or guardian with you when you sign: they sign as your guarantor, "
        "and we'll send a one-time PIN to their phone to confirm it's them.\n\n"
        "Once everything is signed, we'll be in touch with the simple steps to start receiving your "
        "monthly support.\n\n"
        "If you have any questions, reply to this email or contact us at {support}.\n\n"
        "Warm congratulations,\nThe BrightPath Bursary Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Kami gembira berkongsi berita baik. Permohonan anda ke Program Bursari BrightPath telah "
        "berjaya — anda telah dipilih untuk menerima bantuan kewangan bagi pengajian anda.\n\n"
        "Langkah seterusnya ialah menyemak dan menandatangani perjanjian biasiswa anda. Sila log "
        "masuk dan buka halaman permohonan anda. Anda akan melalui semakan ringkas dan mesra "
        "dahulu untuk memastikan terma jelas, kemudian menandatangani perjanjian bersama ibu bapa "
        "atau penjaga anda — semuanya pada peranti yang sama.\n{link}\n\n"
        "Sila pastikan ibu bapa atau penjaga anda bersama anda semasa menandatangani: mereka "
        "menandatangani sebagai penjamin anda, dan kami akan menghantar PIN sekali guna ke telefon "
        "mereka untuk mengesahkannya.\n\n"
        "Setelah semuanya ditandatangani, kami akan menghubungi anda dengan langkah mudah untuk "
        "mula menerima bantuan bulanan anda.\n\n"
        "Jika ada sebarang pertanyaan, balas e-mel ini atau hubungi kami di {support}.\n\n"
        "Tahniah,\nPasukan Program Bursari BrightPath"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "ஒரு நல்ல செய்தியைப் பகிர்வதில் மகிழ்ச்சி அடைகிறோம். BrightPath Bursary திட்டத்திற்கான உங்கள் "
        "விண்ணப்பம் வெற்றிபெற்றுள்ளது — உங்கள் படிப்பிற்கான நிதியுதவியைப் பெற நீங்கள் தேர்ந்தெடுக்கப்பட்டுள்ளீர்கள்.\n\n"
        "அடுத்த படி, உங்கள் உதவித்தொகை ஒப்பந்தத்தை மதிப்பாய்வு செய்து கையொப்பமிடுவதாகும். உள்நுழைந்து உங்கள் "
        "விண்ணப்பப் பக்கத்தைத் திறக்கவும். முதலில் விதிமுறைகள் தெளிவாக இருப்பதை உறுதிசெய்ய ஒரு சிறிய, நட்பான "
        "சரிபார்ப்பின் வழியாகச் செல்வீர்கள், பின்னர் உங்கள் பெற்றோர் அல்லது பாதுகாவலருடன் சேர்ந்து — ஒரே சாதனத்தில் — "
        "ஒப்பந்தத்தில் கையொப்பமிடுவீர்கள்.\n{link}\n\n"
        "கையொப்பமிடும்போது உங்கள் பெற்றோர் அல்லது பாதுகாவலர் உங்களுடன் இருப்பதை உறுதிசெய்யவும்: அவர்கள் உங்கள் "
        "பிணையாளராகக் கையொப்பமிடுகிறார்கள், அவர்கள்தான் என்பதை உறுதிப்படுத்த அவர்களின் தொலைபேசிக்கு ஒரு முறை "
        "PIN அனுப்புவோம்.\n\n"
        "எல்லாம் கையொப்பமிடப்பட்ட பிறகு, உங்கள் மாதாந்திர உதவியைப் பெறத் தொடங்குவதற்கான எளிய படிகளுடன் உங்களைத் "
        "தொடர்புகொள்வோம்.\n\n"
        "ஏதேனும் கேள்விகள் இருந்தால், இந்த மின்னஞ்சலுக்குப் பதிலளிக்கவும் அல்லது {support} இல் எங்களைத் "
        "தொடர்புகொள்ளவும்.\n\n"
        "இதயப்பூர்வ வாழ்த்துகள்,\nBrightPath Bursary குழு"
    ),
}


def send_award_offer_sign_email(to_email, applicant_name, lang='en'):
    """Contract-mode (BURSARY_AGREEMENT_ENABLED) award email: the same good news, but the
    next step is to REVIEW AND SIGN the bursary agreement — NOT Vircle setup (which now
    follows at agreement execution). Points to /scholarship/award. NO amount, NO sponsor
    identity, NO Vircle content or guide. Best-effort; from info@, reply-to help@.

    The CALLER (release_award_offer_emails, flag-ON branch) does NOT raise a Vircle setup
    task on this path — the task is raised at execution instead."""
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    frontend = _P.frontend_url
    link = f'{frontend}/scholarship/award'
    body = AWARD_OFFER_SIGN_BODIES[lang].format(name=name, link=link, support=_P.email_support)
    html = _html_email_shell('<p style="margin:0 0 14px;">'
                             + body.replace('\n\n', '</p><p style="margin:0 0 14px;">').replace('\n', '<br>')
                             + '</p>')
    return _send_html(
        to_email, AWARD_OFFER_SIGN_SUBJECTS[lang], body, html,
        from_email=_P.email_from,
        reply_to=[_P.email_support],
    )


# ── Vircle eWallet setup (VIRCLE_SETUP_ENABLED) ───────────────────────────────
# The follow-up to the award email (which said "nothing to do right now — look out for our
# next message"). This IS that message: the bursary is paid through the Vircle eWallet, so
# install it, then TELL US in the Action Centre. Owner decisions baked into this copy:
#   • The app calls the primary adult account a "Parent account" — say so plainly, or a
#     student reads it as the wrong option and stops. It is the correct account for them.
#   • Eligibility is by birth YEAR, not birthday: born 2008 or earlier.
#   • Two real-world blockers that strand people mid-setup, so they are WARNINGS not asides:
#     the ID check rejects a photo of a photo (physical MyKad only), and a very old phone can
#     fail activation even above the stated iOS 16 / Android 10 floor.
#   • The attached guide tells them to WhatsApp Vircle. We do NOT contradict the attachment —
#     they may, but it is optional; what we need is the Action-Centre confirmation, and we
#     relay to Vircle ourselves.
#   • Owner's edit (2026-07-12): ALL support routes to help@ — the email no longer points at
#     Vircle's WhatsApp line, so a student in trouble comes to US and we hear about it. (Their
#     own support number is still in the attached guide, and on the Action-Centre card.)

VIRCLE_INSTALL_SUBJECTS = {
    'en': 'Set up your Vircle eWallet to receive your BrightPath Bursary 💳',
    'ms': 'Sediakan eWallet Vircle anda untuk menerima Bursari BrightPath 💳',
    'ta': 'உங்கள் BrightPath Bursary-ஐப் பெற Vircle eWallet-ஐ அமைக்கவும் 💳',
}
VIRCLE_INSTALL_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "We're ready to start paying your BrightPath Bursary. Your money will reach you through "
        "Vircle, a Malaysian eWallet app — so the next step is to set up your Vircle account.\n\n"
        "Install the Vircle app from the Apple App Store, Google Play Store or Huawei AppGallery. "
        "You'll need iOS 16 or above, or Android 10 or above. Note that a very old phone can fail "
        "during registration even if it meets this — if it stalls, try again on a newer phone.\n\n"
        "When you sign up, the app asks you to register a Parent account. That is simply Vircle's "
        "name for the main adult account, and it is the correct one for you. You can register if "
        "you were born in 2008 or earlier. Have your MyKad in your hand before you start: the app "
        "photographs the actual card, so a picture of a photocopy, a scan, or an image on another "
        "screen will be rejected.\n\n"
        "If you were born after 2008, you cannot open your own Vircle account yet. Ask a parent or "
        "guardian to register their own Vircle account instead, then email us at {support} and "
        "we'll arrange for you to be added to it.\n\n"
        "The step-by-step guide is attached to this email.\n\n"
        "Once your account is active, please tell us in the Action Centre: enter the mobile "
        "number you registered with Vircle AND your Vircle Wallet ID (have it ready — it's the "
        "long number on your Vircle account). We'll take it from there and arrange for your account "
        "to receive money monthly. (The attached guide asks you to message Vircle on WhatsApp — "
        "you may do so, but you don't have to. Telling us is what we need.)\n\n"
        "If you faced any trouble during registration or activation, reply to this email or "
        "contact us at {support}.\n\n"
        "Warm regards,\nThe BrightPath Bursary Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Kami sudah bersedia untuk mula membayar Bursari BrightPath anda. Wang anda akan sampai "
        "melalui Vircle, sebuah aplikasi eWallet Malaysia — jadi langkah seterusnya ialah menyediakan "
        "akaun Vircle anda.\n\n"
        "Pasang aplikasi Vircle dari Apple App Store, Google Play Store atau Huawei AppGallery. Anda "
        "memerlukan iOS 16 ke atas, atau Android 10 ke atas. Perlu diingat, telefon yang terlalu lama "
        "boleh gagal semasa pendaftaran walaupun memenuhi syarat ini — jika ia tersekat, cuba semula "
        "dengan telefon yang lebih baharu.\n\n"
        "Semasa mendaftar, aplikasi akan meminta anda mendaftar Akaun Parent. Itu hanyalah nama Vircle "
        "bagi akaun dewasa utama, dan ia adalah akaun yang betul untuk anda. Anda boleh mendaftar jika "
        "anda lahir pada tahun 2008 atau lebih awal. Pastikan MyKad anda ada di tangan sebelum mula: "
        "aplikasi akan memotret kad sebenar, jadi gambar salinan fotostat, imbasan, atau imej pada "
        "skrin lain akan ditolak.\n\n"
        "Jika anda lahir selepas tahun 2008, anda belum boleh membuka akaun Vircle anda sendiri. "
        "Sebaliknya, minta ibu bapa atau penjaga anda mendaftar akaun Vircle mereka sendiri, "
        "kemudian e-mel kami di {support} dan kami akan uruskan supaya anda ditambah ke dalam "
        "akaun tersebut.\n\n"
        "Panduan langkah demi langkah disertakan bersama e-mel ini.\n\n"
        "Sebaik sahaja akaun anda aktif, sila beritahu kami di Pusat Tindakan: masukkan nombor "
        "telefon bimbit yang anda daftarkan dengan Vircle DAN ID Dompet Vircle anda (sediakan ia "
        "— nombor panjang pada akaun Vircle anda). Kami akan uruskan yang selebihnya dan "
        "memastikan akaun anda menerima wang setiap bulan. (Panduan yang disertakan meminta anda "
        "menghantar mesej WhatsApp kepada Vircle — anda boleh berbuat demikian, tetapi ia tidak "
        "wajib. Memberitahu kami sudah memadai.)\n\n"
        "Jika anda menghadapi sebarang masalah semasa pendaftaran atau pengaktifan, balas e-mel ini "
        "atau hubungi kami di {support}.\n\n"
        "Salam hormat,\nPasukan Program Bursari BrightPath"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "உங்கள் BrightPath Bursary-ஐ வழங்கத் தொடங்க நாங்கள் தயாராக உள்ளோம். உங்கள் பணம் Vircle என்ற "
        "மலேசிய eWallet செயலி வழியாக உங்களைச் சென்றடையும் — எனவே அடுத்த படி உங்கள் Vircle கணக்கை "
        "அமைப்பதாகும்.\n\n"
        "Apple App Store, Google Play Store அல்லது Huawei AppGallery-இலிருந்து Vircle செயலியை "
        "நிறுவவும். உங்களுக்கு iOS 16 அல்லது அதற்கு மேல், அல்லது Android 10 அல்லது அதற்கு மேல் தேவை. "
        "மிகவும் பழைய தொலைபேசி இதைப் பூர்த்தி செய்தாலும் பதிவின்போது தோல்வியடையலாம் — நின்றுவிட்டால், "
        "புதிய தொலைபேசியில் மீண்டும் முயற்சிக்கவும்.\n\n"
        "பதிவு செய்யும்போது, ஒரு Parent கணக்கைப் பதிவு செய்யுமாறு செயலி கேட்கும். அது Vircle நிறுவனம் "
        "முதன்மை வயதுவந்தோர் கணக்கிற்கு வைத்துள்ள பெயர் மட்டுமே; அதுவே உங்களுக்கான சரியான கணக்கு. "
        "நீங்கள் 2008 அல்லது அதற்கு முன் பிறந்திருந்தால் பதிவு செய்யலாம். தொடங்கும் முன் உங்கள் MyKad-ஐ "
        "கையில் வைத்திருங்கள்: செயலி உண்மையான அட்டையைப் புகைப்படம் எடுக்கிறது, எனவே நகல், ஸ்கேன், அல்லது "
        "மற்றொரு திரையில் உள்ள படத்தின் புகைப்படம் நிராகரிக்கப்படும்.\n\n"
        "நீங்கள் 2008-க்குப் பிறகு பிறந்திருந்தால், உங்கள் சொந்தக் கணக்கை இப்போது திறக்க முடியாது. "
        "அதற்குப் பதிலாக, உங்கள் பெற்றோர் அல்லது பாதுகாவலரை அவர்களின் சொந்த Vircle கணக்கைப் பதிவு "
        "செய்யச் சொல்லுங்கள்; பிறகு {support} இல் எங்களுக்கு மின்னஞ்சல் அனுப்புங்கள் — அந்தக் கணக்கில் "
        "உங்களைச் சேர்ப்பதற்கு நாங்கள் ஏற்பாடு செய்வோம்.\n\n"
        "படிப்படியான வழிகாட்டி இந்த மின்னஞ்சலுடன் இணைக்கப்பட்டுள்ளது.\n\n"
        "உங்கள் கணக்கு செயல்பட்டவுடன், Action Centre-இல் எங்களிடம் தெரிவித்து, Vircle-இல் நீங்கள் "
        "பதிவு செய்த கைபேசி எண்ணையும் உங்கள் Vircle வாலட் ID-யையும் உள்ளிடவும் (அதைத் தயாராக "
        "வைத்திருங்கள் — உங்கள் Vircle கணக்கில் உள்ள நீண்ட எண்). மீதியை நாங்கள் கவனித்து, உங்கள் கணக்கு ஒவ்வொரு மாதமும் "
        "பணத்தைப் பெறுவதற்கு ஏற்பாடு செய்வோம். (இணைக்கப்பட்ட வழிகாட்டி Vircle-க்கு WhatsApp அனுப்பச் "
        "சொல்கிறது — நீங்கள் அனுப்பலாம், ஆனால் அது கட்டாயமில்லை. எங்களிடம் தெரிவிப்பதே எங்களுக்குத் "
        "தேவை.)\n\n"
        "பதிவு அல்லது செயல்படுத்தும் போது ஏதேனும் சிக்கல் ஏற்பட்டால், இந்த மின்னஞ்சலுக்குப் பதிலளிக்கவும் "
        "அல்லது {support} இல் எங்களைத் தொடர்புகொள்ளவும்.\n\n"
        "அன்புடன்,\nBrightPath Bursary குழு"
    ),
}

# Rendered BOLD in the HTML. Each MUST be an exact substring of its body above — a phrase that
# isn't found is silently left un-bolded (same contract as _BOLD_PHRASES).
_VIRCLE_BOLD_PHRASES = {
    'en': ['register a Parent account', 'born in 2008 or earlier',
           'photographs the actual card'],
    'ms': ['mendaftar Akaun Parent', 'lahir pada tahun 2008 atau lebih awal',
           'memotret kad sebenar'],
    'ta': ['Parent கணக்கைப் பதிவு செய்யுமாறு', '2008 அல்லது அதற்கு முன் பிறந்திருந்தால்',
           'உண்மையான அட்டையைப் புகைப்படம் எடுக்கிறது'],
}

# The Action Centre appears TWICE in the HTML, deliberately: as an inline link inside the sentence
# that asks for it, and again as a button under the sign-off. Both point at /scholarship/application.
# A student skim-reading finds the button; a student reading properly finds the link where the ask
# actually is. The plain-text fallback just reads the words, losing only the click.
_VIRCLE_LINK_PHRASES = {
    'en': 'the Action Centre',
    'ms': 'Pusat Tindakan',
    'ta': 'Action Centre-இல்',
}

VIRCLE_CTA_LABELS = {
    'en': 'Confirm in the Action Centre',
    'ms': 'Sahkan di Pusat Tindakan',
    'ta': 'Action Centre-இல் உறுதிப்படுத்தவும்',
}

# The installation guide, shipped as a repo asset (not PII → safe in git).
_VIRCLE_GUIDE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'assets', 'vircle-installation-guide.pdf',
)
_VIRCLE_GUIDE_FILENAME = 'BrightPath Bursary eWallet by Vircle - Installation Guide.pdf'


def vircle_guide_attachment():
    """The installation guide as a ``(filename, content, mimetype)`` triple, or None.

    Source of truth is the LIVE copy in the owner's Drive (``VIRCLE_GUIDE_FOLDER``) so an edit to
    the guide reflects in the next award email without a redeploy; the fetched bytes are cached
    briefly (``VIRCLE_GUIDE_CACHE_SECONDS``) so a batch send doesn't re-download per email. Falls
    back to the bundled repo asset when Drive is disabled/unreachable — a slightly-stale guide
    beats no guide, and no attachment still beats no email at all."""
    filename = getattr(settings, 'VIRCLE_GUIDE_FILENAME', '') or _VIRCLE_GUIDE_FILENAME
    content = _vircle_guide_bytes_from_drive() or _vircle_guide_bytes_from_asset()
    if content is None:
        return None
    return (filename, content, 'application/pdf')


def _vircle_guide_bytes_from_drive():
    """The live guide bytes from Drive, cached for ``VIRCLE_GUIDE_CACHE_SECONDS``. None when the
    folder is unset, Drive is disabled, or the fetch fails (all handled in ``sheets``)."""
    folder = getattr(settings, 'VIRCLE_GUIDE_FOLDER', '')
    if not folder:
        return None
    filename = getattr(settings, 'VIRCLE_GUIDE_FILENAME', '') or _VIRCLE_GUIDE_FILENAME
    ttl = int(getattr(settings, 'VIRCLE_GUIDE_CACHE_SECONDS', 0) or 0)
    # Hash the folder+filename into the key so it's cache-backend-safe (no spaces/slashes) and a
    # config change naturally lands on a fresh key instead of serving a stale cached copy.
    import hashlib
    digest = hashlib.sha1(f'{folder}\n{filename}'.encode('utf-8')).hexdigest()
    cache_key = f'vircle_guide_pdf:{digest}'
    if ttl > 0:
        from django.core.cache import cache
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    from . import sheets
    content = sheets.fetch_drive_pdf(folder, filename)
    if content and ttl > 0:
        from django.core.cache import cache
        cache.set(cache_key, content, ttl)
    return content


def _vircle_guide_bytes_from_asset():
    """The bundled repo copy — the fallback when Drive is unavailable."""
    try:
        with open(_VIRCLE_GUIDE_PATH, 'rb') as fh:
            return fh.read()
    except OSError:
        logger.warning('Vircle installation guide missing at %s', _VIRCLE_GUIDE_PATH)
        return None


def _vircle_install_html(text_body, lang):
    """HTML for the Vircle setup email: paragraphs, key phrases BOLD, the sign-off team name
    bolded, "the Action Centre" as an inline LINK where the ask is made, AND a call-to-action
    button under the sign-off. Both routes lead to /scholarship/application."""
    import html as _h
    frontend = _P.frontend_url
    link_phrase = _VIRCLE_LINK_PHRASES.get(lang, _VIRCLE_LINK_PHRASES['en'])
    phrases = _VIRCLE_BOLD_PHRASES.get(lang, [])

    def _emphasise(escaped):
        for ph in phrases:
            if ph:
                escaped = escaped.replace(_h.escape(ph), f'<strong>{_h.escape(ph)}</strong>')
        # Link the Action Centre in place. Bolded too — it is the one thing we're asking for.
        if link_phrase:
            esc_link = _h.escape(link_phrase)
            anchor = (f'<a href="{frontend}/scholarship/application" '
                      f'style="color:#2563eb;font-weight:600;">{esc_link}</a>')
            escaped = escaped.replace(esc_link, anchor, 1)
        return escaped

    paras = [p.strip() for p in (text_body or '').split('\n\n') if p.strip()]
    blocks = []
    for idx, para in enumerate(paras):
        esc = _emphasise(_h.escape(para))
        if idx == len(paras) - 1 and '\n' in para:   # final paragraph = the sign-off
            head, sep, team = esc.rpartition('\n')
            esc = f'{head}\n<strong>{team}</strong>' if sep else f'<strong>{esc}</strong>'
        blocks.append(f'<p style="margin:0 0 14px;">{esc.replace(chr(10), "<br>")}</p>')

    button = _email_button(f'{frontend}/scholarship/application',
                           VIRCLE_CTA_LABELS.get(lang, VIRCLE_CTA_LABELS['en']))
    blocks.append(f'<p style="margin:22px 0 6px;">{button}</p>')
    return _html_email_shell(''.join(blocks))


def send_vircle_install_email(to_email, applicant_name, lang='en'):
    """Vircle setup email: install the app, then confirm in the Action Centre. The installation
    guide PDF is attached. HTML (key phrases BOLD + one CTA button) + plain-text fallback, from
    info@, reply-to help@."""
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    fmt = {'name': name, 'support': _P.email_support}
    subject = VIRCLE_INSTALL_SUBJECTS[lang]
    text_body = VIRCLE_INSTALL_BODIES[lang].format(**fmt)
    guide = vircle_guide_attachment()
    return _send_html(
        to_email, subject, text_body, _vircle_install_html(text_body, lang),
        from_email=_P.email_from,
        reply_to=[_P.email_support],
        attachments=[guide] if guide else None,
    )


# ── Bursary signing chain (BURSARY_AGREEMENT_ENABLED) ─────────────────────────
# Two student-facing trilingual emails (the "now sign" follow-up + the executed
# confirmation) + two internal English notifications (partner witness-pending +
# Foundation countersign-pending). No donor is ever named in any of them.

SIGN_INVITE_SUBJECTS = {
    'en': 'Your BrightPath Bursary agreement is ready to sign ✍️',
    'ms': 'Perjanjian Bursari BrightPath anda sedia untuk ditandatangani ✍️',
    'ta': 'உங்கள் BrightPath Bursary ஒப்பந்தம் கையொப்பமிடத் தயாராக உள்ளது ✍️',
}
SIGN_INVITE_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "The next step in your bursary is ready: your bursary agreement. Please log in and "
        "open your Action Centre, where you'll first go through a short, friendly check to "
        "make sure the terms are clear, and then sign the agreement together with your parent "
        "or guardian — all on the same device.\n{link}\n\n"
        "Please have your parent or guardian with you when you sign: they sign as your "
        "guarantor, and we'll send a one-time PIN to their phone to confirm it's them.\n\n"
        "If you have any questions, reply to this email or contact us at {support}.\n\n"
        "Warm wishes,\nThe BrightPath Bursary Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Langkah seterusnya dalam biasiswa anda sudah sedia: perjanjian biasiswa anda. Sila "
        "log masuk dan buka Pusat Tindakan anda. Anda akan melalui semakan ringkas dan mesra "
        "dahulu untuk memastikan terma jelas, kemudian menandatangani perjanjian bersama ibu "
        "bapa atau penjaga anda — semuanya pada peranti yang sama.\n{link}\n\n"
        "Sila pastikan ibu bapa atau penjaga anda bersama anda semasa menandatangani: mereka "
        "menandatangani sebagai penjamin anda, dan kami akan menghantar PIN sekali guna ke "
        "telefon mereka untuk mengesahkannya.\n\n"
        "Jika ada sebarang pertanyaan, balas e-mel ini atau hubungi kami di {support}.\n\n"
        "Salam mesra,\nPasukan Program Bursari BrightPath"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "உங்கள் உதவித்தொகையின் அடுத்த படி தயாராக உள்ளது: உங்கள் உதவித்தொகை ஒப்பந்தம். உள்நுழைந்து "
        "உங்கள் செயல் மையத்தைத் (Action Centre) திறக்கவும். முதலில் விதிமுறைகள் தெளிவாக இருப்பதை "
        "உறுதிசெய்ய ஒரு சிறிய, நட்பான சரிபார்ப்பின் வழியாகச் செல்வீர்கள், பின்னர் உங்கள் பெற்றோர் "
        "அல்லது பாதுகாவலருடன் சேர்ந்து — ஒரே சாதனத்தில் — ஒப்பந்தத்தில் கையொப்பமிடுவீர்கள்.\n{link}\n\n"
        "கையொப்பமிடும்போது உங்கள் பெற்றோர் அல்லது பாதுகாவலர் உங்களுடன் இருப்பதை உறுதிசெய்யவும்: "
        "அவர்கள் உங்கள் பிணையாளராகக் கையொப்பமிடுகிறார்கள், அவர்கள்தான் என்பதை உறுதிப்படுத்த அவர்களின் "
        "தொலைபேசிக்கு ஒரு முறை PIN அனுப்புவோம்.\n\n"
        "ஏதேனும் கேள்விகள் இருந்தால், இந்த மின்னஞ்சலுக்குப் பதிலளிக்கவும் அல்லது {support} இல் "
        "எங்களைத் தொடர்புகொள்ளவும்.\n\n"
        "அன்புடன்,\nBrightPath Bursary குழு"
    ),
}


def send_sign_invitation_email(to_email, applicant_name, lang='en'):
    """The follow-up "your agreement is ready to sign" email (owner-sent, after the
    bank-details email). Points to /scholarship/application → Action Centre → the
    comprehension quiz → signing. NO amount, NO sponsor identity. Plain text + info@."""
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    return _send(to_email, SIGN_INVITE_SUBJECTS, SIGN_INVITE_BODIES, name, '', lang,
                 extra={'support': _P.email_support})


AGREEMENT_EXECUTED_SUBJECTS = {
    'en': 'Your BrightPath Bursary agreement is now in effect 🎓',
    'ms': 'Perjanjian Bursari BrightPath anda kini berkuat kuasa 🎓',
    'ta': 'உங்கள் BrightPath Bursary ஒப்பந்தம் இப்போது அமலுக்கு வந்துள்ளது 🎓',
}
AGREEMENT_EXECUTED_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "Good news — your bursary agreement is now fully signed and in effect. Everyone who "
        "needed to sign has done so, and your bursary is confirmed.\n\n"
        "You can view your application and your signed agreement here:\n{link}\n\n"
        "We'll be in touch with the next steps. If you have any questions, reply to this email "
        "or contact us at {support}.\n\n"
        "Warm congratulations,\nThe BrightPath Bursary Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Berita baik — perjanjian biasiswa anda kini ditandatangani sepenuhnya dan berkuat "
        "kuasa. Semua pihak yang perlu menandatangani telah berbuat demikian, dan biasiswa anda "
        "telah disahkan.\n\n"
        "Anda boleh melihat permohonan dan perjanjian anda yang ditandatangani di sini:\n{link}\n\n"
        "Kami akan menghubungi anda dengan langkah seterusnya. Jika ada sebarang pertanyaan, "
        "balas e-mel ini atau hubungi kami di {support}.\n\n"
        "Tahniah,\nPasukan Program Bursari BrightPath"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "நல்ல செய்தி — உங்கள் உதவித்தொகை ஒப்பந்தம் இப்போது முழுமையாகக் கையொப்பமிடப்பட்டு அமலுக்கு "
        "வந்துள்ளது. கையொப்பமிட வேண்டிய அனைவரும் கையொப்பமிட்டுவிட்டனர், உங்கள் உதவித்தொகை "
        "உறுதிப்படுத்தப்பட்டுள்ளது.\n\n"
        "உங்கள் விண்ணப்பத்தையும் கையொப்பமிடப்பட்ட ஒப்பந்தத்தையும் இங்கே காணலாம்:\n{link}\n\n"
        "அடுத்த படிகளுடன் நாங்கள் உங்களைத் தொடர்புகொள்வோம். ஏதேனும் கேள்விகள் இருந்தால், இந்த "
        "மின்னஞ்சலுக்குப் பதிலளிக்கவும் அல்லது {support} இல் எங்களைத் தொடர்புகொள்ளவும்.\n\n"
        "இதயப்பூர்வ வாழ்த்துகள்,\nBrightPath Bursary குழு"
    ),
}


def send_agreement_executed_email(to_email, applicant_name, programme_name='', lang='en',
                                  link='', pdf=None):
    """Sent when the bursary agreement is fully executed (student + guarantor + Foundation
    signed → application 'active'). Confirms the bursary is in effect. NO sponsor identity.
    From info@. When ``pdf`` (the signed-agreement bytes) is given, it is ATTACHED and the
    mail goes HTML via ``_send_html``; otherwise the plain ``_send`` path (backward-compat)."""
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    if pdf is None:
        return _send(to_email, AGREEMENT_EXECUTED_SUBJECTS, AGREEMENT_EXECUTED_BODIES,
                     name, programme_name, lang, extra={'support': _P.email_support})
    subject = AGREEMENT_EXECUTED_SUBJECTS[lang]
    text = AGREEMENT_EXECUTED_BODIES[lang].format(name=name, link=link or '', support=_P.email_support)
    html = _html_email_shell('<p style="margin:0 0 14px;">'
                             + text.replace('\n\n', '</p><p style="margin:0 0 14px;">').replace('\n', '<br>')
                             + '</p>')
    return _send_html(
        to_email, subject, text, html,
        from_email=_P.email_from,
        reply_to=[_P.email_support],
        attachments=[('bursary_agreement.pdf', pdf, 'application/pdf')])


def send_executed_copy_email(to_email, *, applicant_name='', programme_name='', pdf=None, link=''):
    """A copy of a fully-executed bursary agreement, for the witnessing partner contact and
    the org admins (Sprint 5 distribution). Internal (English); the signed PDF attached when
    available. From info@, reply-to help@. Best-effort → bool. Donor never named."""
    if not to_email:
        return False
    who = applicant_name or 'a student'
    subject = f'Executed bursary agreement — {who}'
    text = (f"Hello,\n\nThe bursary agreement for {who} is now fully signed and in effect. "
            f"A copy of the signed agreement is attached for your records.\n\n"
            + (f"View the application:\n{link}\n\n" if link else "")
            + "The BrightPath Bursary Team")
    html = _html_email_shell(
        '<p style="margin:0 0 14px;">Hello,</p>'
        f'<p style="margin:0 0 14px;">The bursary agreement for <strong>{who}</strong> is now '
        'fully signed and in effect. A copy of the signed agreement is attached for your records.</p>'
        + (f'<p style="margin:0 0 6px;">{_email_button(link, "Open the application")}</p>' if link else '')
        + '<p style="margin:18px 0 0;">The BrightPath Bursary Team</p>')
    attachments = [('bursary_agreement.pdf', pdf, 'application/pdf')] if pdf else None
    return _send_html(
        to_email, subject, text, html,
        from_email=_P.email_from,
        reply_to=[_P.email_support], attachments=attachments)


def send_witness_pending_email(to_email, *, contact_person='', applicant_name='',
                               org_name='', link=''):
    """Internal (English) nudge to the referring partner organisation: a bursary agreement
    for a student they referred is awaiting their WITNESS signature. Best-effort. The donor
    is never named; the partner already knows the student (they referred them)."""
    if not to_email:
        return False
    greeting = f'Dear {contact_person},' if contact_person else 'Hello,'
    who = f'<strong>{applicant_name}</strong>' if applicant_name else 'a student you referred'
    text = (
        f"{greeting}\n\n"
        f"A BrightPath Bursary agreement for {applicant_name or 'a student you referred'} is "
        f"ready for your organisation's witness signature. The student and their parent/guardian "
        f"have signed; you are recorded as the witnessing partner.\n\n"
        f"Please log in to the partner console to review and add your witness signature:\n{link}\n\n"
        f"Thank you,\nThe BrightPath Bursary Team"
    )
    html = _html_email_shell(
        f'<p style="margin:0 0 14px;">{greeting}</p>'
        f'<p style="margin:0 0 14px;">A BrightPath Bursary agreement for {who} is ready for '
        f'your organisation’s <strong>witness signature</strong>. The student and their '
        f'parent or guardian have signed; you are recorded as the witnessing partner'
        f'{(" for " + org_name) if org_name else ""}.</p>'
        f'<p style="margin:0 0 18px;">Please log in to the partner console to review and add '
        f'your witness signature.</p>'
        f'<p style="margin:0 0 6px;">{_email_button(link, "Open the partner console")}</p>'
        f'<p style="margin:18px 0 0;">Thank you,<br><strong>The BrightPath Bursary Team</strong></p>'
    )
    return _send_html(
        to_email, 'A bursary agreement is awaiting your witness signature', text, html,
        from_email=_P.email_from,
        reply_to=[_P.email_support],
    )


def send_countersign_pending_email(to_email, *, applicant_name='', link=''):
    """Internal (English) nudge to the Foundation officer / super admins: a bursary agreement
    is awaiting the Foundation's COUNTERSIGNATURE (the binding, final signature that activates
    the bursary). Best-effort. No donor named."""
    if not to_email:
        return False
    who = f'<strong>{applicant_name}</strong>' if applicant_name else 'a student'
    text = (
        "Hello,\n\n"
        f"A BrightPath Bursary agreement for {applicant_name or 'a student'} is awaiting the "
        f"Foundation's countersignature. The student, their guarantor"
        f"{' and the witnessing partner' if link else ''} have signed; the Foundation's "
        f"signature is the final, binding step that activates the bursary.\n\n"
        f"Please log in to the console to review and countersign:\n{link}\n\n"
        f"Thank you,\nThe BrightPath Bursary Team"
    )
    html = _html_email_shell(
        f'<p style="margin:0 0 14px;">Hello,</p>'
        f'<p style="margin:0 0 14px;">A BrightPath Bursary agreement for {who} is awaiting the '
        f'<strong>Foundation’s countersignature</strong> — the final, binding step '
        f'that activates the bursary.</p>'
        f'<p style="margin:0 0 6px;">{_email_button(link, "Open the console")}</p>'
        f'<p style="margin:18px 0 0;">Thank you,<br><strong>The BrightPath Bursary Team</strong></p>'
    )
    return _send_html(
        to_email, 'A bursary agreement is awaiting the Foundation countersignature', text, html,
        from_email=_P.email_from,
        reply_to=[_P.email_support],
    )


# ── F3: sponsor notifications (real-time alert + weekly digest) ───────────────
# Reworked to branded mini-card emails (HTML + plain-text pair) carrying the pool-card
# DNA. The body is built ONLY from already-serialised SponsorPoolDetailSerializer dicts
# (an allowlist) + the public FieldTaxonomy display names/artwork (non-identifying), so it
# can never contain a student's identity by construction. n-aware subjects (no "student(s)")
# with a standout hook; a per-student "Read their story" link; the sponsor's name in the
# greeting when the caller has it. NO '—' placeholders and NO empty lines — a missing fact
# is simply omitted.
FIELD_IMAGE_BASE = 'https://pbrrlyoyyiftckqvzvvo.supabase.co/storage/v1/object/public/field-images'
# Bright flat-illustration alternative set (no people/faces/text), used for the email
# THUMBNAIL — a photo cropped to 56px reads poorly. Same slug filenames, separate public
# bucket. (The sponsor detail-page strip uses the same set via the web `conceptFieldImageUrl`.)
FIELD_IMAGE_CONCEPT_BASE = 'https://pbrrlyoyyiftckqvzvvo.supabase.co/storage/v1/object/public/field-images-concept'

SPONSOR_NEW_SUBJECTS = {
    'en': {'one': 'A new student is waiting for a sponsor',
           'many': '{n} new students are waiting for a sponsor'},
    'ms': {'one': 'Seorang pelajar baharu menunggu penaja',
           'many': '{n} pelajar baharu menunggu penaja'},
    'ta': {'one': 'ஒரு புதிய மாணவர் நிதியுதவியாளருக்காகக் காத்திருக்கிறார்',
           'many': '{n} புதிய மாணவர்கள் நிதியுதவியாளருக்காகக் காத்திருக்கிறார்கள்'},
}
SPONSOR_DIGEST_SUBJECTS = {
    'en': {'one': 'Your weekly update: a student is waiting for a sponsor',
           'many': 'Your weekly update: {n} students waiting for a sponsor'},
    'ms': {'one': 'Kemas kini mingguan: seorang pelajar menunggu penaja',
           'many': 'Kemas kini mingguan: {n} pelajar menunggu penaja'},
    'ta': {'one': 'வாராந்திர புதுப்பிப்பு: ஒரு மாணவர் நிதியுதவியாளருக்காகக் காத்திருக்கிறார்',
           'many': 'வாராந்திர புதுப்பிப்பு: {n} மாணவர்கள் நிதியுதவியாளருக்காகக் காத்திருக்கிறார்கள்'},
}
# Standout hook appended to the subject when the best-academic card also has a state.
_SPONSOR_HOOK = {
    'en': ' — including {acad} from {state}',
    'ms': ' — termasuk {acad} dari {state}',
    'ta': ' — {state} மாநிலத்தைச் சேர்ந்த {acad} உட்பட',
}
_SPONSOR_GREETING = {'en': 'Dear {name},', 'ms': 'Salam {name},', 'ta': 'அன்புள்ள {name},'}
_SPONSOR_GREETING_GENERIC = {'en': 'Dear Sponsor,', 'ms': 'Salam Penaja,', 'ta': 'அன்புள்ள நிதியுதவியாளரே,'}
_SPONSOR_NEW_INTRO = {
    'en': {'one': 'A student is now ready for a sponsor — a young person from a low-income family who has done well despite the odds:',
           'many': 'More students are now ready for a sponsor — young people from low-income families who have done well despite the odds:'},
    'ms': {'one': 'Seorang pelajar kini bersedia untuk penaja — anak muda daripada keluarga berpendapatan rendah yang berjaya walaupun mencabar:',
           'many': 'Beberapa pelajar kini bersedia untuk penaja — anak muda daripada keluarga berpendapatan rendah yang berjaya walaupun mencabar:'},
    'ta': {'one': 'ஒரு மாணவர் இப்போது நிதியுதவியாளருக்குத் தயாராக உள்ளார் — சவால்களுக்கு மத்தியிலும் சிறந்து விளங்கிய, குறைந்த வருமானக் குடும்பத்தைச் சேர்ந்த ஓர் இளையவர்:',
           'many': 'சில மாணவர்கள் இப்போது நிதியுதவியாளருக்குத் தயாராக உள்ளனர் — சவால்களுக்கு மத்தியிலும் சிறந்து விளங்கிய, குறைந்த வருமானக் குடும்பங்களைச் சேர்ந்த இளையவர்கள்:'},
}
_SPONSOR_DIGEST_INTRO = {
    'en': {'one': 'Here is a student who has done well despite the odds — from a low-income family, and waiting for a sponsor to help them go further:',
           'many': 'Here are students who have done well despite the odds — each from a low-income family, and waiting for a sponsor to help them go further:'},
    'ms': {'one': 'Berikut seorang pelajar yang berjaya walaupun mencabar — daripada keluarga berpendapatan rendah, dan menunggu penaja untuk melangkah lebih jauh:',
           'many': 'Berikut pelajar yang berjaya walaupun mencabar — masing-masing daripada keluarga berpendapatan rendah, dan menunggu penaja untuk melangkah lebih jauh:'},
    'ta': {'one': 'சவால்களுக்கு மத்தியிலும் சிறந்து விளங்கிய ஒரு மாணவர் இங்கே — குறைந்த வருமானக் குடும்பத்தைச் சேர்ந்தவர், மேலும் முன்னேற நிதியுதவியாளருக்காகக் காத்திருக்கிறார்:',
           'many': 'சவால்களுக்கு மத்தியிலும் சிறந்து விளங்கிய மாணவர்கள் இங்கே — ஒவ்வொருவரும் குறைந்த வருமானக் குடும்பத்தைச் சேர்ந்தவர்கள், மேலும் முன்னேற நிதியுதவியாளருக்காகக் காத்திருக்கின்றனர்:'},
}
_SPONSOR_CTA = {'en': 'See all students', 'ms': 'Lihat semua pelajar', 'ta': 'அனைத்து மாணவர்களையும் காண்க'}
_SPONSOR_READ_STORY = {'en': 'Read their story →', 'ms': 'Baca kisah mereka →', 'ta': 'அவர்களின் கதையைப் படிக்க →'}
_SPONSOR_REGISTERS = {'en': 'registers {date}', 'ms': 'mendaftar {date}', 'ta': '{date} அன்று பதிவு'}
_SPONSOR_FOOTER = {
    'en': "You're receiving this because your notifications are set to {freq}. You can change this any time in your {account}.",
    'ms': "Anda menerima ini kerana pemberitahuan anda ditetapkan kepada {freq}. Anda boleh menukarnya bila-bila masa dalam {account} anda.",
    'ta': "உங்கள் அறிவிப்புகள் {freq} என அமைக்கப்பட்டுள்ளதால் இதைப் பெறுகிறீர்கள். எப்போது வேண்டுமானாலும் உங்கள் {account} இல் இதை மாற்றலாம்.",
}
_SPONSOR_ACCOUNT = {'en': 'sponsor account', 'ms': 'akaun penaja', 'ta': 'நிதியுதவியாளர் கணக்கு'}
_SPONSOR_SIGNOFF = {
    'en': 'Warm regards,\nThe BrightPath Bursary Team',
    'ms': 'Salam hormat,\nPasukan Program Bursari BrightPath',
    'ta': 'அன்புடன்,\nBrightPath Bursary குழு',
}
_SPONSOR_FREQ_WORD = {
    'realtime': {'en': 'real-time', 'ms': 'masa nyata', 'ta': 'நிகழ்நேரம்'},
    'weekly': {'en': 'weekly', 'ms': 'mingguan', 'ta': 'வாராந்திரம்'},
}


def _field_image_url(slug):
    """Public field-artwork URL from a slug — '' (omit the <img>) when the slug is empty.
    Uses the concept (illustration) set, which crops cleanly at thumbnail size."""
    slug = (slug or '').strip()
    return f'{FIELD_IMAGE_CONCEPT_BASE}/{slug}.png' if slug else ''


def _tax_name_map():
    """{taxonomy_key: {en,ms,ta}} — for turning a raw field key into a display name.
    Non-identifying (catalogue names shared by hundreds of courses); one query per send."""
    from apps.courses.models import FieldTaxonomy
    return {k: {'en': en, 'ms': ms, 'ta': ta}
            for k, en, ms, ta in FieldTaxonomy.objects.values_list(
                'key', 'name_en', 'name_ms', 'name_ta')}


def _programme_of(card, lang, tax):
    """The bold programme line: the confirmed course name, else the field's taxonomy
    DISPLAY name — NEVER a raw field key, NEVER '—'. '' when nothing is known (line omitted)."""
    prog = (card.get('course') or '').strip()
    if prog:
        return (tax[prog][lang] or prog) if prog in tax else prog
    field = (card.get('field') or '').strip()
    if not field:
        return ''
    return (tax.get(field, {}).get(lang) or field)


def _registers_line(card, lang):
    """'registers DD/MM/YYYY' when the course-start date is today/future; else ''."""
    iso = card.get('reporting_date')
    if not iso:
        return ''
    from datetime import date
    from django.utils import timezone
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ''
    if d < timezone.localdate():
        return ''
    return _SPONSOR_REGISTERS[lang].format(date=d.strftime('%d/%m/%Y'))


def _rm_whole(v):
    """Whole-ringgit, thousands-grouped, no decimals — "2000.00" → "2,000" (mirrors the web
    card's rmWhole)."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return str(v or '')
    return f'{int(round(n)):,}'


def _facts_bits(card, lang):
    """academic · RMamount · registers <date> — only the parts present (no '—')."""
    bits = []
    if (card.get('academic') or '').strip():
        bits.append(card['academic'].strip())
    amt = card.get('award_amount')
    if amt:
        bits.append(f'RM{_rm_whole(amt)}')          # RM2,000 (matches the web card)
    reg = _registers_line(card, lang)
    if reg:
        bits.append(reg)
    return bits


def _acad_score(academic):
    """A rough 'best academic' score for the subject hook, off pool.academic_band's format
    ('SPM · N As' / 'STPM · PNGK X.X'): the SPM A-count, or an STPM CGPA magnitude — whichever
    is larger. Subject flavour only, never load-bearing."""
    import re
    a = (academic or '').upper()
    counts = [int(m) for m in re.findall(r'(\d+)\s*A', a)]   # "7 As" / "9A" → 7 / 9
    score = float(max(counts)) if counts else float(a.count('A'))
    m = re.search(r'(\d\.\d+)', a)                            # STPM "PNGK 3.5" → 3.5
    if m:
        score = max(score, float(m.group(1)))
    return score


def _pick_standout(cards):
    best, best_score = None, -1.0
    for c in cards:
        s = _acad_score(c.get('academic', ''))
        if s > best_score:
            best, best_score = c, s
    return best


def _sponsor_subject(subjects, cards, lang, count=None):
    # ``count`` is the FULL number of students this email is about (the subject reflects the
    # whole batch even when the body is capped); the standout hook is drawn from the shown cards.
    n = count if count is not None else len(cards)
    subject = subjects[lang]['one' if n == 1 else 'many'].format(n=n)
    st = _pick_standout(cards)
    if st and (st.get('academic') or '').strip() and (st.get('state') or '').strip():
        subject += _SPONSOR_HOOK[lang].format(acad=st['academic'].strip(), state=st['state'].strip())
    return subject


def _sponsor_card_text(card, lang, frontend, tax):
    """Plain-text mini-card — mirrors the HTML content (never regresses below the old text)."""
    ref = card.get('ref', '')
    prog = _programme_of(card, lang, tax)
    lines = [ref]
    if prog:
        lines.append(prog)
    # Institution only — the home state next to it misleads (matches the web card).
    inst = (card.get('institution') or '').strip()
    if inst:
        lines.append(inst)
    facts = _facts_bits(card, lang)
    if facts:
        lines.append(' · '.join(facts))
    blurb = (card.get('blurb') or '').strip()
    if blurb:
        lines.append(f'"{blurb}"')
    lines.append(f'{_SPONSOR_READ_STORY[lang]} {frontend}/sponsor/students/{card.get("id", "")}')
    return '\n'.join(lines)


def _sponsor_card_html(card, lang, frontend, tax):
    """One email-safe mini-card (table markup, shell-consistent). Thumbnail omitted when
    the field artwork slug is empty; every fact line is dropped when absent (no '—')."""
    import html as _h
    ref = _h.escape(card.get('ref', ''))
    prog = _h.escape(_programme_of(card, lang, tax))
    loc = _h.escape((card.get('institution') or '').strip())   # institution only (no state)
    facts = _h.escape(' · '.join(_facts_bits(card, lang)))
    blurb = (card.get('blurb') or '').strip()
    url = f'{frontend}/sponsor/students/{card.get("id", "")}'
    img = _field_image_url(card.get('field_image_slug', ''))
    thumb = (f'<td width="64" valign="top" style="padding-right:12px;">'
             f'<img src="{img}" width="56" height="56" alt="{prog or "Field"}" '
             f'style="width:56px;height:56px;border-radius:8px;object-fit:cover;display:block;"></td>') if img else ''
    prog_html = f'<div style="margin:6px 0 0;font-weight:700;color:#111827;">{prog}</div>' if prog else ''
    loc_html = f'<div style="color:#6b7280;font-size:13px;">{loc}</div>' if loc else ''
    facts_html = f'<div style="margin-top:4px;font-size:13px;color:#374151;">{facts}</div>' if facts else ''
    blurb_html = (f'<div style="margin:6px 0 0;color:#4b5563;font-style:italic;">{_h.escape(blurb)}</div>'
                  if blurb else '')
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;'
        'border-radius:12px;margin:0 0 12px;"><tr><td style="padding:14px;">'
        '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'{thumb}<td valign="top">'
        f'<div style="display:inline-block;background:#eef2ff;color:#3730a3;font-size:11px;'
        f'font-weight:700;padding:2px 8px;border-radius:999px;">{ref}</div>'
        f'{prog_html}{loc_html}{facts_html}{blurb_html}'
        f'<div style="margin-top:8px;"><a href="{url}" style="color:#2563eb;text-decoration:none;'
        f'font-weight:600;font-size:13px;">{_SPONSOR_READ_STORY[lang]}</a></div>'
        '</td></tr></table></td></tr></table>'
    )


def _sponsor_email_max_cards():
    """A notification email shows at most this many students (a teaser — the 'See all
    students' button leads to the full pool). Owner 2026-07-18: keep it to 5."""
    return int(getattr(settings, 'SPONSOR_EMAIL_MAX_CARDS', 5) or 5)


def _send_sponsor_notify(to_email, subjects, cards, freq, lang, intro_map, name=''):
    if not to_email or not cards:
        return False
    import html as _h
    lang = normalise_lang(lang)
    frontend = _P.frontend_url
    freq_word = _SPONSOR_FREQ_WORD.get(freq, {}).get(lang, freq)
    tax = _tax_name_map()
    all_cards = list(cards)
    full_n = len(all_cards)                            # the whole batch — drives the subject/intro count
    cards = all_cards[:_sponsor_email_max_cards()]     # cap the BODY to 5; the button shows the rest
    greeting = (_SPONSOR_GREETING[lang].format(name=name.strip())
                if (name or '').strip() else _SPONSOR_GREETING_GENERIC[lang])
    intro = intro_map[lang]['one' if full_n == 1 else 'many']
    subject = _sponsor_subject(subjects, cards, lang, count=full_n)
    signoff = _SPONSOR_SIGNOFF[lang]
    cta_url = f'{frontend}/sponsor/students'          # the pool itself, not the portal landing
    account_url = f'{frontend}/sponsor/account'

    # Footer: 'sponsor account' is a link in HTML, a bare URL in plain text.
    account = _SPONSOR_ACCOUNT[lang]
    footer_text = _SPONSOR_FOOTER[lang].format(freq=freq_word, account=f'{account} ({account_url})')
    footer_html = _h.escape(_SPONSOR_FOOTER[lang]).format(
        freq=_h.escape(freq_word),
        account=f'<a href="{account_url}" style="color:#2563eb;">{_h.escape(account)}</a>')

    text_cards = '\n\n'.join(_sponsor_card_text(c, lang, frontend, tax) for c in cards)
    text_body = (f'{greeting}\n\n{intro}\n\n{text_cards}\n\n'
                 f'{_SPONSOR_CTA[lang]}: {cta_url}\n\n{footer_text}\n\n{signoff}')

    html_cards = ''.join(_sponsor_card_html(c, lang, frontend, tax) for c in cards)
    html_body = _html_email_shell(
        f'<p style="margin:0 0 12px;">{_h.escape(greeting)}</p>'
        f'<p style="margin:0 0 16px;">{_h.escape(intro)}</p>'
        + html_cards +
        f'<p style="margin:18px 0 0;">{_email_button(cta_url, _SPONSOR_CTA[lang])}</p>'
        f'<p style="margin:18px 0 0;color:#6b7280;font-size:12px;">{footer_html}</p>'
        f'<p style="margin:12px 0 0;color:#6b7280;font-size:12px;">'
        f'{_h.escape(signoff).replace(chr(10), "<br>")}</p>'
    )
    return _send_html(
        to_email, subject, text_body, html_body,
        from_email=_P.email_from,
        reply_to=[_P.sponsor_reply_to],
    )


def send_sponsor_new_student_email(to_email, cards, lang='en', name=''):
    """F3 real-time: alert a sponsor that newly-published student(s) are waiting.
    ``cards`` = a list of SponsorPoolDetailSerializer dicts (allowlist-safe)."""
    return _send_sponsor_notify(to_email, SPONSOR_NEW_SUBJECTS, cards, 'realtime', lang,
                                _SPONSOR_NEW_INTRO, name=name)


def send_sponsor_digest_email(to_email, cards, lang='en', name=''):
    """F3 weekly: a digest of students published since the sponsor's last digest.
    ``cards`` = a list of SponsorPoolDetailSerializer dicts (allowlist-safe)."""
    return _send_sponsor_notify(to_email, SPONSOR_DIGEST_SUBJECTS, cards, 'weekly', lang,
                                _SPONSOR_DIGEST_INTRO, name=name)


def _decline_html(text_body):
    """Render a plain-text decline body as a branded HTML card: blank-line-separated
    paragraphs become <p>, single newlines (the sign-off) become <br>. Escaped. The
    sign-off team name (the line after the salutation in the final paragraph) is bolded
    in the HTML only — the plain-text fallback stays clean."""
    import html as _h
    paras = [p.strip() for p in (text_body or '').split('\n\n') if p.strip()]
    blocks = []
    for i, p in enumerate(paras):
        esc = _h.escape(p)
        # Final paragraph + a salutation/team split → bold the team-name line.
        if i == len(paras) - 1 and '\n' in p:
            head, _sep, team = esc.rpartition('\n')
            esc = '%s\n<strong>%s</strong>' % (head, team)
        blocks.append('<p style="margin:0 0 14px;">%s</p>' % esc.replace('\n', '<br>'))
    return _html_email_shell(''.join(blocks))


def send_decline_email(to_email, applicant_name, programme_name, category='', lang='en'):
    """Send the right decline email for a rejection bucket, as HTML (branded, warm) with a
    plain-text fallback — From info@, reply-to help@. merit/need/interview get bucket-specific
    copy (the interview bucket thanks the student for their time and for submitting their
    documents); ineligible/contractual/unknown fall back to the generic warm decline (FAIL_*)."""
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    subjects, bodies = _DECLINE_TEMPLATES.get(category, (FAIL_SUBJECTS, FAIL_BODIES))
    frontend = _P.frontend_url
    fmt = {'name': name, 'programme': programme_name,
           'link': f'{frontend}/scholarship/application'}
    subject = subjects[lang].format(programme=programme_name)
    text_body = bodies[lang].format(**fmt)
    return _send_html(
        to_email, subject, text_body, _decline_html(text_body),
        from_email=_P.email_from,
        reply_to=[_P.email_support],
    )


# ── Completion reminders (R1 +2d · R2 +9d · R3 +23d · R4/final +53d) ──────────
# Escalating from a gentle nudge to a final "5 days or we close" warning. Each links
# to the application page (the {link} kwarg is filled by _send). Keyed by stage 1–4.
# Shared help line — built-in AI helper (Cikgu Gopal) + a human fallback. Filled into
# the {help} placeholder of each reminder; the closure email uses CLOSURE_HELP.
HELP_LINE = {
    'en': ("As you go, our friendly AI helper, Cikgu Gopal, will guide you through anything "
           f"on your documents that needs attention. If you're still unsure, email us at "
           f"{_P.email_support} — we're glad to help."),
    'ms': ("Sepanjang proses, pembantu AI mesra kami, Cikgu Gopal, akan membimbing anda dalam "
           f"apa-apa pada dokumen anda yang memerlukan perhatian. Jika anda masih tidak pasti, "
           f"e-mel kami di {_P.email_support} — kami sedia membantu."),
    'ta': ("இந்தச் செயல்பாட்டின்போது, எங்கள் நட்பான AI உதவியாளர் சிக்கு கோபால், உங்கள் ஆவணங்களில் "
           "கவனம் தேவைப்படும் எதையும் வழிநடத்துவார். இன்னும் உறுதியில்லை எனில், "
           f"{_P.email_support}-ல் எங்களுக்கு மின்னஞ்சல் அனுப்பவும் — உதவ நாங்கள் தயாராக இருக்கிறோம்."),
}
CLOSURE_HELP = {
    'en': (f"If you'd like to restart and have any questions, our AI helper Cikgu Gopal can "
           f"guide you, or email us at {_P.email_support}."),
    'ms': (f"Jika anda ingin memulakan semula dan mempunyai sebarang pertanyaan, pembantu AI "
           f"kami Cikgu Gopal boleh membimbing anda, atau e-mel kami di {_P.email_support}."),
    'ta': ("மீண்டும் தொடங்க விரும்பினால், ஏதேனும் கேள்விகள் இருந்தால், எங்கள் AI உதவியாளர் சிக்கு "
           f"கோபால் வழிநடத்துவார், அல்லது {_P.email_support}-ல் எங்களுக்கு மின்னஞ்சல் அனுப்பவும்."),
}

REMINDER_SUBJECTS = {
    1: {'en': 'Complete your {programme} application',
        'ms': 'Lengkapkan permohonan {programme} anda',
        'ta': 'உங்கள் {programme} விண்ணப்பத்தை நிறைவுசெய்யவும்'},
    2: {'en': 'A reminder to complete your {programme} application',
        'ms': 'Peringatan untuk melengkapkan permohonan {programme} anda',
        'ta': 'உங்கள் {programme} விண்ணப்பத்தை நிறைவுசெய்ய ஒரு நினைவூட்டல்'},
    3: {'en': 'Please complete your {programme} application',
        'ms': 'Sila lengkapkan permohonan {programme} anda',
        'ta': 'உங்கள் {programme} விண்ணப்பத்தை நிறைவுசெய்யவும்'},
    4: {'en': 'Final reminder — your {programme} application',
        'ms': 'Peringatan terakhir — permohonan {programme} anda',
        'ta': 'இறுதி நினைவூட்டல் — உங்கள் {programme} விண்ணப்பம்'},
}
REMINDER_BODIES = {
    1: {
        'en': ("Dear {name},\n\n"
               "Congratulations again on being shortlisted for the {programme}. To move "
               "forward, please complete your application — share the last few details, "
               "upload your documents, and give consent. It only takes a few minutes.\n\n"
               "{help}\n\n"
               "Complete it here:\n{link}\n\nWarm regards,\nThe {programme} Team"),
        'ms': ("Salam {name},\n\n"
               "Tahniah sekali lagi kerana disenarai pendek untuk {programme}. Untuk "
               "meneruskan, sila lengkapkan permohonan anda — kongsikan beberapa butiran "
               "terakhir, muat naik dokumen anda, dan berikan persetujuan. Ia hanya "
               "mengambil beberapa minit.\n\n"
               "{help}\n\n"
               "Lengkapkan di sini:\n{link}\n\nSalam hormat,\nPasukan {programme}"),
        'ta': ("அன்புள்ள {name},\n\n"
               "{programme}-க்கு தேர்வுசெய்யப்பட்டதற்கு மீண்டும் வாழ்த்துகள். தொடர, உங்கள் "
               "விண்ணப்பத்தை நிறைவுசெய்யவும் — மீதமுள்ள சில விவரங்களைப் பகிர்ந்து, ஆவணங்களைப் "
               "பதிவேற்றி, ஒப்புதல் அளிக்கவும். சில நிமிடங்கள் மட்டுமே ஆகும்.\n\n"
               "{help}\n\n"
               "இங்கே நிறைவுசெய்யவும்:\n{link}\n\nஅன்புடன்,\n{programme} குழு"),
    },
    2: {
        'en': ("Dear {name},\n\n"
               "We noticed your {programme} application isn't finished yet. Please complete "
               "the remaining steps when you can — it only takes a few minutes, and we're "
               "here to help if you get stuck.\n\n"
               "{help}\n\n"
               "Complete it here:\n{link}\n\nWarm regards,\nThe {programme} Team"),
        'ms': ("Salam {name},\n\n"
               "Kami perasan permohonan {programme} anda belum selesai. Sila lengkapkan "
               "langkah yang tinggal apabila anda boleh — ia hanya mengambil beberapa minit, "
               "dan kami sedia membantu jika anda menghadapi masalah.\n\n"
               "{help}\n\n"
               "Lengkapkan di sini:\n{link}\n\nSalam hormat,\nPasukan {programme}"),
        'ta': ("அன்புள்ள {name},\n\n"
               "உங்கள் {programme} விண்ணப்பம் இன்னும் முடிக்கப்படவில்லை என்பதைக் கவனித்தோம். "
               "உங்களால் முடிந்தபோது மீதமுள்ள படிகளை நிறைவுசெய்யவும் — சில நிமிடங்கள் மட்டுமே "
               "ஆகும், சிக்கல் ஏற்பட்டால் உதவ நாங்கள் இருக்கிறோம்.\n\n"
               "{help}\n\n"
               "இங்கே நிறைவுசெய்யவும்:\n{link}\n\nஅன்புடன்,\n{programme} குழு"),
    },
    3: {
        'en': ("Dear {name},\n\n"
               "Your shortlisted {programme} application is still incomplete. To stay in "
               "consideration, please finish it on your dashboard.\n\n"
               "{help}\n\n"
               "Complete it here:\n{link}\n\nWarm regards,\nThe {programme} Team"),
        'ms': ("Salam {name},\n\n"
               "Permohonan {programme} anda yang disenarai pendek masih belum lengkap. Untuk "
               "kekal dalam pertimbangan, sila selesaikannya di papan pemuka anda.\n\n"
               "{help}\n\n"
               "Lengkapkan di sini:\n{link}\n\nSalam hormat,\nPasukan {programme}"),
        'ta': ("அன்புள்ள {name},\n\n"
               "தேர்வுசெய்யப்பட்ட உங்கள் {programme} விண்ணப்பம் இன்னும் முழுமையடையவில்லை. "
               "பரிசீலனையில் இருக்க, உங்கள் டாஷ்போர்டில் அதை நிறைவுசெய்யவும்.\n\n"
               "{help}\n\n"
               "இங்கே நிறைவுசெய்யவும்:\n{link}\n\nஅன்புடன்,\n{programme} குழு"),
    },
    4: {
        'en': ("Dear {name},\n\n"
               "This is the final reminder about your {programme} application. It has been "
               "shortlisted but is not yet complete.\n\n"
               "If it is not completed within 5 days, we will close it — and you would need "
               "to start a new application if you still wish to be considered.\n\n"
               "{help}\n\n"
               "Please complete it now:\n{link}\n\nWarm regards,\nThe {programme} Team"),
        'ms': ("Salam {name},\n\n"
               "Ini ialah peringatan terakhir mengenai permohonan {programme} anda. Ia telah "
               "disenarai pendek tetapi belum lengkap.\n\n"
               "Jika ia tidak dilengkapkan dalam masa 5 hari, kami akan menutupnya — dan anda "
               "perlu memulakan permohonan baharu jika anda masih ingin dipertimbangkan.\n\n"
               "{help}\n\n"
               "Sila lengkapkannya sekarang:\n{link}\n\nSalam hormat,\nPasukan {programme}"),
        'ta': ("அன்புள்ள {name},\n\n"
               "உங்கள் {programme} விண்ணப்பம் குறித்த இறுதி நினைவூட்டல் இது. அது "
               "தேர்வுசெய்யப்பட்டுள்ளது, ஆனால் இன்னும் முழுமையடையவில்லை.\n\n"
               "5 நாட்களுக்குள் நிறைவுசெய்யப்படாவிட்டால், நாங்கள் அதை மூடிவிடுவோம் — மேலும் "
               "நீங்கள் இன்னும் பரிசீலிக்கப்பட விரும்பினால், புதிய விண்ணப்பத்தைத் தொடங்க "
               "வேண்டியிருக்கும்.\n\n"
               "{help}\n\n"
               "தயவுசெய்து இப்போதே நிறைவுசெய்யவும்:\n{link}\n\nஅன்புடன்,\n{programme} குழு"),
    },
}

# ── Auto-close (sent when an application expires for non-completion) ───────────
CLOSED_SUBJECTS = {
    'en': 'Your {programme} application has been closed',
    'ms': 'Permohonan {programme} anda telah ditutup',
    'ta': 'உங்கள் {programme} விண்ணப்பம் மூடப்பட்டது',
}
CLOSED_BODIES = {
    'en': ("Dear {name},\n\n"
           "As your {programme} application was not completed in time, it has now been "
           "closed. We're sorry we couldn't take it further this round.\n\n"
           "You are welcome to start a fresh application if you would still like to be "
           "considered — simply begin again here:\n{link}\n\n"
           "{help}\n\n"
           "Warm regards,\nThe {programme} Team"),
    'ms': ("Salam {name},\n\n"
           "Memandangkan permohonan {programme} anda tidak dilengkapkan dalam masa yang "
           "ditetapkan, ia kini telah ditutup. Kami memohon maaf kerana tidak dapat "
           "meneruskannya pada pusingan ini.\n\n"
           "Anda dialu-alukan untuk memulakan permohonan baharu jika anda masih ingin "
           "dipertimbangkan — mulakan semula di sini:\n{link}\n\n"
           "{help}\n\n"
           "Salam hormat,\nPasukan {programme}"),
    'ta': ("அன்புள்ள {name},\n\n"
           "உங்கள் {programme} விண்ணப்பம் உரிய நேரத்தில் நிறைவுசெய்யப்படாததால், அது இப்போது "
           "மூடப்பட்டுள்ளது. இந்தச் சுற்றில் அதைத் தொடர முடியாததற்கு வருந்துகிறோம்.\n\n"
           "நீங்கள் இன்னும் பரிசீலிக்கப்பட விரும்பினால், புதிய விண்ணப்பத்தைத் தொடங்கலாம் — "
           "இங்கே மீண்டும் தொடங்கவும்:\n{link}\n\n{help}\n\nஅன்புடன்,\n{programme} குழு"),
}


def send_reminder_email(to_email, applicant_name, programme_name, stage, lang='en'):
    """Send completion reminder ``stage`` (1–4). Stage 4 is the final 'complete within
    5 days or we close it' warning. No-op for an unknown stage."""
    if stage not in REMINDER_SUBJECTS:
        return False
    return _send(to_email, REMINDER_SUBJECTS[stage], REMINDER_BODIES[stage],
                 applicant_name, programme_name, lang,
                 extra={'help': HELP_LINE[normalise_lang(lang)]})


def send_application_closed_email(to_email, applicant_name, programme_name, lang='en'):
    """Confirm an application was auto-closed for non-completion, inviting a fresh start."""
    return _send(to_email, CLOSED_SUBJECTS, CLOSED_BODIES, applicant_name, programme_name, lang,
                 extra={'help': CLOSURE_HELP[normalise_lang(lang)]})


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
    frontend = _P.frontend_url
    link = f'{frontend}/scholarship/application'
    try:
        send_mail(
            subject=REQUEST_INFO_SUBJECTS[lang].format(programme=programme_name),
            message=REQUEST_INFO_BODIES[lang].format(
                name=name, programme=programme_name, note=note, link=link),
            from_email=_P.email_from,
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send request-info email to %s', to_email, exc_info=True)
        return False


QUERY_REMINDER_SUBJECTS = {
    'en': 'A few things we need for your {programme} application',
    'ms': 'Beberapa perkara yang kami perlukan untuk permohonan {programme} anda',
    'ta': 'உங்கள் {programme} விண்ணப்பத்திற்கு எங்களுக்குத் தேவையான சில விவரங்கள்',
}
QUERY_REMINDER_BODIES = {
    'en': ('Dear {name},\n\nThere are {n} item(s) waiting in your Action Centre — a few '
           'questions and/or documents — to help us complete your {programme} profile. Please '
           'sign in and respond to each one within about {days} day(s): {link}\n\nIf we do not '
           'hear back in time we will proceed with what we have, so it is best to respond.\n\n'
           'Thank you.'),
    'ms': ('Salam {name},\n\nTerdapat {n} perkara menunggu di Pusat Tindakan anda — beberapa '
           'soalan dan/atau dokumen — untuk membantu kami melengkapkan profil {programme} anda. '
           'Sila log masuk dan lengkapkan setiap satu dalam kira-kira {days} hari: {link}\n\n'
           'Jika kami tidak menerima maklum balas tepat pada masanya, kami akan teruskan dengan '
           'maklumat sedia ada, jadi eloklah membalas.\n\nTerima kasih.'),
    'ta': ('அன்புள்ள {name},\n\nஉங்கள் {programme} விவரக்குறிப்பை முழுமைப்படுத்த உதவ உங்கள் செயல் '
           'மையத்தில் {n} விவரம்(கள்) — சில கேள்விகள் மற்றும்/அல்லது ஆவணங்கள் — காத்திருக்கின்றன. '
           'தயவுசெய்து உள்நுழைந்து சுமார் {days} நாட்களுக்குள் ஒவ்வொன்றுக்கும் பதிலளிக்கவும்: {link}'
           '\n\nசரியான நேரத்தில் பதில் கிடைக்காவிட்டால், எங்களிடம் உள்ள தகவலுடன் தொடர்வோம், எனவே '
           'பதிலளிப்பது நல்லது.\n\nநன்றி.'),
}


def send_query_reminder_email(to_email, applicant_name, programme_name, n_queries,
                              days_left, lang='en'):
    """Check 2 STEP 2: nudge the student to answer their open AI clarify queries in the
    Action Centre before the SLA lapses. Trilingual; best-effort."""
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    frontend = _P.frontend_url
    link = f'{frontend}/scholarship/application'
    try:
        send_mail(
            subject=QUERY_REMINDER_SUBJECTS[lang].format(programme=programme_name),
            message=QUERY_REMINDER_BODIES[lang].format(
                name=name, programme=programme_name, n=n_queries, days=days_left, link=link),
            from_email=_P.email_from,
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send query-reminder email to %s', to_email, exc_info=True)
        return False


QUERY_RAISED_SUBJECTS = {
    'en': 'A few things we need for your {programme} application',
    'ms': 'Beberapa perkara yang kami perlukan untuk permohonan {programme} anda',
    'ta': 'உங்கள் {programme} விண்ணப்பத்திற்கு எங்களுக்குத் தேவையான சில விவரங்கள்',
}
QUERY_RAISED_BODIES = {
    'en': ('Dear {name},\n\nThank you for submitting your {programme} application. We are '
           'reviewing it and need a little more from you — {n} item(s) (a few questions and/or '
           'documents) are waiting in your Action Centre. Please sign in and respond to each one '
           'here: {link}\n\nIt only takes a few minutes, and it helps us put your case forward '
           'well.\n\nThank you.'),
    'ms': ('Salam {name},\n\nTerima kasih kerana menghantar permohonan {programme} anda. Kami '
           'sedang menyemaknya dan memerlukan sedikit lagi daripada anda — {n} perkara (beberapa '
           'soalan dan/atau dokumen) menunggu di Pusat Tindakan anda. Sila log masuk dan '
           'lengkapkan setiap satu di sini: {link}\n\nIa hanya mengambil beberapa minit, dan ia '
           'membantu kami mengetengahkan kes anda dengan baik.\n\nTerima kasih.'),
    'ta': ('அன்புள்ள {name},\n\nஉங்கள் {programme} விண்ணப்பத்தைச் சமர்ப்பித்ததற்கு நன்றி. நாங்கள் '
           'அதை மதிப்பாய்வு செய்து வருகிறோம்; உங்களிடமிருந்து இன்னும் சிறிது தேவை — {n} விவரம்(கள்) '
           '(சில கேள்விகள் மற்றும்/அல்லது ஆவணங்கள்) உங்கள் செயல் மையத்தில் காத்திருக்கின்றன. '
           'தயவுசெய்து உள்நுழைந்து ஒவ்வொன்றுக்கும் இங்கே பதிலளிக்கவும்: {link}\n\nஇதற்கு சில '
           'நிமிடங்களே ஆகும்; இது உங்கள் வழக்கை நன்கு முன்வைக்க உதவும்.\n\nநன்றி.'),
}


def send_query_raised_email(to_email, applicant_name, programme_name, n_queries, lang='en'):
    """Check 2 STEP 2: at submission, tell the student a few clarify questions are waiting
    in their Action Centre so they come back and answer. Trilingual; best-effort."""
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    frontend = _P.frontend_url
    link = f'{frontend}/scholarship/application'
    try:
        send_mail(
            subject=QUERY_RAISED_SUBJECTS[lang].format(programme=programme_name),
            message=QUERY_RAISED_BODIES[lang].format(
                name=name, programme=programme_name, n=n_queries, link=link),
            from_email=_P.email_from,
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send query-raised email to %s', to_email, exc_info=True)
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
            from_email=_P.email_from,
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send sponsor-interest email for %s', email, exc_info=True)
        return False


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


def send_vision_outage_alert_email(stats):
    """Alert the admin that Google Vision OCR appears to be down — every recent
    IC/parent-IC OCR attempt errored and none succeeded. Sent to
    ``settings.ADMIN_NOTIFY_EMAIL`` (contact@halatuju.xyz); skipped silently if unset.
    English-only (internal). Best-effort — swallows send failures."""
    to_email = getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or ''
    if not to_email:
        return False
    try:
        send_mail(
            subject='[HalaTuju] Document OCR (Google Vision) may be down',
            message=(
                'Automated check: in the last {window_hours}h, every IC / parent-IC '
                'OCR attempt failed with a service error and none succeeded '
                '({service_failures} service failures across {attempts} attempts).\n\n'
                'While this persists, shortlisted students cannot pass the consent '
                'identity check (their IC can\'t be auto-verified). Please check the '
                'Google Vision API status, quota and billing for the HalaTuju project.\n\n'
                'This is an automated alert and will repeat daily until OCR recovers.'
            ).format(**stats),
            from_email=_P.email_from,
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send Vision-outage alert email', exc_info=True)
        return False


def send_profile_complete_admin_email(application_id, applicant_name, programme_name):
    """Phase C: notify the admin that an applicant has confirmed a complete Step-4
    profile and is ready for review. English-only (internal). Sent to
    ``settings.ADMIN_NOTIFY_EMAIL``; skipped silently if that's unset so it never
    blocks the student's confirm. Best-effort — swallows send failures."""
    to_email = getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or ''
    if not to_email:
        return False
    frontend = _P.frontend_url
    name = applicant_name or 'An applicant'
    try:
        send_mail(
            subject=f'[{programme_name}] Application #{application_id} ready for review',
            message=(
                f'{name} has confirmed a complete profile for {programme_name} '
                f'(application #{application_id}) and is ready for review.\n\n'
                f'Review it: {frontend}/admin/scholarship/{application_id}'
            ),
            from_email=_P.email_from,
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send admin-notify email for application #%s',
                       application_id, exc_info=True)
        return False


# ── Reviewer emails — shared bits (one greeting, one CTA, one sign-off) ────────
# All reviewer mail goes out via _send_plain → from the monitored interview@ alias with a
# working reply-to, so "reply to reassign" / replies actually reach a person. The subject
# carries the Scholar-code so a reviewer juggling several applicants can triage at a glance.
_REVIEWER_SIGNOFF = 'Thanks,\nThe BrightPath Bursary Team'


def _reviewer_dashboard_cta():
    """The single CTA every reviewer email shares — one name ('reviewer dashboard'), one link."""
    frontend = _P.frontend_url
    return f'Open in your reviewer dashboard:\n{frontend}/admin/login'


def _reviewer_subject(base, ref):
    """Append the Scholar-code (ref) so reviewers can triage from the subject line."""
    return f'{base} — {ref}' if ref else base


def send_reviewer_assigned_email(to_email, reviewer_name, *, ref='', programme='', review_by=''):
    """F7: notify a reviewer that an applicant has been assigned to them. English-only
    (reviewers are internal staff). Sent on each (re)assignment — never re-sent for an
    unchanged assignee, because assign_reviewer short-circuits a no-op before this fires.
    From the monitored interview@ alias so 'reply to reassign' actually reaches a person.
    Best-effort — swallows send failures so a mail hiccup never breaks the assignment."""
    if not to_email:
        return False
    reviewer = reviewer_name or 'there'
    details = [f'Reference: {ref or "—"}', f'Programme: {programme or "—"}']
    if review_by:
        details.append(f'Please review by: {review_by}')
    body = (
        f'Dear {reviewer},\n\n'
        f'A new applicant has been assigned to you for review.\n\n'
        + '\n'.join(details) + '\n\n'
        f'Everything you need — profile, documents, and the verification checks — is in your '
        f'reviewer dashboard:\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f"Can't take this one? Just reply and we'll reassign it.\n\n"
        f'{_REVIEWER_SIGNOFF}'
    )
    return _send_plain(to_email, _reviewer_subject('New applicant assigned to you', ref), body)


_PARTNER_ROLE_LABELS = {
    'admin': 'an administrator',
    'partner': 'a partner organisation representative',
    'reviewer': 'a reviewer',
    'qc': 'a quality-control reviewer',
    'super': 'a super administrator',
}


def send_partner_welcome_email(to_email, name, role, temp_password=None, google=False):
    """Onboard a new partner admin / reviewer. English-only (internal staff), like every other
    admin-facing email here.

    Replaces the Supabase "Invite user" email (2026-07-12). That one carried a magic link that
    EXPIRED IN 24 HOURS and, once expired, could not be re-sent by any route — an invitee who
    missed the window was stuck. This email carries no token: the account already exists when it is
    sent, so re-sending is always safe. The temp password itself now expires after 7 days (owner
    2026-07-14), but that is never a dead-end — Forgot-password (self-serve, any time) or a Resend
    re-issues it. The Google / already-registered variants get no password at all.

    ``temp_password`` is None when the person already had a HalaTuju account (they sign in with
    the credentials they already have). It is the ONLY copy of that password — it is not stored,
    logged, or returned to the caller — so a send failure must be surfaced, not swallowed; the
    bool return is what the view reports as ``emailed``.
    """
    if not to_email:
        return False
    who = name or 'there'
    role_label = _PARTNER_ROLE_LABELS.get(role, 'a team member')
    frontend = _P.frontend_url
    link = f'{frontend}/admin/login'

    if google:
        access = (
            f'Just click "Sign in with Google" and use this email address ({to_email}) — '
            f'there is no password to set up. Your access is waiting for you.'
        )
    elif temp_password:
        access = (
            f'Your temporary password (valid for 7 days) is:\n\n'
            f'    {temp_password}\n\n'
            f"You'll be asked to choose your own password the first time you use it.\n\n"
            f'If it expires before you sign in, or you lose it, you can set a new one yourself at '
            f'any time with "Forgot password" on the sign-in page — or ask whoever added you to '
            f're-send your details.'
        )
    else:
        access = (
            f'You already have a HalaTuju account, so simply sign in the way you normally do '
            f'— with Google, or with your existing password. Your new access is waiting for you.'
        )

    body = (
        f'Dear {who},\n\n'
        f'You have been added to HalaTuju as {role_label}.\n\n'
        f'Sign in here:\n{link}\n\n'
        f'{access}\n\n'
        f'Any trouble at all, just reply to this email.\n\n'
        f'Warm regards,\nThe HalaTuju Team'
    )
    try:
        EmailMessage(
            subject='Your HalaTuju partner access',
            body=body,
            from_email=_P.email_from,
            to=[to_email],
            reply_to=[_P.email_support],
        ).send()
        return True
    except Exception:
        logger.warning('Failed to send partner welcome email to %s', to_email, exc_info=True)
        return False


def send_qc_returned_email(to_email, reviewer_name, *, ref='', applicant_name='', qc_comments=''):
    """QC (2026-07): notify a reviewer that quality control has RETURNED their case for revision,
    carrying the QC's comments (what was missing / the gaps). English-only (internal staff), from
    the monitored interview@ alias. Best-effort — a mail hiccup never breaks the QC action."""
    if not to_email:
        return False
    reviewer = reviewer_name or 'there'
    details = [f'Reference: {ref or "—"}', f'Applicant: {applicant_name or "—"}']
    body = (
        f'Dear {reviewer},\n\n'
        f'Quality control has returned one of your cases for revision.\n\n'
        + '\n'.join(details) + '\n\n'
        f'What to address:\n{qc_comments}\n\n'
        f'Please review the points above, update your findings/verdict, and resubmit. Everything '
        f'you need is in your reviewer dashboard:\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _send_plain(to_email, _reviewer_subject('Case returned by QC — action needed', ref), body)


def send_qc_rejected_email(to_email, reviewer_name, *, ref='', applicant_name='', qc_comments=''):
    """QC (2026-07): notify a reviewer that quality control has REJECTED one of their cases outright
    (not returned for revision — the case is closed). Carries the QC's reason. English-only (internal
    staff), from the monitored interview@ alias. Best-effort — a mail hiccup never breaks the action."""
    if not to_email:
        return False
    reviewer = reviewer_name or 'there'
    details = [f'Reference: {ref or "—"}', f'Applicant: {applicant_name or "—"}']
    body = (
        f'Dear {reviewer},\n\n'
        f'After quality control review, one of your cases has been rejected. No further action is '
        f'needed from you — this note is for your records.\n\n'
        + '\n'.join(details) + '\n\n'
        f'QC reason:\n{qc_comments}\n\n'
        f'You can see the case in your reviewer dashboard:\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _send_plain(to_email, _reviewer_subject('Case rejected by QC', ref), body)


def send_student_assigned_reviewer_email(to_email, *, student_name, english_only=False,
                                         reviewer_name='', reviewer_email='', reviewer_phone=''):
    """Advance notice to the STUDENT once a reviewer is assigned: what happens next (an
    interview is coming, times to follow), with a short prep list. HTML primary + plain-text
    fallback; bilingual (EN + BM) by default, ``english_only=True`` drops the BM mirror. The
    interviewer's NAME is woven in when known, but never their contact details (owner's design).
    Best-effort; never breaks the assignment. Gated by STUDENT_ASSIGNMENT_EMAIL_ENABLED at the
    call site. (reviewer_email/reviewer_phone kept for call compatibility; unused.)"""
    if not to_email:
        return False
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'
    reviewer = (reviewer_name or '').strip()
    subject = 'Your BrightPath Bursary Programme interview — what happens next'

    en_intro = ('Your application has reached the interview stage of the BrightPath Bursary Programme, '
                + (f'and your interview will be with {reviewer}, one of our programme’s interviewers.'
                   if reviewer else 'and an interviewer from our team has now been assigned to you.'))
    en_what = ('The interview is a short video call, about 30 minutes, to understand your '
               'family’s situation fairly. We’ll send you a few times to choose from shortly, '
               'so you can pick the one that suits you best. Once you choose, we’ll send a '
               'Google Meet link and, if necessary, reminders before the call — there’s nothing you '
               'need to arrange yourself in the meantime.')
    en_points = [
        'Please join by video, with your camera on, as this helps us verify your application.',
        'If you are under 18, please have a parent or guardian with you for the call. If they’re '
        'available, our interviewer would be glad to speak with them whatever your age.',
        'The support is for families with genuine financial need, so we’ll ask honestly about your '
        'circumstances — and we value your honesty in return.',
    ]
    en_safety = (f'One note for your peace of mind: we’ll only ever ask about you and your studies. '
                 f'We will never ask you for money, a bank password, or an OTP or PIN. If anyone '
                 f'does, it’s not us — please tell us at {_P.email_support}.')

    bm_intro = ('Permohonan anda telah sampai ke peringkat temu duga Program Bursari BrightPath, '
                + (f'dan temu duga anda akan bersama {reviewer}, salah seorang penemu duga program kami.'
                   if reviewer else 'dan seorang penemu duga daripada pasukan kami kini telah ditugaskan kepada anda.'))
    bm_what = ('Temu duga ialah panggilan video ringkas, kira-kira 30 minit, untuk memahami '
               'keadaan keluarga anda secara adil. Kami akan menghantar kepada anda beberapa masa '
               'untuk dipilih tidak lama lagi, supaya anda boleh memilih yang '
               'paling sesuai. Setelah anda memilih, kami akan menghantar pautan Google Meet dan, '
               'jika perlu, peringatan sebelum panggilan — tiada apa-apa yang perlu anda uruskan '
               'sendiri buat masa ini.')
    bm_points = [
        'Sila sertai melalui video, dengan kamera dibuka, kerana ini membantu kami mengesahkan '
        'permohonan anda.',
        'Jika anda di bawah 18 tahun, sila pastikan ibu bapa atau penjaga bersama anda semasa '
        'panggilan. Jika mereka ada, penemu duga kami amat berbesar hati untuk bercakap dengan '
        'mereka tidak kira umur anda.',
        'Bantuan ini untuk keluarga yang benar-benar memerlukan, jadi kami akan bertanya secara '
        'jujur tentang keadaan anda — dan kami menghargai kejujuran anda sebagai balasan.',
    ]
    bm_safety = (f'Satu nota untuk ketenangan anda: kami hanya akan bertanya tentang diri dan '
                 f'pengajian anda. Kami tidak sekali-kali akan meminta wang, kata laluan bank, '
                 f'atau OTP atau PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila '
                 f'beritahu kami di {_P.email_support}.')

    # ── Plain text ────────────────────────────────────────────────────────────
    def text_block(greeting, intro, what, points_label, points, safety, closing, signoff):
        bullets = '\n'.join(f'• {p}' for p in points)
        return (f'{greeting}\n\n{intro}\n\n{what}\n\n{points_label}\n{bullets}\n\n'
                f'{safety}\n\n{closing}\n\n{signoff}')
    en_text = text_block(
        f'Hi {en_name},', en_intro, en_what, 'A few things to know beforehand:', en_points,
        en_safety, 'We look forward to speaking with you.',
        'Warm regards,\nThe BrightPath Bursary Team')
    bm_text = text_block(
        f'Salam {bm_name},', bm_intro, bm_what, 'Beberapa perkara untuk diketahui:', bm_points,
        bm_safety, 'Kami menantikan untuk bercakap dengan anda.',
        'Salam hormat,\nPasukan Program Bursari BrightPath')
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    # ── HTML ──────────────────────────────────────────────────────────────────
    def html_block(greeting, intro, what, points_label, points, safety, closing, signoff):
        lis = ''.join(f'<li style="margin:0 0 8px;">{p}</li>' for p in points)
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 14px;">{intro}</p>'
            f'<p style="margin:0 0 14px;">{what}</p>'
            f'<p style="margin:0 0 6px;">{points_label}</p>'
            f'<ul style="margin:0 0 16px;padding-left:20px;">{lis}</ul>'
            f'<p style="margin:0 0 16px;color:#6b7280;font-size:13px;">{safety}</p>'
            f'<p style="margin:0 0 14px;">{closing}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    en_html = html_block(
        f'Hi {en_name},', en_intro, en_what, 'A few things to know beforehand:', en_points,
        en_safety, 'We look forward to speaking with you.',
        'Warm regards,<br>The BrightPath Bursary Team')
    bm_html = html_block(
        f'Salam {bm_name},', bm_intro, bm_what, 'Beberapa perkara untuk diketahui:', bm_points,
        bm_safety, 'Kami menantikan untuk bercakap dengan anda.',
        'Salam hormat,<br>Pasukan Program Bursari BrightPath')
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    return _send_html(to_email, subject, text_body, html_body)


def send_profile_complete_student_email(to_email, *, student_name, english_only=False):
    """Sent to the STUDENT when they confirm their profile (shortlisted → profile_complete):
    thanks + congratulates them for completing the stage and submitting documents, then sets
    expectations for what comes next (Check-2 review → possible doc requests / questions →
    interview with three slots to pick → minors need a parent/guardian present). HTML primary
    + plain-text fallback; bilingual (EN + BM) unless ``english_only``. Best-effort → bool."""
    if not to_email:
        return False
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'
    frontend = _P.frontend_url
    link = f'{frontend}/scholarship/application'
    subject = 'Your B40 application is in — here’s what happens next'

    en_intro = ('Thank you — your application and documents for the BrightPath Bursary Programme are '
                'safely in. Pulling everything together takes real effort, so well done for getting '
                'it done.')
    en_lead = ('Your application is now with our team. Here’s exactly what happens next, so there '
               'are no surprises:')
    en_steps = [
        ('We review everything you’ve sent.', 'Our team reads through your application and documents '
         'carefully, to understand your family’s situation fairly. Sometimes we need a clearer copy '
         'of a document, an extra document, or a short answer to a question — if so, it’ll appear in '
         'your Action Centre and we’ll email to let you know. Just reply inside the Action Centre; '
         'responding quickly helps your application move along.'),
        ('We invite you to a short interview.', 'Once the review is settled, we’ll offer you three '
         'time slots — pick the one that suits you best. If you’re under 18, please choose a time a '
         'parent or guardian can join too, as they’ll need to be with you for the call.'),
        ('The interview itself.', 'It’s a short video call, about 30 minutes, on Google Meet. We’ll '
         'email the joining link as soon as you book, with a reminder before the call. Please join '
         'with your camera on so we can meet you face to face. If you’re under 18, your parent or '
         'guardian should be with you — and whatever your age, our interviewer is always glad to '
         'say hello to them.'),
    ]
    en_after = ('For now, there’s nothing you need to arrange — just keep an eye on your email and '
                'Action Centre. You’ll usually hear from us within about one to two weeks, whether '
                'that’s a quick question or your invitation to interview.')
    en_safety = (f'One note for your peace of mind: we’ll only ever ask about you and your studies. '
                 f'We will never ask you for money, a bank password, or an OTP or PIN. If anyone '
                 f'does, it isn’t us — please tell us straight away at {_P.email_support}.')

    bm_intro = ('Terima kasih — permohonan dan dokumen anda untuk Program Bursari BrightPath telah selamat '
                'diterima. Mengumpulkan semuanya memerlukan usaha yang sungguh-sungguh, jadi syabas '
                'kerana menyelesaikannya.')
    bm_lead = ('Permohonan anda kini bersama pasukan kami. Berikut ialah perkara yang akan berlaku '
               'seterusnya, supaya tiada kejutan:')
    bm_steps = [
        ('Kami menyemak semua yang anda hantar.', 'Pasukan kami membaca permohonan dan dokumen anda '
         'dengan teliti, untuk memahami keadaan keluarga anda secara adil. Kadangkala kami '
         'memerlukan salinan dokumen yang lebih jelas, dokumen tambahan, atau jawapan ringkas '
         'kepada soalan — jika ya, ia akan muncul di Pusat Tindakan anda dan kami akan menghantar '
         'e-mel untuk memberitahu anda. Balas sahaja di dalam Pusat Tindakan; membalas dengan cepat '
         'membantu permohonan anda bergerak.'),
        ('Kami menjemput anda ke temu duga ringkas.', 'Setelah semakan selesai, kami akan menawarkan '
         'anda tiga slot masa — pilih yang paling sesuai untuk anda. Jika anda di bawah 18 tahun, '
         'sila pilih masa yang membolehkan ibu bapa atau penjaga turut menyertai, kerana mereka '
         'perlu bersama anda semasa panggilan.'),
        ('Temu duga itu sendiri.', 'Ia panggilan video ringkas, kira-kira 30 minit, melalui Google '
         'Meet. Kami akan menghantar pautan untuk menyertai sebaik sahaja anda menempah, dengan '
         'peringatan sebelum panggilan. Sila sertai dengan kamera dibuka supaya kami dapat bertemu '
         'anda secara bersemuka. Jika anda di bawah 18 tahun, ibu bapa atau penjaga anda perlu '
         'bersama anda — dan tidak kira umur anda, penemu duga kami sentiasa berbesar hati untuk '
         'menyapa mereka.'),
    ]
    bm_after = ('Buat masa ini, tiada apa-apa yang perlu anda uruskan — pantau sahaja e-mel dan '
                'Pusat Tindakan anda. Kebiasaannya anda akan mendengar daripada kami dalam masa '
                'kira-kira satu hingga dua minggu, sama ada soalan ringkas atau jemputan temu duga '
                'anda.')
    bm_safety = (f'Satu nota untuk ketenangan anda: kami hanya akan bertanya tentang diri dan '
                 f'pengajian anda. Kami tidak sekali-kali akan meminta wang, kata laluan bank, atau '
                 f'OTP atau PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila beritahu kami '
                 f'dengan segera di {_P.email_support}.')

    # ── Plain text ────────────────────────────────────────────────────────────
    def text_block(greeting, intro, lead, steps, btn_line, after, safety, signoff):
        body_steps = '\n\n'.join(f'{i}. {t} {d}' for i, (t, d) in enumerate(steps, 1))
        return (f'{greeting}\n\n{intro}\n\n{lead}\n\n{body_steps}\n\n{btn_line}\n\n'
                f'{after}\n\n{safety}\n\n{signoff}')
    en_text = text_block(
        f'Hi {en_name},', en_intro, en_lead, en_steps, f'View my application: {link}', en_after,
        en_safety, 'Warm regards,\nThe BrightPath Bursary Team')
    bm_text = text_block(
        f'Salam {bm_name},', bm_intro, bm_lead, bm_steps, f'Lihat permohonan saya: {link}', bm_after,
        bm_safety, 'Salam hormat,\nPasukan Program Bursari BrightPath')
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    # ── HTML ──────────────────────────────────────────────────────────────────
    def html_block(greeting, intro, lead, steps, btn_label, after, safety, signoff):
        lis = ''.join(
            f'<li style="margin:0 0 12px;"><strong>{t}</strong> {d}</li>' for t, d in steps)
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 14px;">{intro}</p>'
            f'<p style="margin:0 0 10px;">{lead}</p>'
            f'<ol style="margin:0 0 18px;padding-left:20px;">{lis}</ol>'
            f'<p style="margin:0 0 18px;">{_email_button(link, btn_label)}</p>'
            f'<p style="margin:0 0 14px;">{after}</p>'
            f'<p style="margin:0 0 16px;color:#6b7280;font-size:13px;">{safety}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    en_html = html_block(
        f'Hi {en_name},', en_intro, en_lead, en_steps, 'View my application', en_after,
        en_safety, 'Warm regards,<br>The BrightPath Bursary Team')
    bm_html = html_block(
        f'Salam {bm_name},', bm_intro, bm_lead, bm_steps, 'Lihat permohonan saya', bm_after,
        bm_safety, 'Salam hormat,<br>Pasukan Program Bursari BrightPath')
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    # General programme email → from info@ (DEFAULT_FROM_EMAIL), reply to support; NOT interview@.
    return _send_html(to_email, subject, text_body, html_body,
                      from_email=_P.email_from,
                      reply_to=[_P.email_support])


def send_contact_submission_admin_email(*, to_email, name, contact, category, message, created_at):
    """Internal: email a public contact-form submission to the team (contact@ via
    ADMIN_NOTIFY_EMAIL). Reply-To is set to the submitter's contact when it looks like
    an email, so a reply goes straight back to them. Plain English. Best-effort → bool."""
    if not to_email:
        return False
    body = (
        f'New contact-form message — {category}\n\n'
        f'From:     {name}\n'
        f'Contact:  {contact}\n'
        f'Received: {created_at}\n\n'
        f'{message}\n'
    )
    reply_to = [contact] if (contact and '@' in contact) else None
    try:
        EmailMessage(
            subject=f'[HalaTuju contact] {category} — {name}'[:120],
            body=body,
            from_email=_P.email_from,
            to=[to_email],
            reply_to=reply_to,
        ).send()
        return True
    except Exception:
        logger.warning('Failed to send contact-submission email to %s', to_email, exc_info=True)
        return False


# ── Interview scheduling (booking confirmation + reminders + cancellation) ────
# Student-facing emails are bilingual (English then Bahasa Melayu) and use the
# student-facing term "interviewer" / "Penemu duga". Reviewer-facing emails are
# plain English (internal staff). All best-effort; the booking never depends on them.

def _fmt_myt_time(dt):
    """Time-only in Malaysia time, e.g. '8:00 PM' (used in the reminder 'when' phrase)."""
    if dt is None:
        return ''
    try:
        from zoneinfo import ZoneInfo
        local = dt.astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
    except Exception:
        local = dt
    hour12 = local.hour % 12 or 12
    ampm = 'AM' if local.hour < 12 else 'PM'
    return f'{hour12}:{local:%M} {ampm}'


def _fmt_myt(dt):
    """Format a tz-aware datetime in Malaysia time, e.g. 'Mon, 23 Jun 2026, 8:00 PM (MYT)'."""
    if dt is None:
        return ''
    try:
        from zoneinfo import ZoneInfo
        local = dt.astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
    except Exception:
        local = dt
    # %-I isn't portable (Windows); derive a no-leading-zero 12-hour clock manually.
    hour12 = local.hour % 12 or 12
    ampm = 'AM' if local.hour < 12 else 'PM'
    return f'{local:%a, %d %b %Y}, {hour12}:{local:%M} {ampm} (MYT)'


def _interview_unsub_headers():
    """A harmless List-Unsubscribe on interview/service emails: a mailto to support, so a
    mistaken 'unsubscribe' click just lands a note in the support inbox for a human — instead
    of triggering the ESP's auto-suppression that would silently stop us reaching the student
    about reminders or their decision. No one-click POST header, so nothing auto-fires. (The
    definitive fix is a Brevo-side List-Help on transactional mail.)"""
    return {'List-Unsubscribe': f'<mailto:{_P.email_support}?subject=Unsubscribe%20from%20B40%20emails>'}


def _send_bilingual(to_email, subject, en, bm):
    """Send one EN+BM email (the booking-flow pattern), with Reply-To = the interview
    alias so replies route there. Best-effort → bool."""
    if not to_email:
        return False
    try:
        EmailMessage(
            subject=subject,
            body=en + '\n\n———\n\n' + bm,
            from_email=_P.interview_from,
            to=[to_email],
            reply_to=[_P.interview_reply_to],
            headers=_interview_unsub_headers(),
        ).send()
        return True
    except Exception:
        logger.warning('Failed to send interview email to %s', to_email, exc_info=True)
        return False


def english_only_email(application) -> bool:
    """True when we can confidently send a student email in English only: they used the app
    in English, did NOT ask to be contacted in Malay/Tamil, AND scored A/A+ in SPM English.
    Otherwise bilingual (EN+BM) — conservative: any Malay/Tamil signal keeps the Malay mirror."""
    profile = getattr(application, 'profile', None)
    locale = (getattr(application, 'locale', '') or '').lower()
    call_lang = (getattr(profile, 'preferred_call_language', '') or '').lower() if profile else ''
    if locale != 'en' or call_lang in ('ms', 'ta'):
        return False
    grades = getattr(profile, 'grades', None) if profile else None
    eng = ''
    if isinstance(grades, dict):
        eng = str(grades.get('eng', '') or '').strip().upper().replace('−', '-')
    return eng in ('A+', 'A')


def _send_html(to_email, subject, text_body, html_body, reply_to=None, ics=None, from_email=None,
               attachments=None):
    """Send a multipart email — HTML primary + plain-text fallback. From/Reply-To default to
    the interview alias (interview emails are the main caller); pass ``from_email`` +
    ``reply_to`` for a general (non-interview) email, e.g. the info@ sender. ``ics`` (a
    calendar string) is attached as interview.ics so the client offers "add to calendar".
    ``attachments`` is a list of ``(filename, content, mimetype)`` triples — e.g. the Vircle
    installation-guide PDF. Best-effort → bool."""
    if not to_email:
        return False
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email or _P.interview_from,
            to=[to_email],
            reply_to=reply_to or [_P.interview_reply_to],
            headers=_interview_unsub_headers(),
        )
        msg.attach_alternative(html_body, 'text/html')
        if ics:
            msg.attach('interview.ics', ics, 'text/calendar')
        for attachment in (attachments or []):
            msg.attach(*attachment)
        msg.send()
        return True
    except Exception:
        logger.warning('Failed to send HTML email to %s', to_email, exc_info=True)
        return False


def _interview_ics(*, start, duration_min, summary, description='', location=''):
    """A minimal VCALENDAR/VEVENT for the booked interview (attached so mail clients show
    an 'add to calendar' affordance)."""
    from datetime import datetime, timedelta, timezone as dtz
    def z(dt):
        return dt.astimezone(dtz.utc).strftime('%Y%m%dT%H%M%SZ')
    def esc(s):
        return (str(s or '').replace('\\', '\\\\').replace(';', '\\;')
                .replace(',', '\\,').replace('\n', '\\n'))
    end = start + timedelta(minutes=duration_min)
    lines = [
        'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//HalaTuju//B40//EN', 'METHOD:PUBLISH',
        'BEGIN:VEVENT', f'UID:b40-interview-{int(start.timestamp())}@{_P.ics_uid_domain}',
        f'DTSTAMP:{datetime.now(dtz.utc).strftime("%Y%m%dT%H%M%SZ")}', f'DTSTART:{z(start)}', f'DTEND:{z(end)}',
        f'SUMMARY:{esc(summary)}', f'DESCRIPTION:{esc(description)}', f'LOCATION:{esc(location)}',
        'END:VEVENT', 'END:VCALENDAR',
    ]
    return '\r\n'.join(lines) + '\r\n'


def _gcal_url(*, start, duration_min, text, details='', location=''):
    """A Google Calendar 'create event' template URL for the 'Add to calendar' button."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    from urllib.parse import urlencode
    def z(dt):
        return dt.astimezone(ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ')
    end = start + timedelta(minutes=duration_min)
    q = urlencode({'action': 'TEMPLATE', 'text': text, 'dates': f'{z(start)}/{z(end)}',
                   'details': details, 'location': location})
    return f'https://calendar.google.com/calendar/render?{q}'


def _html_email_shell(*sections):
    """Wrap one or more HTML strings in a simple, email-client-safe card layout."""
    divider = '<hr style="border:none;border-top:1px solid #e5e7eb;margin:22px 0;">'
    inner = divider.join(sections)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;background:#f3f4f6;">'
        '<div style="max-width:560px;margin:0 auto;padding:24px;'
        'font-family:Arial,Helvetica,sans-serif;color:#111827;font-size:15px;line-height:1.55;">'
        '<div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;padding:24px;">'
        + inner +
        '</div></div></body></html>'
    )


def _email_button(href, label):
    return (
        f'<a href="{href}" style="display:inline-block;background:#2563eb;color:#ffffff;'
        f'text-decoration:none;font-weight:600;padding:12px 22px;border-radius:8px;'
        f'font-size:15px;">{label}</a>'
    )


def _join_line(meeting_url, lang='en'):
    if meeting_url:
        return (f'• Join here: {meeting_url}\n' if lang == 'en'
                else f'• Sertai di sini: {meeting_url}\n')
    return ('• Your interviewer will share the video-call link before the interview.\n'
            if lang == 'en'
            else '• Penemu duga anda akan berkongsi pautan panggilan video sebelum temu duga.\n')


def send_interview_booked_email(to_email, *, student_name, reviewer_name, start,
                                meeting_url='', english_only=False, duration_min=None,
                                reviewer_phone=''):
    """Student confirmation that an interview slot is booked. HTML primary + plain-text
    fallback; bilingual (EN + BM) by default, ``english_only=True`` drops the BM mirror.
    Names the interviewer (no contact details); attaches an .ics + an Add-to-calendar
    button. Best-effort. (``reviewer_phone`` kept for call compatibility; unused.)"""
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'
    reviewer = (reviewer_name or '').strip()
    rev_en = reviewer or 'one of our interviewers'
    rev_bm = reviewer or 'salah seorang penemu duga kami'
    when = _fmt_myt(start)
    cutoff = getattr(settings, 'INTERVIEW_RESCHEDULE_CUTOFF_HOURS', 12)
    duration_min = duration_min or getattr(settings, 'INTERVIEW_DURATION_MIN', 45)
    app_link = f"{_P.frontend_url}/scholarship/application"
    summary = 'BrightPath Bursary Programme interview'
    details = f'Join: {meeting_url}' if meeting_url else 'Your interviewer will share the video-call link.'
    gcal = _gcal_url(start=start, duration_min=duration_min, text=summary,
                     details=details, location=meeting_url or 'Video call')
    ics = _interview_ics(start=start, duration_min=duration_min, summary=summary,
                         description=details, location=meeting_url or 'Video call')
    join_en = (f'Join here: {meeting_url}' if meeting_url
               else 'Your interviewer will share the video-call link before the interview.')
    join_bm = (f'Sertai di sini: {meeting_url}' if meeting_url
               else 'Penemu duga anda akan berkongsi pautan panggilan video sebelum temu duga.')

    en_text = (
        f'Hi {en_name},\n\n'
        f'Your BrightPath Bursary Programme interview is confirmed. Here are the details:\n\n'
        f'Date & time: {when}\n'
        f'Interviewer: {rev_en}\n'
        f'{join_en}\n\n'
        f'Add to calendar: {gcal}\n\n'
        f'The interview is a video call and takes about 30 minutes. Please join with your camera '
        f'on. If you are under 18, please have a parent or guardian with you; whatever your age, '
        f'they’re welcome to join too.\n\n'
        f'Need a different time? You can reschedule or cancel from your application page in '
        f'HalaTuju ({app_link}) up to {cutoff} hours before the interview.\n\n'
        f'One note for your peace of mind: we’ll only ever ask about you and your studies. We will '
        f'never ask you for money, a bank password, or an OTP or PIN. If anyone does, it’s not us — '
        f'please tell us at {_P.email_support}.\n\n'
        f'We look forward to speaking with you.\n\n'
        f'Warm regards,\nThe BrightPath Bursary Team'
    )
    bm_text = (
        f'Salam {bm_name},\n\n'
        f'Temu duga Program Bursari BrightPath anda telah disahkan. Berikut butirannya:\n\n'
        f'Tarikh & masa: {when}\n'
        f'Penemu duga: {rev_bm}\n'
        f'{join_bm}\n\n'
        f'Tambah ke kalendar: {gcal}\n\n'
        f'Temu duga ialah panggilan video dan mengambil masa kira-kira 30 minit. Sila sertai '
        f'dengan kamera dibuka. Jika anda di bawah 18 tahun, sila pastikan ibu bapa atau penjaga '
        f'bersama anda; tidak kira umur anda, mereka juga dialu-alukan untuk menyertai.\n\n'
        f'Perlu masa lain? Anda boleh menjadual semula atau membatalkan melalui halaman permohonan '
        f'anda di HalaTuju ({app_link}) sehingga {cutoff} jam sebelum temu duga.\n\n'
        f'Satu nota untuk ketenangan anda: kami hanya akan bertanya tentang diri dan pengajian '
        f'anda. Kami tidak sekali-kali akan meminta wang, kata laluan bank, atau OTP atau PIN. Jika '
        f'sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {_P.email_support}.\n\n'
        f'Kami menantikan untuk bercakap dengan anda.\n\n'
        f'Salam hormat,\nPasukan Program Bursari BrightPath'
    )
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    def section(greeting, lead, rows, join, btn_label, body, safety, closing, signoff):
        detail_rows = ''.join(
            f'<tr><td style="padding:2px 10px 2px 0;color:#6b7280;white-space:nowrap;">{k}</td>'
            f'<td style="padding:2px 0;">{v}</td></tr>' for k, v in rows)
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 12px;">{lead}</p>'
            f'<table style="margin:0 0 16px;border-collapse:collapse;font-size:15px;"><tbody>'
            f'{detail_rows}<tr><td style="padding:2px 10px 2px 0;color:#6b7280;">{join[0]}</td>'
            f'<td style="padding:2px 0;">{join[1]}</td></tr></tbody></table>'
            f'<p style="margin:0 0 18px;">{_email_button(gcal, btn_label)}</p>'
            f'<p style="margin:0 0 14px;">{body}</p>'
            f'<p style="margin:0 0 16px;color:#6b7280;font-size:13px;">{safety}</p>'
            f'<p style="margin:0 0 14px;">{closing}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    join_cell_en = (f'<a href="{meeting_url}">{meeting_url}</a>' if meeting_url
                    else 'Your interviewer will share the link before the interview.')
    join_cell_bm = (f'<a href="{meeting_url}">{meeting_url}</a>' if meeting_url
                    else 'Penemu duga anda akan berkongsi pautan sebelum temu duga.')
    en_html = section(
        f'Hi {en_name},',
        'Your BrightPath Bursary Programme interview is confirmed. Here are the details:',
        [('Date &amp; time', when), ('Interviewer', rev_en)], ('Join here', join_cell_en),
        'Add to calendar',
        'The interview is a video call and takes about 30 minutes. Please join with your camera on. '
        'If you are under 18, please have a parent or guardian with you; whatever your age, they’re '
        'welcome to join too. Need a different time? You can reschedule or cancel from '
        f'<a href="{app_link}">your application page</a> in HalaTuju up to {cutoff} hours before the '
        'interview.',
        'One note for your peace of mind: we’ll only ever ask about you and your studies. We will '
        f'never ask you for money, a bank password, or an OTP or PIN. If anyone does, it’s not us — '
        f'please tell us at {_P.email_support}.',
        'We look forward to speaking with you.',
        'Warm regards,<br>The BrightPath Bursary Team')
    bm_html = section(
        f'Salam {bm_name},',
        'Temu duga Program Bursari BrightPath anda telah disahkan. Berikut butirannya:',
        [('Tarikh &amp; masa', when), ('Penemu duga', rev_bm)], ('Sertai di sini', join_cell_bm),
        'Tambah ke kalendar',
        'Temu duga ialah panggilan video dan mengambil masa kira-kira 30 minit. Sila sertai dengan '
        'kamera dibuka. Jika anda di bawah 18 tahun, sila pastikan ibu bapa atau penjaga bersama '
        'anda; tidak kira umur anda, mereka juga dialu-alukan untuk menyertai. Perlu masa lain? Anda '
        f'boleh menjadual semula atau membatalkan melalui <a href="{app_link}">halaman permohonan '
        f'anda</a> sehingga {cutoff} jam sebelum temu duga.',
        'Satu nota untuk ketenangan anda: kami hanya akan bertanya tentang diri dan pengajian anda. '
        f'Kami tidak sekali-kali akan meminta wang, kata laluan bank, atau OTP atau PIN. Jika sesiapa '
        f'berbuat demikian, itu bukan kami — sila beritahu kami di {_P.email_support}.',
        'Kami menantikan untuk bercakap dengan anda.',
        'Salam hormat,<br>Pasukan Program Bursari BrightPath')
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    return _send_html(to_email, 'Your BrightPath Bursary Programme interview is booked',
                      text_body, html_body, ics=ics)


def send_interview_slots_proposed_email(to_email, *, student_name, english_only=False,
                                        reviewer_name='', rescheduled=False):
    """Student notice that interview times are ready to pick — fired when the reviewer
    PROPOSES slots, so the in-app scheduler isn't invisible to students. HTML primary +
    plain-text fallback. Bilingual (EN + BM) by default; ``english_only=True`` drops the
    BM mirror (used for confidently English-preferring students). Links to the application
    page (the booking panel lives there); a Google Meet link is created automatically on
    booking. ``rescheduled=True`` is sent when the REVIEWER moved an already-booked
    interview — the intro/subject then explain the original time was released and ask the
    student to pick again. Best-effort → bool. (``reviewer_name`` kept for call compat.)"""
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'
    frontend = _P.frontend_url
    link = f'{frontend}/scholarship/application'
    subject = ('Your BrightPath Bursary Programme interview time has changed — pick a new slot'
               if rescheduled
               else 'Pick a time slot for your BrightPath Bursary Programme interview')
    intro_en = (
        'Your interviewer has had to move your interview, so the time you had booked has been '
        'released. Please choose a new date and time that suits you best.'
        if rescheduled else
        'The next step in your BrightPath Bursary Programme application is a short interview, and '
        'you can choose the date and time that suits you best.')
    intro_bm = (
        'Penemu duga anda terpaksa menukar temu duga anda, jadi masa yang anda tempah sebelum ini '
        'telah dilepaskan. Sila pilih tarikh dan masa baharu yang paling sesuai untuk anda.'
        if rescheduled else
        'Langkah seterusnya dalam permohonan Program Bursari BrightPath anda ialah temu duga ringkas, '
        'dan anda boleh memilih tarikh dan masa yang paling sesuai.')

    # ── Plain-text fallback ───────────────────────────────────────────────────
    en_text = (
        f'Hi {en_name},\n\n'
        f'{intro_en}\n\n'
        f'Choose your interview time: {link}\n\n'
        f'The interview is a video call and takes about 30 minutes. Once you pick a slot, we’ll '
        f'email you a confirmation with a Google Meet link, and send reminders one day and one '
        f'hour before.\n\n'
        f'If none of them suit you, you can ask for other times on that same page — your '
        f'interviewer will then suggest new ones.\n\n'
        f'For your peace of mind: we’ll only ever ask about you and your studies. We will never '
        f'ask you for money, your password, or an OTP or PIN. If anyone claiming to represent the '
        f'BrightPath Bursary Programme does, it isn’t us.\n\n'
        f'Warm regards,\nThe BrightPath Bursary Team'
    )
    bm_text = (
        f'Salam {bm_name},\n\n'
        f'{intro_bm}\n\n'
        f'Pilih masa temu duga anda: {link}\n\n'
        f'Temu duga dijalankan melalui panggilan video dan mengambil masa kira-kira 30 minit. '
        f'Setelah anda memilih slot, kami akan menghantar e-mel pengesahan dengan pautan Google '
        f'Meet, serta peringatan satu hari dan satu jam sebelumnya.\n\n'
        f'Jika tiada yang sesuai, anda boleh meminta masa lain pada halaman yang sama — penemu '
        f'duga anda kemudian akan mencadangkan masa baharu.\n\n'
        f'Untuk ketenangan anda: kami hanya akan bertanya tentang diri dan pengajian anda. Kami '
        f'tidak sekali-kali akan meminta wang, kata laluan, atau OTP atau PIN. Jika sesiapa yang '
        f'mendakwa mewakili Program Bursari BrightPath berbuat demikian, itu bukan kami.\n\n'
        f'Salam hormat,\nPasukan Program Bursari BrightPath'
    )
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    # ── HTML primary (EN then BM) ─────────────────────────────────────────────
    def section(greeting, intro, btn_label, detail, alt, safety, signoff):
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 18px;">{intro}</p>'
            f'<p style="margin:0 0 18px;">{_email_button(link, btn_label)}</p>'
            f'<p style="margin:0 0 14px;">{detail}</p>'
            f'<p style="margin:0 0 18px;">{alt}</p>'
            f'<p style="margin:0 0 18px;color:#6b7280;font-size:13px;">{safety}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    en_html = section(
        f'Hi {en_name},',
        intro_en,
        'Choose your interview time',
        'The interview is a video call and takes about 30 minutes. Once you pick a slot, we’ll '
        'email you a confirmation with a Google Meet link, and send reminders one day and one '
        'hour before.',
        'If none of them suit you, you can ask for other times on that same page — your '
        'interviewer will then suggest new ones.',
        'For your peace of mind: we’ll only ever ask about you and your studies. We will never ask '
        'you for money, your password, or an OTP or PIN. If anyone claiming to represent the B40 '
        'Assistance Programme does, it isn’t us.',
        'Warm regards,<br>The BrightPath Bursary Team')
    bm_html = section(
        f'Salam {bm_name},',
        intro_bm,
        'Pilih masa temu duga anda',
        'Temu duga dijalankan melalui panggilan video dan mengambil masa kira-kira 30 minit. '
        'Setelah anda memilih slot, kami akan menghantar e-mel pengesahan dengan pautan Google '
        'Meet, serta peringatan satu hari dan satu jam sebelumnya.',
        'Jika tiada yang sesuai, anda boleh meminta masa lain pada halaman yang sama — penemu duga '
        'anda kemudian akan mencadangkan masa baharu.',
        'Untuk ketenangan anda: kami hanya akan bertanya tentang diri dan pengajian anda. Kami '
        'tidak sekali-kali akan meminta wang, kata laluan, atau OTP atau PIN. Jika sesiapa yang '
        'mendakwa mewakili Program Bursari BrightPath berbuat demikian, itu bukan kami.',
        'Salam hormat,<br>Pasukan Program Bursari BrightPath')

    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)
    return _send_html(to_email, subject, text_body, html_body)


def send_interview_reminder_email(to_email, *, student_name, start, meeting_url='', when='1day',
                                  english_only=False):
    """Student reminder (1 day / 1 hour before). HTML primary + plain-text fallback. Bilingual
    (EN+BM) by default; ``english_only=True`` drops the BM mirror. Best-effort."""
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'
    whenfmt = _fmt_myt(start)
    soon_en = 'tomorrow' if when == '1day' else 'in about an hour'
    soon_bm = 'esok' if when == '1day' else 'dalam kira-kira sejam'

    # ── Plain-text fallback ───────────────────────────────────────────────────
    en_text = (
        f'Hi {en_name},\n\n'
        f'A reminder that your BrightPath Bursary Programme interview is {soon_en}:\n\n'
        f'• {whenfmt}\n'
        f'{_join_line(meeting_url, "en")}\n'
        f'Please be on camera and ready a few minutes early. See you soon.\n\n'
        f'Warm regards,\nThe BrightPath Bursary Team'
    )
    bm_text = (
        f'Salam {bm_name},\n\n'
        f'Peringatan bahawa temu duga Program Bursari BrightPath anda adalah {soon_bm}:\n\n'
        f'• {whenfmt}\n'
        f'{_join_line(meeting_url, "bm")}\n'
        f'Sila buka kamera dan bersedia beberapa minit lebih awal. Jumpa tidak lama lagi.\n\n'
        f'Salam hormat,\nPasukan Program Bursari BrightPath'
    )
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    # ── HTML primary ──────────────────────────────────────────────────────────
    if meeting_url:
        join_en_html = _email_button(meeting_url, 'Join the video call')
        join_bm_html = _email_button(meeting_url, 'Sertai panggilan video')
    else:
        join_en_html = 'Your interviewer will share the video-call link before the interview.'
        join_bm_html = 'Penemu duga anda akan berkongsi pautan panggilan video sebelum temu duga.'

    def section(greeting, lead, join_html, footer, signoff):
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 10px;">{lead}</p>'
            f'<p style="margin:0 0 6px;font-weight:600;">{whenfmt}</p>'
            f'<p style="margin:0 0 18px;">{join_html}</p>'
            f'<p style="margin:0 0 18px;">{footer}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    en_html = section(
        f'Hi {en_name},',
        f'A reminder that your BrightPath Bursary Programme interview is {soon_en}:',
        join_en_html,
        'Please be on camera and ready a few minutes early. See you soon.',
        'Warm regards,<br>The BrightPath Bursary Team')
    bm_html = section(
        f'Salam {bm_name},',
        f'Peringatan bahawa temu duga Program Bursari BrightPath anda adalah {soon_bm}:',
        join_bm_html,
        'Sila buka kamera dan bersedia beberapa minit lebih awal. Jumpa tidak lama lagi.',
        'Salam hormat,<br>Pasukan Program Bursari BrightPath')
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    subj = ('Reminder: your B40 interview is tomorrow' if when == '1day'
            else 'Reminder: your B40 interview is in 1 hour')
    return _send_html(to_email, subj, text_body, html_body)


def send_interview_cancelled_email(to_email, *, student_name, english_only=False):
    """Confirmation to the student that *they* cancelled their interview (this notice is sent
    on every cancel, and a student-initiated cancel is the common case). HTML primary +
    plain-text fallback. Bilingual (EN+BM) by default; ``english_only=True`` drops the BM
    mirror. Best-effort."""
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'

    # ── Plain-text fallback (the owner-approved copy) ─────────────────────────
    en_text = (
        f'Hi {en_name},\n\n'
        f"This confirms that you've cancelled your interview for the BrightPath Bursary Programme, so "
        f'the time you had booked is now released.\n\n'
        f'Your application is still active — cancelling the interview doesn\'t affect it. Your '
        f"interviewer will propose some alternative times, and you're welcome to choose one "
        f"whenever you're ready, if you'd like to take this forward.\n\n"
        f"If you didn't mean to cancel, or you have any questions, just reply to this email and "
        f"we'll help you sort it out.\n\n"
        f'One note for your peace of mind: we\'ll only ever ask about you and your studies. We '
        f'will never ask you for money, a bank password, or an OTP or PIN. If anyone does, it\'s '
        f'not us — please tell us at {_P.email_support}.\n\n'
        f'Warm regards,\nThe BrightPath Bursary Team'
    )
    bm_text = (
        f'Salam {bm_name},\n\n'
        f'E-mel ini mengesahkan bahawa anda telah membatalkan temu duga Program Bursari BrightPath anda, '
        f'jadi masa yang anda tempah sebelum ini kini dilepaskan.\n\n'
        f'Permohonan anda masih aktif — membatalkan temu duga tidak menjejaskannya. Penemu duga '
        f'anda akan mencadangkan beberapa masa alternatif, dan anda dialu-alukan untuk memilih satu '
        f'bila-bila masa anda bersedia, jika anda ingin meneruskannya.\n\n'
        f'Jika anda tidak berniat untuk membatalkannya, atau anda mempunyai sebarang pertanyaan, '
        f'balas sahaja e-mel ini dan kami akan membantu anda.\n\n'
        f'Satu perkara untuk ketenangan fikiran anda: kami hanya akan bertanya tentang anda dan '
        f'pengajian anda. Kami tidak akan sekali-kali meminta wang, kata laluan bank, atau OTP atau '
        f'PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {_P.email_support}.\n\n'
        f'Salam hormat,\nPasukan Program Bursari BrightPath'
    )
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    # ── HTML primary ──────────────────────────────────────────────────────────
    def section(greeting, p_confirm, p_active, p_reply, safety, signoff):
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 14px;">{p_confirm}</p>'
            f'<p style="margin:0 0 14px;">{p_active}</p>'
            f'<p style="margin:0 0 18px;">{p_reply}</p>'
            f'<p style="margin:0 0 18px;color:#6b7280;font-size:13px;">{safety}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    en_html = section(
        f'Hi {en_name},',
        "This confirms that you've cancelled your interview for the BrightPath Bursary Programme, so the "
        'time you had booked is now released.',
        "Your application is still active — cancelling the interview doesn’t affect it. Your interviewer "
        "will propose some alternative times, and you’re welcome to choose one whenever you’re ready, if "
        "you’d like to take this forward.",
        "If you didn’t mean to cancel, or you have any questions, just reply to this email and we’ll help "
        "you sort it out.",
        f'One note for your peace of mind: we’ll only ever ask about you and your studies. We will never '
        f'ask you for money, a bank password, or an OTP or PIN. If anyone does, it’s not us — please tell '
        f'us at {_P.email_support}.',
        'Warm regards,<br>The BrightPath Bursary Team')
    bm_html = section(
        f'Salam {bm_name},',
        'E-mel ini mengesahkan bahawa anda telah membatalkan temu duga Program Bursari BrightPath anda, jadi '
        'masa yang anda tempah sebelum ini kini dilepaskan.',
        'Permohonan anda masih aktif — membatalkan temu duga tidak menjejaskannya. Penemu duga anda akan '
        'mencadangkan beberapa masa alternatif, dan anda dialu-alukan untuk memilih satu bila-bila masa '
        'anda bersedia, jika anda ingin meneruskannya.',
        'Jika anda tidak berniat untuk membatalkannya, atau anda mempunyai sebarang pertanyaan, balas '
        'sahaja e-mel ini dan kami akan membantu anda.',
        f'Satu perkara untuk ketenangan fikiran anda: kami hanya akan bertanya tentang anda dan pengajian '
        f'anda. Kami tidak akan sekali-kali meminta wang, kata laluan bank, atau OTP atau PIN. Jika '
        f'sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {_P.email_support}.',
        'Salam hormat,<br>Pasukan Program Bursari BrightPath')
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    return _send_html(to_email, "You've cancelled your BrightPath Bursary Programme interview",
                      text_body, html_body)


def send_interview_released_email(to_email, *, student_name, english_only=False):
    """Notice to the student when the interview is released because their INTERVIEWER
    changed (an admin unassigned the reviewer) — distinct from the student-initiated
    cancellation above (which says 'you cancelled'). Reassures them nothing is wrong and
    they need do nothing until a new interviewer proposes fresh times. HTML primary +
    plain-text fallback; bilingual (EN+BM) unless ``english_only``. Best-effort."""
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'

    en_text = (
        f'Hi {en_name},\n\n'
        f"There's been a change to who will be interviewing you for the BrightPath Bursary "
        f"Programme, so the interview time you'd booked has been released.\n\n"
        f"Your application is still active and this doesn't affect it. A new interviewer will "
        f"be assigned and will propose fresh times for you to choose from — there's nothing you "
        f"need to do right now.\n\n"
        f"If you have any questions, just reply to this email and we'll help.\n\n"
        f"One note for your peace of mind: we'll only ever ask about you and your studies. We "
        f"will never ask you for money, a bank password, or an OTP or PIN. If anyone does, it's "
        f"not us — please tell us at {_P.email_support}.\n\n"
        f'Warm regards,\nThe BrightPath Bursary Team'
    )
    bm_text = (
        f'Salam {bm_name},\n\n'
        f'Terdapat perubahan pada penemu duga yang akan menemu duga anda untuk Program Bursari '
        f'BrightPath, jadi masa temu duga yang anda tempah sebelum ini kini dilepaskan.\n\n'
        f'Permohonan anda masih aktif dan perkara ini tidak menjejaskannya. Seorang penemu duga '
        f'baharu akan ditugaskan dan akan mencadangkan masa baharu untuk anda pilih — tiada apa '
        f'yang perlu anda lakukan sekarang.\n\n'
        f'Jika anda mempunyai sebarang pertanyaan, balas sahaja e-mel ini dan kami akan membantu.\n\n'
        f'Satu perkara untuk ketenangan fikiran anda: kami hanya akan bertanya tentang anda dan '
        f'pengajian anda. Kami tidak akan sekali-kali meminta wang, kata laluan bank, atau OTP atau '
        f'PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {_P.email_support}.\n\n'
        f'Salam hormat,\nPasukan Program Bursari BrightPath'
    )
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    def section(greeting, p_confirm, p_active, p_reply, safety, signoff):
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 14px;">{p_confirm}</p>'
            f'<p style="margin:0 0 14px;">{p_active}</p>'
            f'<p style="margin:0 0 18px;">{p_reply}</p>'
            f'<p style="margin:0 0 18px;color:#6b7280;font-size:13px;">{safety}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    en_html = section(
        f'Hi {en_name},',
        "There’s been a change to who will be interviewing you for the BrightPath Bursary "
        "Programme, so the interview time you’d booked has been released.",
        "Your application is still active and this doesn’t affect it. A new interviewer will be "
        "assigned and will propose fresh times for you to choose from — there’s nothing you need "
        "to do right now.",
        "If you have any questions, just reply to this email and we’ll help.",
        f'One note for your peace of mind: we’ll only ever ask about you and your studies. We will '
        f'never ask you for money, a bank password, or an OTP or PIN. If anyone does, it’s not us — '
        f'please tell us at {_P.email_support}.',
        'Warm regards,<br>The BrightPath Bursary Team')
    bm_html = section(
        f'Salam {bm_name},',
        'Terdapat perubahan pada penemu duga yang akan menemu duga anda untuk Program Bursari '
        'BrightPath, jadi masa temu duga yang anda tempah sebelum ini kini dilepaskan.',
        'Permohonan anda masih aktif dan perkara ini tidak menjejaskannya. Seorang penemu duga '
        'baharu akan ditugaskan dan akan mencadangkan masa baharu untuk anda pilih — tiada apa yang '
        'perlu anda lakukan sekarang.',
        'Jika anda mempunyai sebarang pertanyaan, balas sahaja e-mel ini dan kami akan membantu.',
        f'Satu perkara untuk ketenangan fikiran anda: kami hanya akan bertanya tentang anda dan '
        f'pengajian anda. Kami tidak akan sekali-kali meminta wang, kata laluan bank, atau OTP atau '
        f'PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {_P.email_support}.',
        'Salam hormat,<br>Pasukan Program Bursari BrightPath')
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    return _send_html(to_email, 'Your BrightPath Bursary Programme interview time has been released',
                      text_body, html_body)


def _send_plain(to_email, subject, body):
    if not to_email:
        return False
    try:
        EmailMessage(subject=subject, body=body,
                     from_email=_P.interview_from,
                     to=[to_email], reply_to=[_P.interview_reply_to],
                     headers=_interview_unsub_headers()).send()
        return True
    except Exception:
        logger.warning('Failed to send reviewer interview email to %s', to_email, exc_info=True)
        return False


def send_reviewer_interview_booked_email(to_email, *, reviewer_name, applicant_name, start,
                                         meeting_url='', ref='', duration_min=None,
                                         calendar_invite_sent=False):
    """Reviewer notice that a student booked one of their proposed times. Plain EN.

    Calendar: when the Google Meet/Calendar integration is on, both parties are added to one
    auto-created event (calendar_invite_sent=True) — so we DON'T offer a manual 'add to
    calendar' link (it would double-book). When it's off, no event exists, so we include an
    'Add to your calendar' Google link so the reviewer always ends up with the time held."""
    applicant = applicant_name or 'An applicant'
    details = [f'When: {_fmt_myt(start)}']
    if meeting_url:
        details.append(f'Meet link: {meeting_url}')
    if calendar_invite_sent:
        calendar_line = "It's on your calendar (a Google invite has been sent) and in their record."
    else:
        gcal = _gcal_url(start=start, duration_min=duration_min or 30,
                         text=f'B40 interview — {applicant}',
                         details='BrightPath Bursary Programme interview.', location=meeting_url or '')
        calendar_line = (
            "The booking is in their record. Add it to your calendar so you don't lose the time:\n"
            f'Add to your calendar:\n{gcal}')
    body = (
        f'Dear {reviewer_name or "there"},\n\n'
        f'{applicant} has booked their B40 interview with you.\n\n'
        + '\n'.join(details) + '\n\n'
        f'{calendar_line}\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _send_plain(to_email, _reviewer_subject('Interview booked', ref), body)


def send_reviewer_interview_reminder_email(to_email, *, reviewer_name, applicant_name, start,
                                           meeting_url='', when='1day', ref='', verdict_due=''):
    """Reviewer reminder (1 day / 1 hour before). Plain EN. A nudge only — no calendar link,
    since the time was added when it was booked. ``verdict_due`` (a date string) adds a heads-up
    that the verdict for this applicant is due by then — the interview and verdict are different
    clocks, so a reviewer juggling cases sees both (TD-131)."""
    soon = 'tomorrow' if when == '1day' else 'in about an hour'
    details = [f'When: {_fmt_myt(start)}']
    if meeting_url:
        details.append(f'Meet link: {meeting_url}')
    verdict_line = (f'After the interview, please record your verdict — it is due by {verdict_due}.\n\n'
                    if verdict_due else '')
    body = (
        f'Dear {reviewer_name or "there"},\n\n'
        f'Your B40 interview with {applicant_name or "an applicant"} is {soon}.\n\n'
        + '\n'.join(details) + '\n\n'
        f'{verdict_line}'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    base = ('Reminder: your interview is tomorrow' if when == '1day'
            else 'Reminder: your interview is in 1 hour')
    return _send_plain(to_email, _reviewer_subject(base, ref), body)


def send_reviewer_alternatives_requested_email(to_email, *, reviewer_name, applicant_name,
                                               note='', ref=''):
    """Reviewer notice that the student said none of the proposed times work and wants other
    options. Routes the request to the right person (vs a reply lost in a shared inbox). Plain EN."""
    note_block = f'\nWhat they said:\n  "{note}"\n' if note else ''
    body = (
        f'Dear {reviewer_name or "there"},\n\n'
        f'{applicant_name or "An applicant"} says none of the interview times you proposed will '
        f'work, and has asked for other options.\n'
        f'{note_block}\n'
        f'Open their record and use "Propose alternative times" to offer a fresh set — '
        f"they'll be emailed automatically.\n\n"
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _send_plain(to_email, _reviewer_subject('Applicant needs different interview times', ref), body)


def send_reviewer_student_message_email(to_email, *, reviewer_name, applicant_name,
                                        message, ref='', interview_start=None):
    """Reviewer notice that the student sent them a message (the always-open channel —
    fires in any interview state, INCLUDING inside the reschedule cutoff, e.g. "I'm
    running late" an hour before the call). Plain EN; the booked interview time is
    included when known so the reviewer can judge urgency from the email alone."""
    when_line = ''
    if interview_start is not None:
        when_line = f'Their interview is booked for {_fmt_myt(interview_start)}.\n\n'
    body = (
        f'Dear {reviewer_name or "there"},\n\n'
        f'{applicant_name or "An applicant"} sent you a message about their interview:\n\n'
        f'  "{message}"\n\n'
        f'{when_line}'
        f'If it needs a reply, open their record — you can propose new times, reschedule, '
        f'or reach them through the contact details there.\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _send_plain(to_email, _reviewer_subject('Message from applicant', ref), body)


def send_reviewer_interview_cancelled_email(to_email, *, reviewer_name, applicant_name, ref='', reason=''):
    """Reviewer notice that a student cancelled. Plain EN. Includes the student's reason if given."""
    reason_line = f'Reason they gave: "{reason.strip()}"\n\n' if (reason or '').strip() else ''
    body = (
        f'Dear {reviewer_name or "there"},\n\n'
        f'{applicant_name or "An applicant"} has cancelled their booked B40 interview.\n\n'
        f'{reason_line}'
        f'Their application is still open — only the interview slot was released. When you\'re '
        f'ready, open their record and use "Propose alternative times" to offer new ones.\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _send_plain(to_email, _reviewer_subject('Applicant cancelled their interview', ref), body)


def send_reviewer_verdict_due_email(to_email, *, reviewer_name, applicant_name, ref='',
                                    due_by='', overdue=False):
    """TD-131: nudge the assigned reviewer that a verdict is due soon / now overdue. Plain EN,
    consistent reviewer style (Dear / dashboard CTA / {ref} subject / BrightPath Bursary Team)."""
    applicant = applicant_name or 'an applicant'
    if overdue:
        lead = (f'Your verdict for {applicant} is overdue'
                + (f' — it was due {due_by}' if due_by else '') + '.')
        base = 'Verdict overdue'
    else:
        lead = (f'Your verdict for {applicant} is due soon'
                + (f' — by {due_by}' if due_by else '') + '.')
        base = 'Verdict due soon'
    body = (
        f'Dear {reviewer_name or "there"},\n\n'
        f'{lead}\n\n'
        f'Please open their record, complete your review, and record your verdict.\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _send_plain(to_email, _reviewer_subject(base, ref), body)


def send_super_verdict_escalation_email(to_email, *, applicant_name, ref='', reviewer_name='',
                                        due_by=''):
    """TD-131: escalate an overdue verdict to a super-admin — the assigned reviewer hasn't recorded
    a verdict well past the SLA. Plain EN."""
    who = reviewer_name or 'the assigned reviewer'
    body = (
        f'Hi,\n\n'
        f'A B40 verdict is overdue and needs attention.\n\n'
        f'Reference: {ref or "—"}\n'
        f'Applicant: {applicant_name or "—"}\n'
        f'Assigned reviewer: {who}\n'
        + (f'Was due: {due_by}\n' if due_by else '')
        + f'\n{who} has not recorded a verdict past the review deadline. You may want to follow up, '
        f'or reassign the case from the admin console.\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _send_plain(to_email, _reviewer_subject('Overdue verdict needs attention', ref), body)


def _run_month_label(run):
    """The month a run pays for, e.g. 'July 2026' (falls back to the payment date's month)."""
    d = getattr(run, 'period_month', None) or getattr(run, 'payment_date', None)
    return d.strftime('%B %Y') if d else ''


def _run_totals(run):
    """(included-student count, total amount) for a run."""
    from decimal import Decimal
    included = [i for i in run.items.all() if i.included]
    return len(included), sum((i.amount for i in included), Decimal('0'))


def _rm_amount(v):
    """Whole-ringgit display: Decimal('200.00') → '200' (a genuine .50 is kept)."""
    try:
        return f'{v.normalize():f}'
    except Exception:
        return str(v)


def send_payment_countersign_email(run):
    """Payments (owner 2026-07-16): when the maker signs a run, tell the organisation admin(s)
    it awaits their countersignature. Internal officer email (English); best-effort — never
    raises, a failure never blocks the signature."""
    from apps.courses.models import PartnerAdmin
    frontend = _P.frontend_url
    link = f'{frontend}/admin/payments/{run.id}'
    month = _run_month_label(run)
    n, total = _run_totals(run)
    vircle_to = getattr(settings, 'VIRCLE_PAYMENTS_EMAIL', '')
    subject = f'Payment run {run.reference} awaits your countersignature'
    sent = False
    approvers = PartnerAdmin.objects.filter(
        owning_organisation=run.organisation, role='org_admin', is_active=True)
    for approver in approvers:
        if not (approver.email or '').strip():
            continue
        body = (
            f'Dear {(approver.name or "").strip() or "Organisation Admin"},\n\n'
            f'{run.admin_signed_name} has signed payment run {run.reference}, paying the '
            f'BrightPath Bursary for {month}:\n\n'
            f'    Students:      {n}\n'
            f'    Total:         RM{_rm_amount(total)}\n'
            f'    Payment date:  {run.payment_date:%d/%m/%Y}\n\n'
            f'It now needs your countersignature. Once you countersign, the payment '
            f'instruction (with the payment file attached) will be emailed to Vircle at '
            f'{vircle_to}.\n\n'
            f'Review and countersign here: {link}\n\n'
            f'If anything looks wrong, do not countersign — editing the run returns it to '
            f'draft and clears the first signature, or ask {run.admin_signed_name} to '
            f'correct it.\n\n'
            f'The HalaTuju Team'
        )
        try:
            EmailMessage(subject=subject, body=body,
                         from_email=settings.DEFAULT_FROM_EMAIL,
                         to=[approver.email]).send()
            sent = True
        except Exception:
            logger.warning('Failed to send countersign notification for run %s to %s',
                           run.reference, approver.email, exc_info=True)
    return sent


def send_payment_finance_check_email(run):
    """Payments / Sprint 14: when the maker signs a run in an organisation that HAS an active
    finance admin, the run goes to finance for the check before the approver ever sees it — so
    this email replaces the countersign one at that moment (``payments.sign`` picks). Internal
    officer email (English); best-effort — never raises, a failure never blocks the signature.

    Deliberately carries NO programme-name literal (conventions rule 2): it is addressed to the
    organisation's own finance staff about their own run, so the reference and the month say
    everything the recipient needs. (The sibling countersign email predates that rule.)"""
    from apps.courses.models import PartnerAdmin
    frontend = _P.frontend_url
    link = f'{frontend}/admin/payments/{run.id}'
    month = _run_month_label(run)
    n, total = _run_totals(run)
    subject = f'Payment run {run.reference} awaits your finance check'
    sent = False
    checkers = PartnerAdmin.objects.filter(
        owning_organisation=run.organisation, role='finance', is_active=True)
    for checker in checkers:
        if not (checker.email or '').strip():
            continue
        body = (
            f'Dear {(checker.name or "").strip() or "Finance Admin"},\n\n'
            f'{run.admin_signed_name} has signed payment run {run.reference}, covering '
            f'{month}:\n\n'
            f'    Students:      {n}\n'
            f'    Total:         RM{_rm_amount(total)}\n'
            f'    Payment date:  {run.payment_date:%d/%m/%Y}\n\n'
            f'It now needs your finance check. The run cannot be countersigned — and no money '
            f'moves — until you have checked it.\n\n'
            f'Review the list and the payment file, then sign here: {link}\n\n'
            f'If anything looks wrong, do not sign. Ask {run.admin_signed_name} to correct it; '
            f'editing the run returns it to draft and clears every signature collected so far, '
            f'including yours.\n\n'
            f'The HalaTuju Team'
        )
        try:
            EmailMessage(subject=subject, body=body,
                         from_email=settings.DEFAULT_FROM_EMAIL,
                         to=[checker.email]).send()
            sent = True
        except Exception:
            logger.warning('Failed to send finance-check notification for run %s to %s',
                           run.reference, checker.email, exc_info=True)
    return sent


def send_vircle_activation_email(rows, csv_text=None):
    """The 48h activation request to Vircle: the accounts installed but not yet activated, with a
    CSV attached and a Bcc reference copy. Recipient = VIRCLE_ACTIVATION_EMAIL, else the payments
    contact. Best-effort; returns True on send, False if disabled / empty / send failed."""
    recipient = ((getattr(settings, 'VIRCLE_ACTIVATION_EMAIL', '') or '').strip()
                 or (getattr(settings, 'VIRCLE_PAYMENTS_EMAIL', '') or '').strip())
    if not recipient or not rows:
        return False
    from django.utils import timezone

    from . import vircle
    if csv_text is None:
        csv_text = vircle.activation_csv_text(rows)
    today = timezone.localdate()
    n = len(rows)
    # Reference copy (owner A+B): Bcc a mailbox, and the command also files the CSV to Drive.
    bcc = [e for e in [((getattr(settings, 'VIRCLE_ACTIVATION_BCC', '') or '')
                        or (getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or '')).strip()] if e]
    listing = '\n'.join(
        f"  {i}. {r['name']} — NRIC {r['nric']} — eWallet ID {r['ewallet']} — "
        f"mobile {r['phone']} — installed {r['installed_on']}"
        for i, r in enumerate(rows, 1))
    body = (
        'Dear Vircle team,\n\n'
        'The student(s) below have installed the BrightPath Bursary eWallet and completed their '
        'account details, but their account(s) are not yet activated on your side. Please activate '
        'them so we can proceed with disbursement.\n\n'
        f'Awaiting activation: {n}  (full details in the attached CSV)\n\n'
        f'{listing}\n\n'
        'Once you activate an account we remove it from this list. This reminder is sent every '
        '48 hours for any accounts still awaiting activation.\n\n'
        'Thank you,\n'
        'The BrightPath Bursary Team'
    )
    try:
        msg = EmailMessage(
            subject=(f'BrightPath Bursary — eWallet activation request '
                     f'({n} account{"" if n == 1 else "s"}) — {today:%d %B %Y}'),
            body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient], bcc=bcc)
        msg.attach(f'vircle-activation-{today:%Y-%m-%d}.csv', csv_text, 'text/csv')
        msg.send()
        return True
    except Exception:
        logger.warning('Failed to send the Vircle activation email', exc_info=True)
        return False


def send_payment_run_email(run):
    """Payments D7 — on countersignature, email Vircle the payment instruction with the run's
    CSV attached. Enabled when ``VIRCLE_PAYMENTS_EMAIL`` is set (default gokula@vircle.com);
    best-effort — a failure never breaks the completed run (the DB is the record)."""
    recipient = (getattr(settings, 'VIRCLE_PAYMENTS_EMAIL', '') or '').strip()
    if not recipient:
        return False
    from . import sheets
    month = _run_month_label(run)
    n, total = _run_totals(run)
    body = (
        'Dear Vircle team,\n\n'
        f'Please find attached the payment instruction for the BrightPath Bursary '
        f'for {month}.\n\n'
        f'    Run reference:  {run.reference}\n'
        f'    Payment date:   {run.payment_date:%d/%m/%Y}\n'
        f'    Students:       {n}\n'
        f'    Total:          RM{_rm_amount(total)}\n\n'
        "The attached file lists each student's Wallet ID, NRIC, full name and the amount to "
        "credit. Kindly credit each student's Vircle wallet on the payment date, and reply "
        'to this email to confirm once the payments have been processed.\n\n'
        f'This run was signed by {run.admin_signed_name} and countersigned by '
        f'{run.org_admin_signed_name} of the BrightPath Bursary programme.\n\n'
        'Thank you,\n'
        'The BrightPath Bursary Team'
    )
    # Owner 2026-07-17 (approver's ask): CC the countersigning org admin so the
    # organisation holds its own copy of exactly what was sent to Vircle.
    cc = [e for e in [(run.org_admin_signed_email or '').strip()] if e]
    try:
        msg = EmailMessage(
            subject=f'BrightPath Bursary — payment instruction {run.reference} ({month})',
            body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient], cc=cc)
        msg.attach(f'{run.reference}.csv', sheets.payment_csv_text(run), 'text/csv')
        msg.send()
        return True
    except Exception:
        logger.warning('Failed to send the Vircle payment email for run %s',
                       run.reference, exc_info=True)
        return False
