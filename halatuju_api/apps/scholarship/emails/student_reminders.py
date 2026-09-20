"""Completion reminders and the application-closed notice, with the help line each carries.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from .shared import _P
from .student_decisions import _send, normalise_lang


# ── Completion reminders (R1 +2d · R2 +9d · R3 +23d · R4/final +53d) ──────────
# Escalating from a gentle nudge to a final "5 days or we close" warning. Each links
# to the application page (the {link} kwarg is filled by _send). Keyed by stage 1–4.
# Shared help line — built-in AI helper (Cikgu Gopal) + a human fallback. Filled into
# the {help} placeholder of each reminder; the closure email uses CLOSURE_HELP.
# {persona} = the coach's rendered name (per language) and {support} = the support address, both
# filled from the branding seam at send time (send_reminder_email / send_application_closed_email).
HELP_LINE = {
    'en': ("As you go, our friendly AI helper, {persona}, will guide you through anything "
           "on your documents that needs attention. If you're still unsure, email us at "
           "{support} — we're glad to help."),
    'ms': ("Sepanjang proses, pembantu AI mesra kami, {persona}, akan membimbing anda dalam "
           "apa-apa pada dokumen anda yang memerlukan perhatian. Jika anda masih tidak pasti, "
           "e-mel kami di {support} — kami sedia membantu."),
    'ta': ("இந்தச் செயல்பாட்டின்போது, எங்கள் நட்பான AI உதவியாளர் {persona}, உங்கள் ஆவணங்களில் "
           "கவனம் தேவைப்படும் எதையும் வழிநடத்துவார். இன்னும் உறுதியில்லை எனில், "
           "{support}-ல் எங்களுக்கு மின்னஞ்சல் அனுப்பவும் — உதவ நாங்கள் தயாராக இருக்கிறோம்."),
}
CLOSURE_HELP = {
    'en': ("If you'd like to restart and have any questions, our AI helper {persona} can "
           "guide you, or email us at {support}."),
    'ms': ("Jika anda ingin memulakan semula dan mempunyai sebarang pertanyaan, pembantu AI "
           "kami {persona} boleh membimbing anda, atau e-mel kami di {support}."),
    'ta': ("மீண்டும் தொடங்க விரும்பினால், ஏதேனும் கேள்விகள் இருந்தால், எங்கள் AI உதவியாளர் "
           "{persona} வழிநடத்துவார், அல்லது {support}-ல் எங்களுக்கு மின்னஞ்சல் அனுப்பவும்."),
}


def _help_line(mapping, lang, branding):
    """Render a persona help line ({persona}/{support}) from the branding seam."""
    b = branding or _P
    return mapping[lang].format(persona=b.persona_name(lang), support=b.email_support)

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


def send_reminder_email(to_email, applicant_name, programme_name, stage, lang='en', branding=None):
    """Send completion reminder ``stage`` (1–4). Stage 4 is the final 'complete within
    5 days or we close it' warning. No-op for an unknown stage."""
    if stage not in REMINDER_SUBJECTS:
        return False
    return _send(to_email, REMINDER_SUBJECTS[stage], REMINDER_BODIES[stage],
                 applicant_name, programme_name, lang,
                 extra={'help': _help_line(HELP_LINE, normalise_lang(lang), branding)},
                 branding=branding)


def send_application_closed_email(to_email, applicant_name, programme_name, lang='en', branding=None):
    """Confirm an application was auto-closed for non-completion, inviting a fresh start."""
    return _send(to_email, CLOSED_SUBJECTS, CLOSED_BODIES, applicant_name, programme_name, lang,
                 extra={'help': _help_line(CLOSURE_HELP, normalise_lang(lang), branding)},
                 branding=branding)
