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
        "Warm regards,\nThe B40 Assistance Programme Team"
    ),
    'ms': (
        "Salam Penaja,\n\n"
        "{intro}\n\n{list}\n\n"
        "Log masuk untuk membaca profil tanpa nama mereka dan memilih seseorang untuk ditaja:\n{link}\n\n"
        "Anda menerima ini kerana pemberitahuan anda ditetapkan kepada {freq}. Anda boleh "
        "menukarnya bila-bila masa dalam akaun penaja anda.\n\n"
        "Salam hormat,\nPasukan Program Bantuan B40"
    ),
    'ta': (
        "அன்புள்ள நிதியுதவியாளரே,\n\n"
        "{intro}\n\n{list}\n\n"
        "அவர்களின் அடையாளம் தெரியாத சுயவிவரங்களைப் படித்து, உதவ ஒருவரைத் தேர்ந்தெடுக்க உள்நுழையவும்:\n{link}\n\n"
        "உங்கள் அறிவிப்புகள் {freq} என அமைக்கப்பட்டுள்ளதால் இதைப் பெறுகிறீர்கள். உங்கள் நிதியுதவியாளர் "
        "கணக்கில் எப்போது வேண்டுமானாலும் இதை மாற்றலாம்.\n\n"
        "அன்புடன்,\nB40 உதவித் திட்டக் குழு"
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
        send_mail(
            subject=subjects[lang].format(n=len(cards)),
            message=SPONSOR_NOTIFY_BODIES[lang].format(
                intro=intro_map[lang], list=_format_sponsor_cards(cards, lang),
                link=f'{frontend}/sponsor', freq=freq_word,
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
            recipient_list=[to_email],
        )
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


def send_decline_email(to_email, applicant_name, programme_name, category='', lang='en'):
    """Send the right decline email for a rejection bucket. merit/need/interview each
    get suggestive bucket-specific copy; ineligible/contractual/unknown fall back to
    the generic warm decline (FAIL_*)."""
    subjects, bodies = _DECLINE_TEMPLATES.get(category, (FAIL_SUBJECTS, FAIL_BODIES))
    return _send(to_email, subjects, bodies, applicant_name, programme_name, lang)


# ── Completion reminders (R1 +2d · R2 +9d · R3 +23d · R4/final +53d) ──────────
# Escalating from a gentle nudge to a final "5 days or we close" warning. Each links
# to the application page (the {link} kwarg is filled by _send). Keyed by stage 1–4.
# Shared help line — built-in AI helper (Cikgu Gopal) + a human fallback. Filled into
# the {help} placeholder of each reminder; the closure email uses CLOSURE_HELP.
SUPPORT_EMAIL = 'tamiliam@gmail.com'
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
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
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
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
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
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
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
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
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
        send_mail(
            subject=REFERRAL_INVITE_SUBJECTS[lang].format(inviter=inviter),
            message=REFERRAL_INVITE_BODIES[lang].format(inviter=inviter, note=note_block, link=link),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send sponsor-referral invite to %s', to_email, exc_info=True)
        return False


def send_vision_outage_alert_email(stats):
    """Alert the admin that Google Vision OCR appears to be down — every recent
    IC/parent-IC OCR attempt errored and none succeeded. Sent to
    ``settings.ADMIN_NOTIFY_EMAIL`` (tamiliam@gmail.com); skipped silently if unset.
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
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
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
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send admin-notify email for application #%s',
                       application_id, exc_info=True)
        return False


def send_reviewer_assigned_email(to_email, reviewer_name, applicant_name):
    """F7: notify a reviewer that an applicant has been assigned to them. English-only
    (reviewers are internal staff). Sent on each (re)assignment — never re-sent for an
    unchanged assignee, because assign_reviewer short-circuits a no-op before this fires.
    Best-effort — swallows send failures so a mail hiccup never breaks the assignment."""
    if not to_email:
        return False
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    reviewer = reviewer_name or 'there'
    applicant = applicant_name or 'A new applicant'
    try:
        send_mail(
            subject='A new applicant has been assigned to you — HalaTuju',
            message=(
                f'Dear {reviewer},\n\n'
                f'{applicant} has been assigned to you for review on HalaTuju.\n\n'
                f'Please sign in to your reviewer dashboard to see their profile, '
                f'supporting documents, and verification checks, and to record your '
                f'decision:\n\n'
                f'{frontend}/admin/login\n\n'
                f'If you have any questions, just reply to this email.\n\n'
                f'Thank you for supporting the B40 Assistance Programme.\n\n'
                f'Warm regards,\nThe HalaTuju Team'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send reviewer-assigned email to %s', to_email,
                       exc_info=True)
        return False


def send_student_assigned_reviewer_email(to_email, *, student_name, reviewer_name,
                                         reviewer_email='', reviewer_phone=''):
    """F7 advance notice to the STUDENT: who will interview them + how, so they expect the
    call and pick up. Bilingual (English then Bahasa Melayu) in one email. No document
    checklist (the interviewer asks for anything still needed). The phone + call-to-action
    adapt to whether the reviewer shares their number (ReviewerProfile.share_phone_with_students).
    Best-effort; never breaks the assignment. Gated by STUDENT_ASSIGNMENT_EMAIL_ENABLED at the
    call site."""
    if not to_email:
        return False
    student = student_name or 'there'
    student_bm = student_name or 'di sana'
    reviewer = reviewer_name or 'our interviewer'
    reviewer_bm = reviewer_name or 'penemu duga kami'
    phone_disp = f'+60 {reviewer_phone}' if reviewer_phone else ''

    en_contact = (
        f'• Interviewer: {reviewer}\n'
        + (f'• Contact: phone / WhatsApp {phone_disp} · email {reviewer_email}\n'
           if phone_disp else f'• Contact: email {reviewer_email}\n')
    )
    bm_contact = (
        f'• Penemu duga: {reviewer}\n'
        + (f'• Hubungi: telefon / WhatsApp {phone_disp} · e-mel {reviewer_email}\n'
           if phone_disp else f'• Hubungi: e-mel {reviewer_email}\n')
    )
    # The call-to-action depends on whether a phone was shared (the reviewer may opt out).
    en_action = ('Please save the above number and pick up when they call. If you miss it, just '
                 'reply to arrange another time.' if phone_disp
                 else 'Please look out for their email and reply to arrange a time.')
    bm_action = ('Sila simpan nombor di atas dan jawab apabila mereka menelefon. Jika terlepas, '
                 'balas sahaja untuk menetapkan masa lain.' if phone_disp
                 else 'Sila perhatikan e-mel mereka dan balas untuk menetapkan masa.')

    en = (
        f'Hi {student},\n\n'
        f'Good news — your application has reached the interview stage of the B40 Assistance '
        f'Programme, and an interviewer has been assigned to you:\n\n'
        f'{en_contact}\n'
        f'{reviewer} will contact you within the next few days to arrange a short interview '
        f'(by phone or video call). {en_action}\n\n'
        f'For a video call, please be on camera. If your parents or guardian are around, our '
        f'interviewer would be glad to speak with them too.\n\n'
        f'This is simply to understand your family’s situation fairly. The support is for families '
        f'with genuine financial need, and we value your honesty.\n\n'
        f'For your safety: we will never ask you for money, your bank password, or an OTP/PIN. If '
        f'anyone does, it is not from us — please email tamiliam@gmail.com.\n\n'
        f'Thank you, and we look forward to speaking with you.\n'
        f'— The B40 Assistance Programme team'
    )
    bm = (
        f'Salam {student_bm},\n\n'
        f'Berita baik — permohonan anda telah sampai ke peringkat temu duga Program Bantuan B40, '
        f'dan seorang penemu duga telah ditugaskan kepada anda:\n\n'
        f'{bm_contact}\n'
        f'{reviewer_bm} akan menghubungi anda dalam masa beberapa hari untuk menetapkan temu duga '
        f'ringkas (melalui telefon atau panggilan video). {bm_action}\n\n'
        f'Untuk panggilan video, sila buka kamera. Jika ibu bapa atau penjaga anda ada bersama, '
        f'penemu duga kami amat berbesar hati untuk bercakap dengan mereka juga.\n\n'
        f'Ini hanyalah untuk memahami keadaan keluarga anda secara adil. Bantuan ini untuk keluarga '
        f'yang benar-benar memerlukan, dan kami menghargai kejujuran anda.\n\n'
        f'Untuk keselamatan anda: kami tidak sekali-kali akan meminta wang, kata laluan bank, atau '
        f'OTP/PIN. Jika sesiapa berbuat demikian, ia bukan daripada kami — sila e-mel '
        f'tamiliam@gmail.com.\n\n'
        f'Terima kasih, dan kami menantikan untuk bercakap dengan anda.\n'
        f'— Pasukan Program Bantuan B40'
    )
    try:
        send_mail(
            subject='Your B40 Assistance Programme interview',
            message=en + '\n\n———\n\n' + bm,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@halatuju.com'),
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send student-assigned-reviewer email to %s', to_email,
                       exc_info=True)
        return False
