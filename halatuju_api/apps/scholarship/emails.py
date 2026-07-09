"""
Trilingual emails for the BrightPath Bursary Programme.

Phase 1 uses email (every HalaTuju account has a verified Google address).
WhatsApp is a Phase 2 enhancement.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives, send_mail

# Topical reply-to aliases (all land in the same Workspace inbox; they just route
# replies to a sensible address and keep things filterable). From-address is the
# global DEFAULT_FROM_EMAIL (info@halatuju.xyz) so every reply is deliverable.
INTERVIEW_REPLY_TO = 'interview@halatuju.xyz'
SPONSOR_REPLY_TO = 'sponsor@halatuju.xyz'
# All interview comms send FROM (and reply to) the interview alias, so the whole thread is
# self-contained on interview@ rather than the global info@ sender.
INTERVIEW_FROM_EMAIL = 'interview@halatuju.xyz'

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
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    link = f"{frontend}/scholarship/application"
    fmt = {'name': name, 'programme': programme_name, 'link': link, **(extra or {})}
    try:
        send_mail(
            subject=subjects[lang].format(programme=programme_name),
            message=bodies[lang].format(**fmt),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
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
# offer/acceptance. Good news + how support is paid (a monthly payment arrangement) + a formal
# offer & bursary contract to follow. NO bank-details ask (an alternative payment arrangement is
# being worked out; documentation pending) — and therefore NO call-to-action button. Deliberately
# states NO amount (the formal offer carries the figure) and NO sponsor identity (two-way
# anonymity). From info@, reply-to help@. Owner-cleared wording 2026-06-30.
AWARD_OFFER_SUBJECTS = {
    'en': 'Good news about your BrightPath Bursary application 🎓',
    'ms': 'Berita baik tentang permohonan Biasiswa BrightPath anda 🎓',
    'ta': 'உங்கள் BrightPath Bursary விண்ணப்பம் பற்றிய நல்ல செய்தி 🎓',
}
AWARD_OFFER_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "We're delighted to share some good news. Your application to the BrightPath Bursary "
        "Programme has been successful — you have been selected to receive financial support for "
        "your studies.\n\n"
        "Your support will be provided through a monthly payment arrangement. We're finalising the "
        "details now, and we'll send you a formal offer and bursary contract very soon, along with "
        "the simple steps to accept it.\n\n"
        "There's nothing you need to do right now — please look out for our next message.\n\n"
        "If you have any questions in the meantime, reply to this email or contact us at {support}.\n\n"
        "Warm congratulations,\nThe BrightPath Bursary Team"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Kami gembira berkongsi berita baik. Permohonan anda ke Program Biasiswa BrightPath telah "
        "berjaya — anda telah dipilih untuk menerima bantuan kewangan bagi pengajian anda.\n\n"
        "Bantuan anda akan disalurkan melalui aturan pembayaran bulanan. Kami sedang memuktamadkan "
        "butirannya sekarang, dan kami akan menghantar tawaran rasmi dan kontrak biasiswa kepada anda "
        "tidak lama lagi, berserta langkah mudah untuk menerimanya.\n\n"
        "Tiada apa-apa yang perlu anda lakukan buat masa ini — sila tunggu mesej kami yang seterusnya.\n\n"
        "Jika ada sebarang pertanyaan, balas e-mel ini atau hubungi kami di {support}.\n\n"
        "Tahniah,\nPasukan Biasiswa BrightPath"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "ஒரு நல்ல செய்தியைப் பகிர்வதில் மகிழ்ச்சி அடைகிறோம். BrightPath Bursary திட்டத்திற்கான உங்கள் "
        "விண்ணப்பம் வெற்றிபெற்றுள்ளது — உங்கள் படிப்பிற்கான நிதியுதவியைப் பெற நீங்கள் தேர்ந்தெடுக்கப்பட்டுள்ளீர்கள்.\n\n"
        "உங்கள் உதவி மாதாந்திரக் கட்டண முறையில் வழங்கப்படும். அதன் விவரங்களை நாங்கள் இப்போது இறுதி செய்து "
        "வருகிறோம்; விரைவில் முறையான வழங்கல் (offer) மற்றும் உதவித்தொகை ஒப்பந்தத்தை (bursary contract), அதை "
        "ஏற்கும் எளிய படிகளுடன் உங்களுக்கு அனுப்புவோம்.\n\n"
        "இப்போதைக்கு நீங்கள் எதுவும் செய்ய வேண்டியதில்லை — எங்கள் அடுத்த செய்திக்காகக் காத்திருங்கள்.\n\n"
        "ஏதேனும் கேள்விகள் இருந்தால், இந்த மின்னஞ்சலுக்குப் பதிலளிக்கவும் அல்லது {support} இல் "
        "எங்களைத் தொடர்புகொள்ளவும்.\n\n"
        "இதயப்பூர்வ வாழ்த்துகள்,\nBrightPath Bursary குழு"
    ),
}


# The key phrases rendered BOLD in the HTML (how support is paid + the offer/contract to
# follow), per language. Each must be an exact substring of the body above. There is no
# call-to-action button on this email — it asks nothing of the student yet.
_BOLD_PHRASES = {
    'en': ['monthly payment arrangement', 'formal offer and bursary contract'],
    'ms': ['aturan pembayaran bulanan', 'tawaran rasmi dan kontrak biasiswa'],
    'ta': ['மாதாந்திரக் கட்டண முறையில்',
           'முறையான வழங்கல் (offer) மற்றும் உதவித்தொகை ஒப்பந்தத்தை (bursary contract)'],
}


def _award_offer_html(text_body, lang):
    """HTML for the award good-news email: paragraphs, with the key phrases (how support is
    paid + the offer/contract to follow) in BOLD and the sign-off team name (the line after the
    salutation in the final paragraph) bolded. No call-to-action button — the email asks nothing
    of the student yet. Falls back gracefully: a phrase that isn't found is left un-bolded."""
    import html as _h
    phrases = _BOLD_PHRASES.get(lang, [])

    def _emphasise(escaped):
        for ph in phrases:
            if ph:
                escaped = escaped.replace(_h.escape(ph), f'<strong>{_h.escape(ph)}</strong>')
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
    return _html_email_shell(''.join(blocks))


