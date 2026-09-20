"""Request-for-information, query-raised and query-reminder mail.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.core.mail import send_mail
from .shared import _DEFAULT_NAME, _P, logger
from .student_decisions import normalise_lang


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
