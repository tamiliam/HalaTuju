"""Request-for-information, query-raised and query-reminder mail.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.

Sprint SUP1 (2026-11-14): the query-raised and reminder mails now NAME each open item by its
student-facing title, say the Action Centre always shows the latest list, and carry a
reply-to (the support address). The reminder has its own subject.
"""
from django.core.mail import EmailMessage
from .sending import _interview_unsub_headers
from .shared import _DEFAULT_NAME, _P, _meter_email, logger
from .student_decisions import normalise_lang


def _items_block(titles):
    """The open items as a bullet list for the body ('' when none were passed): titles only."""
    return ('\n'.join(f'- {t}' for t in titles) + '\n\n') if titles else ''


def _send_with_unsub(*, subject, message, from_email, recipient_list):
    """`send_mail`'s plain message, keyword for keyword, plus the harmless mailto
    List-Unsubscribe the interview mail carries (TD-130) — `send_mail` cannot take headers.

    S6a (2026-10-30): METERED, like every other student send (tenancy rule 6). These three were the
    only student emails that left no usage row at all, so they were neither billed nor visible as
    "last sent". The meter names the row after the `send_*` caller (frame 2 = that caller).

    SUP1 (2026-11-14): `reply_to` is the support address, as the award and decline mail set it, so
    a student who answers the email reaches a person."""
    _meter_email()
    EmailMessage(subject=subject, body=message, from_email=from_email, to=recipient_list,
                 headers=_interview_unsub_headers(), reply_to=[_P.email_support]).send()


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
        _send_with_unsub(
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
    'en': 'A reminder: a few things we still need for your {programme} application',
    'ms': 'Peringatan: beberapa perkara yang masih kami perlukan untuk permohonan {programme} anda',
    'ta': 'நினைவூட்டல்: உங்கள் {programme} விண்ணப்பத்திற்கு இன்னும் எங்களுக்குத் தேவையான சில விவரங்கள்',
}
def count_words(n, days=None):
    """Singular / plural words for the count and the days left (SUP1: no more "item(s)").
    Every key is passed to every language; a template uses only its own (`format` ignores the
    rest). Malay needs none: "perkara" and "hari" do not change."""
    one, one_day = n == 1, days == 1
    return {
        'these': '' if one else 'These ',   # "1 item is", "These 3 items are"
        'item_word': 'item' if one else 'items',
        'is_are': 'is' if one else 'are',
        'day_word': 'day' if one_day else 'days',
        'ta_item': 'விவரம்' if one else 'விவரங்கள்',
        'ta_waits': 'காத்திருக்கிறது' if one else 'காத்திருக்கின்றன',
        'ta_within_days': 'நாளுக்குள்' if one_day else 'நாட்களுக்குள்',
    }


QUERY_REMINDER_BODIES = {
    'en': ('Dear {name},\n\nA gentle reminder: {n} {item_word} {is_are} still waiting in your '
           'Action Centre to help us complete your {programme} profile:\n\n{items}Please sign in '
           'and respond to each one within about {days} {day_word}: {link}\n\nYour Action Centre '
           'always shows the latest list, so it is the best place to check what is still '
           'needed.\n\nIf we do not hear back in time, we may have to review your application '
           'with the information we already have, so it helps to reply soon.\n\nThank you.'),
    'ms': ('Salam {name},\n\nSekadar peringatan: {n} perkara masih menunggu di Pusat Tindakan '
           'anda untuk membantu kami melengkapkan profil {programme} anda:\n\n{items}Sila log '
           'masuk dan lengkapkan setiap satu dalam kira-kira {days} hari: {link}\n\nPusat '
           'Tindakan anda sentiasa menunjukkan senarai terkini, jadi itulah tempat terbaik untuk '
           'menyemak apa yang masih diperlukan.\n\nJika kami tidak menerima maklum balas tepat '
           'pada masanya, kami mungkin terpaksa menyemak permohonan anda dengan maklumat yang '
           'sedia ada, jadi eloklah membalas segera.\n\nTerima kasih.'),
    'ta': ('அன்புள்ள {name},\n\nசிறிய நினைவூட்டல்: உங்கள் {programme} விவரக்குறிப்பை '
           'முழுமைப்படுத்த உதவ, பின்வரும் {n} {ta_item} உங்கள் செயல் மையத்தில் இன்னும் '
           '{ta_waits}:\n\n{items}தயவுசெய்து உள்நுழைந்து சுமார் {days} {ta_within_days} '
           'ஒவ்வொன்றுக்கும் பதிலளிக்கவும்: {link}\n\nஉங்கள் செயல் மையம் எப்போதும் அண்மைய '
           'பட்டியலைக் காட்டும்; ஆகவே இன்னும் என்ன தேவை என்பதை அங்கே பார்க்கலாம்.\n\nசரியான '
           'நேரத்தில் பதில் கிடைக்காவிட்டால், எங்களிடம் ஏற்கெனவே உள்ள தகவலைக் கொண்டே உங்கள் '
           'விண்ணப்பத்தை மதிப்பாய்வு செய்ய வேண்டியிருக்கலாம்; எனவே விரைவில் பதிலளிப்பது '
           'நல்லது.\n\nநன்றி.'),
}