def send_award_offer_email(to_email, applicant_name, lang='en'):
    """Award good-news email: a sponsor has committed (status 'awarded'). Tells the student the
    application succeeded, that support is paid as a monthly arrangement, and that a formal offer
    + bursary contract will follow. NO bank-details ask, NO call-to-action, NO amount, NO sponsor
    identity. HTML (key phrases BOLD) + plain-text fallback, from info@, reply-to help@."""
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    fmt = {'name': name, 'support': SUPPORT_EMAIL}
    subject = AWARD_OFFER_SUBJECTS[lang]
    text_body = AWARD_OFFER_BODIES[lang].format(**fmt)
    return _send_html(
        to_email, subject, text_body, _award_offer_html(text_body, lang),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
        reply_to=[SUPPORT_EMAIL],
    )


# ── Bursary signing chain (BURSARY_AGREEMENT_ENABLED) ─────────────────────────
# Two student-facing trilingual emails (the "now sign" follow-up + the executed
# confirmation) + two internal English notifications (partner witness-pending +
# Foundation countersign-pending). No donor is ever named in any of them.

SIGN_INVITE_SUBJECTS = {
    'en': 'Your BrightPath Bursary agreement is ready to sign ✍️',
    'ms': 'Perjanjian Biasiswa BrightPath anda sedia untuk ditandatangani ✍️',
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
        "Salam mesra,\nPasukan Biasiswa BrightPath"
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
                 extra={'support': SUPPORT_EMAIL})


AGREEMENT_EXECUTED_SUBJECTS = {
    'en': 'Your BrightPath Bursary agreement is now in effect 🎓',
    'ms': 'Perjanjian Biasiswa BrightPath anda kini berkuat kuasa 🎓',
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
        "Tahniah,\nPasukan Biasiswa BrightPath"
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


def send_agreement_executed_email(to_email, applicant_name, programme_name='', lang='en'):
    """Sent when the bursary agreement is fully executed (student + guarantor + Foundation
    signed → application 'active'). Confirms the bursary is in effect. NO sponsor identity.
    Plain text + info@."""
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    return _send(to_email, AGREEMENT_EXECUTED_SUBJECTS, AGREEMENT_EXECUTED_BODIES,
                 name, programme_name, lang, extra={'support': SUPPORT_EMAIL})


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
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
        reply_to=[SUPPORT_EMAIL],
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
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
        reply_to=[SUPPORT_EMAIL],
    )


