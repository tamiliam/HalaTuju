"""The plain-text student decision mail: acknowledgement, submission received, pass, award
confirmed, and the fail / merit / need / interview copy the decline mail also reads.
`_send` is the plain-text primitive for all of it.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.core.mail import send_mail
from .shared import _DEFAULT_NAME, _P, _meter_email, logger


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


def _send(to_email, subjects, bodies, applicant_name, programme_name, lang, extra=None,
          branding=None):
    """
    Best-effort send: a mail failure is logged and swallowed so it never blocks
    the surrounding workflow. Returns True if the send succeeded. ``extra`` supplies
    any additional, already-language-resolved body placeholders (e.g. {help}); a
    template that doesn't reference them ignores the extras harmlessly. ``branding``
    (default = the platform seam) supplies the sender identity + frontend URL; the
    caller passes ``programme_name`` (the {programme} placeholder) and any brand
    tokens ({signoff}, …) through ``extra`` so a tenant renders its own copy.
    """
    if not to_email:
        return False
    b = branding or _P
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    # Link to the complete-your-profile page (the shortlist body uses {link}; the
    # ack/decline bodies don't reference it, so the kwarg is harmlessly ignored).
    frontend = b.frontend_url
    link = f"{frontend}/scholarship/application"
    fmt = {'name': name, 'programme': programme_name, 'link': link, **(extra or {})}
    _meter_email()
    try:
        send_mail(
            subject=subjects[lang].format(programme=programme_name),
            message=bodies[lang].format(**fmt),
            from_email=b.email_from,
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