def send_query_reminder_email(to_email, applicant_name, programme_name, n_queries,
                              days_left, lang='en', titles=None):
    """Check 2 STEP 2: nudge the student to answer their open items in the Action Centre before
    the SLA lapses. Trilingual; best-effort.

    `titles` = the student-facing title of each open item, from `services.query_items`. An EMPTY
    list sends nothing (the caller recounted just now and nothing is open); a non-empty one makes
    the count in the body the list's own length, so the two can never disagree."""
    if not to_email or titles == []:
        return False
    if titles:
        n_queries = len(titles)
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    frontend = _P.frontend_url
    link = f'{frontend}/scholarship/application'
    try:
        _send_with_unsub(
            subject=QUERY_REMINDER_SUBJECTS[lang].format(programme=programme_name),
            message=QUERY_REMINDER_BODIES[lang].format(
                name=name, programme=programme_name, n=n_queries, days=days_left, link=link,
                items=_items_block(titles), **count_words(n_queries, days_left)),
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
           'reviewing it and need a little more from you. {these}{n} {item_word} {is_are} '
           'waiting in your Action Centre:\n\n{items}Please sign in and respond to each one here: '
           '{link}\n\nYour Action Centre always shows the latest list, so it is the best place to '
           'check what is still needed.\n\nIt only takes a few minutes, and it helps us put your '
           'case forward well.\n\nThank you.'),
    'ms': ('Salam {name},\n\nTerima kasih kerana menghantar permohonan {programme} anda. Kami '
           'sedang menyemaknya dan memerlukan sedikit lagi daripada anda. {n} perkara berikut '
           'menunggu di Pusat Tindakan anda:\n\n{items}Sila log masuk dan lengkapkan setiap satu '
           'di sini: {link}\n\nPusat Tindakan anda sentiasa menunjukkan senarai terkini, jadi '
           'itulah tempat terbaik untuk menyemak apa yang masih diperlukan.\n\nIa hanya '
           'mengambil beberapa minit, dan ia membantu kami mengetengahkan kes anda dengan '
           'baik.\n\nTerima kasih.'),
    'ta': ('அன்புள்ள {name},\n\nஉங்கள் {programme} விண்ணப்பத்தைச் சமர்ப்பித்ததற்கு நன்றி. நாங்கள் '
           'அதை மதிப்பாய்வு செய்து வருகிறோம்; உங்களிடமிருந்து இன்னும் சிறிது தேவை. பின்வரும் {n} '
           '{ta_item} உங்கள் செயல் மையத்தில் {ta_waits}:\n\n{items}தயவுசெய்து உள்நுழைந்து '
           'ஒவ்வொன்றுக்கும் இங்கே பதிலளிக்கவும்: {link}\n\nஉங்கள் செயல் மையம் எப்போதும் '
           'அண்மைய பட்டியலைக் காட்டும்; ஆகவே இன்னும் என்ன தேவை என்பதை அங்கே பார்க்கலாம்.'
           '\n\nஇதற்குச் சில நிமிடங்களே ஆகும்; இது உங்கள் வழக்கை நன்கு முன்வைக்க உதவும்.'
           '\n\nநன்றி.'),
}


def send_query_raised_email(to_email, applicant_name, programme_name, n_queries, lang='en',
                            titles=None):
    """Check 2 STEP 2: at submission, tell the student a few items are waiting in their Action
    Centre so they come back and answer. Trilingual; best-effort. `titles` as for the reminder:
    an EMPTY list sends nothing, and a non-empty one is the count."""
    if not to_email or titles == []:
        return False
    if titles:
        n_queries = len(titles)
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    frontend = _P.frontend_url
    link = f'{frontend}/scholarship/application'
    try:
        _send_with_unsub(
            subject=QUERY_RAISED_SUBJECTS[lang].format(programme=programme_name),
            message=QUERY_RAISED_BODIES[lang].format(
                name=name, programme=programme_name, n=n_queries, link=link,
                items=_items_block(titles), **count_words(n_queries)),
            from_email=_P.email_from,
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send query-raised email to %s', to_email, exc_info=True)
        return False