# ── F3: sponsor notifications (real-time alert + weekly digest) ───────────────
# The body is built ONLY from already-serialised SponsorPoolDetailSerializer dicts
# (an allowlist), so it can never contain a student's identity by construction.
SPONSOR_NEW_SUBJECTS = {
    'en': '{n} new student(s) waiting for a sponsor',
    'ms': '{n} pelajar baharu sedang menunggu penaja',
    'ta': '{n} புதிய மாணவர்(கள்) நிதியுதவியாளருக்காகக் காத்திருக்கிறார்கள்',
}
SPONSOR_DIGEST_SUBJECTS = {
    'en': 'Your weekly update: {n} student(s) waiting for a sponsor',
    'ms': 'Kemas kini mingguan anda: {n} pelajar menunggu penaja',
    'ta': 'உங்கள் வாராந்திர புதுப்பிப்பு: {n} மாணவர்(கள்) நிதியுதவியாளருக்காகக் காத்திருக்கிறார்கள்',
}
SPONSOR_NOTIFY_BODIES = {
    'en': (
        "Dear Sponsor,\n\n"
        "{intro}\n\n{list}\n\n"
        "Sign in to read their anonymous profiles and choose someone to support:\n{link}\n\n"
        "You're receiving this because your notifications are set to {freq}. You can "
        "change this any time in your sponsor account.\n\n"
        "Warm regards,\nThe BrightPath Bursary Programme Team"
    ),
    'ms': (
        "Salam Penaja,\n\n"
        "{intro}\n\n{list}\n\n"
        "Log masuk untuk membaca profil tanpa nama mereka dan memilih seseorang untuk ditaja:\n{link}\n\n"
        "Anda menerima ini kerana pemberitahuan anda ditetapkan kepada {freq}. Anda boleh "
        "menukarnya bila-bila masa dalam akaun penaja anda.\n\n"
        "Salam hormat,\nPasukan Program Bursari BrightPath"
    ),
    'ta': (
        "அன்புள்ள நிதியுதவியாளரே,\n\n"
        "{intro}\n\n{list}\n\n"
        "அவர்களின் அடையாளம் தெரியாத சுயவிவரங்களைப் படித்து, உதவ ஒருவரைத் தேர்ந்தெடுக்க உள்நுழையவும்:\n{link}\n\n"
        "உங்கள் அறிவிப்புகள் {freq} என அமைக்கப்பட்டுள்ளதால் இதைப் பெறுகிறீர்கள். உங்கள் நிதியுதவியாளர் "
        "கணக்கில் எப்போது வேண்டுமானாலும் இதை மாற்றலாம்.\n\n"
        "அன்புடன்,\nBrightPath Bursary திட்டக் குழு"
    ),
}
_SPONSOR_NEW_INTRO = {
    'en': 'A new anonymised student has joined the pool and is waiting for a sponsor:',
    'ms': 'Seorang pelajar tanpa nama baharu telah menyertai kumpulan dan menunggu penaja:',
    'ta': 'ஒரு புதிய அடையாளம் தெரியாத மாணவர் சேர்ந்து நிதியுதவியாளருக்காகக் காத்திருக்கிறார்:',
}
_SPONSOR_DIGEST_INTRO = {
    'en': 'Here are the students who joined the pool this week:',
    'ms': 'Berikut ialah pelajar yang menyertai kumpulan minggu ini:',
    'ta': 'இந்த வாரம் கூட்டத்தில் சேர்ந்த மாணவர்கள் இங்கே:',
}
_SPONSOR_FREQ_WORD = {
    'realtime': {'en': 'real-time', 'ms': 'masa nyata', 'ta': 'நிகழ்நேரம்'},
    'weekly': {'en': 'weekly', 'ms': 'mingguan', 'ta': 'வாராந்திரம்'},
}


def _format_sponsor_cards(cards, lang):
    """Render the anonymised card dicts as a plain-text bullet list. Reads ONLY the
    allowlist keys the SponsorPoolDetailSerializer produces — never any identity."""
    lines = []
    for c in cards:
        ref = c.get('ref', '')
        field = c.get('field', '') or '—'
        bits = [field]
        if c.get('academic'):
            bits.append(c['academic'])
        if c.get('state'):
            bits.append(c['state'])
        lines.append(f"• {ref} — {', '.join(bits)}")
    return '\n'.join(lines)


def _send_sponsor_notify(to_email, subjects, cards, freq, lang, intro_map):
    if not to_email or not cards:
        return False
    lang = normalise_lang(lang)
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    freq_word = _SPONSOR_FREQ_WORD.get(freq, {}).get(lang, freq)
    try:
        EmailMessage(
            subject=subjects[lang].format(n=len(cards)),
            body=SPONSOR_NOTIFY_BODIES[lang].format(
                intro=intro_map[lang], list=_format_sponsor_cards(cards, lang),
                link=f'{frontend}/sponsor', freq=freq_word,
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
            to=[to_email],
            reply_to=[SPONSOR_REPLY_TO],
        ).send()
        return True
    except Exception:
        logger.warning('Failed to send sponsor notification to %s', to_email, exc_info=True)
        return False


def send_sponsor_new_student_email(to_email, cards, lang='en'):
    """F3 real-time: alert a sponsor that newly-published student(s) are waiting.
    ``cards`` = a list of SponsorPoolDetailSerializer dicts (allowlist-safe)."""
    return _send_sponsor_notify(to_email, SPONSOR_NEW_SUBJECTS, cards, 'realtime', lang, _SPONSOR_NEW_INTRO)


def send_sponsor_digest_email(to_email, cards, lang='en'):
    """F3 weekly: a digest of students published since the sponsor's last digest.
    ``cards`` = a list of SponsorPoolDetailSerializer dicts (allowlist-safe)."""
    return _send_sponsor_notify(to_email, SPONSOR_DIGEST_SUBJECTS, cards, 'weekly', lang, _SPONSOR_DIGEST_INTRO)


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
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    fmt = {'name': name, 'programme': programme_name,
           'link': f'{frontend}/scholarship/application'}
    subject = subjects[lang].format(programme=programme_name)
    text_body = bodies[lang].format(**fmt)
    return _send_html(
        to_email, subject, text_body, _decline_html(text_body),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
        reply_to=[SUPPORT_EMAIL],
    )


# ── Completion reminders (R1 +2d · R2 +9d · R3 +23d · R4/final +53d) ──────────
# Escalating from a gentle nudge to a final "5 days or we close" warning. Each links
# to the application page (the {link} kwarg is filled by _send). Keyed by stage 1–4.
# Shared help line — built-in AI helper (Cikgu Gopal) + a human fallback. Filled into
# the {help} placeholder of each reminder; the closure email uses CLOSURE_HELP.
SUPPORT_EMAIL = 'help@halatuju.xyz'
HELP_LINE = {
    'en': ("As you go, our friendly AI helper, Cikgu Gopal, will guide you through anything "
           f"on your documents that needs attention. If you're still unsure, email us at "
           f"{SUPPORT_EMAIL} — we're glad to help."),
    'ms': ("Sepanjang proses, pembantu AI mesra kami, Cikgu Gopal, akan membimbing anda dalam "
           f"apa-apa pada dokumen anda yang memerlukan perhatian. Jika anda masih tidak pasti, "
           f"e-mel kami di {SUPPORT_EMAIL} — kami sedia membantu."),
    'ta': ("இந்தச் செயல்பாட்டின்போது, எங்கள் நட்பான AI உதவியாளர் சிக்கு கோபால், உங்கள் ஆவணங்களில் "
           "கவனம் தேவைப்படும் எதையும் வழிநடத்துவார். இன்னும் உறுதியில்லை எனில், "
           f"{SUPPORT_EMAIL}-ல் எங்களுக்கு மின்னஞ்சல் அனுப்பவும் — உதவ நாங்கள் தயாராக இருக்கிறோம்."),
}
CLOSURE_HELP = {
    'en': (f"If you'd like to restart and have any questions, our AI helper Cikgu Gopal can "
           f"guide you, or email us at {SUPPORT_EMAIL}."),
    'ms': (f"Jika anda ingin memulakan semula dan mempunyai sebarang pertanyaan, pembantu AI "
           f"kami Cikgu Gopal boleh membimbing anda, atau e-mel kami di {SUPPORT_EMAIL}."),
    'ta': ("மீண்டும் தொடங்க விரும்பினால், ஏதேனும் கேள்விகள் இருந்தால், எங்கள் AI உதவியாளர் சிக்கு "
           f"கோபால் வழிநடத்துவார், அல்லது {SUPPORT_EMAIL}-ல் எங்களுக்கு மின்னஞ்சல் அனுப்பவும்."),
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
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    link = f'{frontend}/scholarship/application'
    try:
        send_mail(
            subject=REQUEST_INFO_SUBJECTS[lang].format(programme=programme_name),
            message=REQUEST_INFO_BODIES[lang].format(
                name=name, programme=programme_name, note=note, link=link),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
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
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    link = f'{frontend}/scholarship/application'
    try:
        send_mail(
            subject=QUERY_REMINDER_SUBJECTS[lang].format(programme=programme_name),
            message=QUERY_REMINDER_BODIES[lang].format(
                name=name, programme=programme_name, n=n_queries, days=days_left, link=link),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
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
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    link = f'{frontend}/scholarship/application'
    try:
        send_mail(
            subject=QUERY_RAISED_SUBJECTS[lang].format(programme=programme_name),
            message=QUERY_RAISED_BODIES[lang].format(
                name=name, programme=programme_name, n=n_queries, link=link),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
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
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
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
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    link = f"{frontend}/sponsor?ref={code}"
    note_block = _REFERRAL_NOTE_PREFIX[lang].format(note=note) if (note or '').strip() else ''
    try:
        EmailMessage(
            subject=REFERRAL_INVITE_SUBJECTS[lang].format(inviter=inviter),
            body=REFERRAL_INVITE_BODIES[lang].format(inviter=inviter, note=note_block, link=link),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
            to=[to_email],
            reply_to=[SPONSOR_REPLY_TO],
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
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
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
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
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
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
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
                 f'does, it’s not us — please tell us at {SUPPORT_EMAIL}.')

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
                 f'beritahu kami di {SUPPORT_EMAIL}.')

    # ── Plain text ────────────────────────────────────────────────────────────
    def text_block(greeting, intro, what, points_label, points, safety, closing, signoff):
        bullets = '\n'.join(f'• {p}' for p in points)
        return (f'{greeting}\n\n{intro}\n\n{what}\n\n{points_label}\n{bullets}\n\n'
                f'{safety}\n\n{closing}\n\n{signoff}')
    en_text = text_block(
        f'Hi {en_name},', en_intro, en_what, 'A few things to know beforehand:', en_points,
        en_safety, 'We look forward to speaking with you.',
        'Warm regards,\nThe BrightPath Bursary Programme team')
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
        'Warm regards,<br>The BrightPath Bursary Programme team')
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
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
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
                 f'does, it isn’t us — please tell us straight away at {SUPPORT_EMAIL}.')

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
                 f'dengan segera di {SUPPORT_EMAIL}.')

    # ── Plain text ────────────────────────────────────────────────────────────
    def text_block(greeting, intro, lead, steps, btn_line, after, safety, signoff):
        body_steps = '\n\n'.join(f'{i}. {t} {d}' for i, (t, d) in enumerate(steps, 1))
        return (f'{greeting}\n\n{intro}\n\n{lead}\n\n{body_steps}\n\n{btn_line}\n\n'
                f'{after}\n\n{safety}\n\n{signoff}')
    en_text = text_block(
        f'Hi {en_name},', en_intro, en_lead, en_steps, f'View my application: {link}', en_after,
        en_safety, 'Warm regards,\nThe BrightPath Bursary Programme Team')
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
        en_safety, 'Warm regards,<br>The BrightPath Bursary Programme Team')
    bm_html = html_block(
        f'Salam {bm_name},', bm_intro, bm_lead, bm_steps, 'Lihat permohonan saya', bm_after,
        bm_safety, 'Salam hormat,<br>Pasukan Program Bursari BrightPath')
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    # General programme email → from info@ (DEFAULT_FROM_EMAIL), reply to support; NOT interview@.
    return _send_html(to_email, subject, text_body, html_body,
                      from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@halatuju.xyz'),
                      reply_to=[SUPPORT_EMAIL])


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
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.xyz'),
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
    return {'List-Unsubscribe': f'<mailto:{SUPPORT_EMAIL}?subject=Unsubscribe%20from%20B40%20emails>'}


def _send_bilingual(to_email, subject, en, bm):
    """Send one EN+BM email (the booking-flow pattern), with Reply-To = the interview
    alias so replies route there. Best-effort → bool."""
    if not to_email:
        return False
    try:
        EmailMessage(
            subject=subject,
            body=en + '\n\n———\n\n' + bm,
            from_email=INTERVIEW_FROM_EMAIL,
            to=[to_email],
            reply_to=[INTERVIEW_REPLY_TO],
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


def _send_html(to_email, subject, text_body, html_body, reply_to=None, ics=None, from_email=None):
    """Send a multipart email — HTML primary + plain-text fallback. From/Reply-To default to
    the interview alias (interview emails are the main caller); pass ``from_email`` +
    ``reply_to`` for a general (non-interview) email, e.g. the info@ sender. ``ics`` (a
    calendar string) is attached as interview.ics so the client offers "add to calendar".
    Best-effort → bool."""
    if not to_email:
        return False
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email or INTERVIEW_FROM_EMAIL,
            to=[to_email],
            reply_to=reply_to or [INTERVIEW_REPLY_TO],
            headers=_interview_unsub_headers(),
        )
        msg.attach_alternative(html_body, 'text/html')
        if ics:
            msg.attach('interview.ics', ics, 'text/calendar')
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
        'BEGIN:VEVENT', f'UID:b40-interview-{int(start.timestamp())}@halatuju.xyz',
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
    app_link = f"{getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')}/scholarship/application"
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
        f'please tell us at {SUPPORT_EMAIL}.\n\n'
        f'We look forward to speaking with you.\n\n'
        f'Warm regards,\nThe BrightPath Bursary Programme team'
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
        f'sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {SUPPORT_EMAIL}.\n\n'
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
        f'please tell us at {SUPPORT_EMAIL}.',
        'We look forward to speaking with you.',
        'Warm regards,<br>The BrightPath Bursary Programme team')
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
        f'berbuat demikian, itu bukan kami — sila beritahu kami di {SUPPORT_EMAIL}.',
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
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
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
        f'Warm regards,\nThe BrightPath Bursary Programme Team'
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
        'Warm regards,<br>The BrightPath Bursary Programme Team')
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
        f'Warm regards,\nThe BrightPath Bursary Programme Team'
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
        'Warm regards,<br>The BrightPath Bursary Programme Team')
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
        f'not us — please tell us at {SUPPORT_EMAIL}.\n\n'
        f'Warm regards,\nThe BrightPath Bursary Programme Team'
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
        f'PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {SUPPORT_EMAIL}.\n\n'
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
        f'us at {SUPPORT_EMAIL}.',
        'Warm regards,<br>The BrightPath Bursary Programme Team')
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
        f'sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {SUPPORT_EMAIL}.',
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
        f"not us — please tell us at {SUPPORT_EMAIL}.\n\n"
        f'Warm regards,\nThe BrightPath Bursary Programme Team'
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
        f'PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {SUPPORT_EMAIL}.\n\n'
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
        f'please tell us at {SUPPORT_EMAIL}.',
        'Warm regards,<br>The BrightPath Bursary Programme Team')
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
        f'PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {SUPPORT_EMAIL}.',
        'Salam hormat,<br>Pasukan Program Bursari BrightPath')
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    return _send_html(to_email, 'Your BrightPath Bursary Programme interview time has been released',
                      text_body, html_body)


def _send_plain(to_email, subject, body):
    if not to_email:
        return False
    try:
        EmailMessage(subject=subject, body=body,
                     from_email=INTERVIEW_FROM_EMAIL,
                     to=[to_email], reply_to=[INTERVIEW_REPLY_TO],
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
