"""The emails a FUNDED student receives about her results (student maintenance S4b, 2026-10-29).

Three kinds, each in the student's language (en / ms / ta), each the ORGANISATION's to word:

  * ``results_due``     — her next result is due soon (the daily `results-due-reminders` job);
  * ``results_overdue`` — a result is past its due date and the grace (the daily `results-overdue-flag`);
  * ``result_queried``  — an officer queried a result she sent, with the officer's note.

S6b added ``letter_issued`` (a formal letter, locked) and S7b ``mentor_assigned`` ("You have a mentor",
switchable, sent by `mentoring.assign` to the student only). S8 added ``announcement`` (switchable, sent by the
hourly `announcement-emails` job): the organisation words the WRAPPER; the announcement's own title and
message are inserted as staff wrote them (`announcement_title`, `announcement_body`). S9 added ``survey_open``
(switchable, sent by the hourly `survey-emails` job): ONE wording for both survey emails — the opening one and
the reminder — the difference carried by `{survey_note}`, a line the code fills in her language
(`survey_emails.NOTES`). S10 added ``module_published`` (switchable, sent by the hourly `module-emails` job): ONE
wording for the "a new module is ready" email and the reminder before its due date, `{module_note}` saying which
(`development_emails.NOTES`) and `{due_note}` the due date, or nothing.

WHERE THE WORDS LIVE. The platform's default wording is HERE, in code (``DEFAULTS``). An organisation
that edits a letter (Organisation → Settings → Student communications) gets its own
``StudentEmailTemplate`` row for that (kind, language); "Reset" deletes the row and the default
applies again. Nothing is seeded: a schema-only migration, and a new organisation needs no data step
to start with sound wording (decisions.md, S4b).

⚠ THE KILL SWITCH. ``settings.MAINTENANCE_REMINDERS_ENABLED`` (env, default OFF; ON in production since
2026-10-30) takes ALL THREE dark — the reminders, the overdue notice AND the queried notice. Under it,
an organisation may switch any of the three off for its own students (S6a,
``student_email_catalogue.may_send``); the platform flag always wins.
The student still sees an officer's query on her My Bursary page either way.

Rendering is the shared engine (``email_templates.render``), sent through ``emails.sending._send_html``
(which meters each send) inside ``usage.usage_context(application=...)`` so the tenant is billed,
from the organisation's own sender (``branding.for_application``). There is no opt-out field on a
student today; these are transactional notices about her own bursary.
"""
from django.conf import settings
from django.db import transaction

from . import email_templates
from .models import StudentEmailTemplate

KINDS = ('results_due', 'results_overdue', 'result_queried', 'letter_issued', 'mentor_assigned', 'announcement',
         'survey_open', 'module_published')
#: The kinds `MAINTENANCE_REMINDERS_ENABLED` holds back. The letter notice is NOT one of them: a
#: letter is a formal act by an officer, and she learns of it by this email (S6b, locked).
PLATFORM_SWITCHED = frozenset({'results_due', 'results_overdue', 'result_queried'})
LANGUAGES = ('en', 'ms', 'ta')

_COMMON = ('name', 'programme', 'link', 'support', 'signoff')
#: The tokens each kind may use — anything else refuses the save (`unknown_placeholders`).
PLACEHOLDERS = {
    'results_due': _COMMON + ('due_date',),
    'results_overdue': _COMMON + ('due_date',),
    'result_queried': _COMMON + ('semester', 'note'),
    'letter_issued': _COMMON + ('response_due', 'letter_subject'),
    # S7b: the mentor's details as the student may see them (`mentoring._send_you_have_a_mentor`):
    # `mentor_contact` is the email, and the phone ONLY when the mentor shares it with students.
    'mentor_assigned': _COMMON + ('mentor_name', 'mentor_area', 'mentor_languages', 'mentor_contact'),
    # S8: the announcement as staff wrote it; `{link}` opens My Bursary on its News tab.
    'announcement': _COMMON + ('announcement_title', 'announcement_body'),
    # S9: the survey as staff named it, its closing day, and the line that says "new" or "a reminder";
    # `{link}` opens My Bursary on its Surveys tab.
    'survey_open': _COMMON + ('survey_title', 'closes_on', 'survey_note'),
    # S10: the module as staff named it, the line that says "new" or "a reminder", and "please finish it by
    # …" (empty without a due date); `{link}` opens My Bursary on its Growth tab.
    'module_published': _COMMON + ('module_title', 'module_note', 'due_note'),
}

DEFAULTS = {
    'results_due': {
        'en': ('Your next result is due by {due_date}',
               'Dear {name},\n\nYour next semester result for the {programme} is due by {due_date}.\n\n'
               'When your results are out, please upload your result slip on your My Bursary page — '
               'a result is accepted only with its slip uploaded there:\n{link}\n\n'
               'If you have a question, write to {support}.\n\n{signoff}'),
        'ms': ('Keputusan anda yang seterusnya perlu dihantar sebelum {due_date}',
               'Salam {name},\n\nKeputusan semester anda yang seterusnya untuk {programme} perlu dihantar '
               'sebelum {due_date}.\n\nApabila keputusan anda keluar, sila muat naik slip keputusan anda di '
               'halaman Biasiswa Saya — keputusan hanya diterima jika slipnya dimuat naik di sana:\n{link}\n\n'
               'Jika ada pertanyaan, tulis kepada {support}.\n\n{signoff}'),
        'ta': ('உங்கள் அடுத்த முடிவு {due_date}-க்குள் அனுப்பப்பட வேண்டும்',
               'அன்புள்ள {name},\n\n{programme}-க்கான உங்கள் அடுத்த பருவ முடிவு {due_date}-க்குள் அனுப்பப்பட '
               'வேண்டும்.\n\nஉங்கள் முடிவுகள் வெளியானதும், எனது உதவித்தொகை பக்கத்தில் உங்கள் முடிவுச் சீட்டைப் '
               'பதிவேற்றுங்கள் — அங்கே சீட்டு பதிவேற்றப்பட்டால் மட்டுமே முடிவு ஏற்கப்படும்:\n{link}\n\n'
               'கேள்விகள் இருந்தால் {support}-க்கு எழுதுங்கள்.\n\n{signoff}'),
    },
    'results_overdue': {
        'en': ('Your result was due by {due_date}',
               'Dear {name},\n\nYour semester result for the {programme} was due by {due_date}, and we have '
               'not received it yet.\n\nPlease upload your result slip on your My Bursary page as soon as you '
               'can:\n{link}\n\nIf something is holding it up, write to {support} and tell us — we are here '
               'to help.\n\n{signoff}'),
        'ms': ('Keputusan anda sepatutnya dihantar sebelum {due_date}',
               'Salam {name},\n\nKeputusan semester anda untuk {programme} sepatutnya dihantar sebelum '
               '{due_date}, dan kami belum menerimanya.\n\nSila muat naik slip keputusan anda di halaman '
               'Biasiswa Saya secepat mungkin:\n{link}\n\nJika ada sesuatu yang menghalang, tulis kepada '
               '{support} dan beritahu kami — kami sedia membantu.\n\n{signoff}'),
        'ta': ('உங்கள் முடிவு {due_date}-க்குள் அனுப்பப்பட்டிருக்க வேண்டும்',
               'அன்புள்ள {name},\n\n{programme}-க்கான உங்கள் பருவ முடிவு {due_date}-க்குள் அனுப்பப்பட்டிருக்க '
               'வேண்டும்; அது இன்னும் எங்களுக்குக் கிடைக்கவில்லை.\n\nஎனது உதவித்தொகை பக்கத்தில் உங்கள் முடிவுச் '
               'சீட்டை விரைவில் பதிவேற்றுங்கள்:\n{link}\n\nஏதேனும் தடை இருந்தால் {support}-க்கு எழுதி '
               'எங்களிடம் சொல்லுங்கள் — உதவ நாங்கள் இருக்கிறோம்.\n\n{signoff}'),
    },
    'result_queried': {
        'en': ('A question about your {semester} result',
               'Dear {name},\n\nWe have looked at the {semester} result you sent for the {programme} and need '
               'you to check something:\n\n{note}\n\nPlease open your My Bursary page and send the result '
               'again with its slip:\n{link}\n\nIf you have a question, write to {support}.\n\n{signoff}'),
        'ms': ('Satu soalan tentang keputusan {semester} anda',
               'Salam {name},\n\nKami telah menyemak keputusan {semester} yang anda hantar untuk {programme} '
               'dan perlu anda menyemak sesuatu:\n\n{note}\n\nSila buka halaman Biasiswa Saya anda dan hantar '
               'keputusan itu semula bersama slipnya:\n{link}\n\nJika ada pertanyaan, tulis kepada {support}.'
               '\n\n{signoff}'),
        'ta': ('உங்கள் {semester} முடிவு பற்றி ஒரு கேள்வி',
               'அன்புள்ள {name},\n\n{programme}-க்காக நீங்கள் அனுப்பிய {semester} முடிவைப் பார்த்தோம்; நீங்கள் '
               'ஒன்றைச் சரிபார்க்க வேண்டும்:\n\n{note}\n\nஉங்கள் எனது உதவித்தொகை பக்கத்தைத் திறந்து, முடிவைச் '
               'சீட்டுடன் மீண்டும் அனுப்புங்கள்:\n{link}\n\nகேள்விகள் இருந்தால் {support}-க்கு எழுதுங்கள்.'
               '\n\n{signoff}'),
    },
    # S6b: an officer has issued her a formal letter. The letter itself is on My Bursary (and its
    # PDF, English or Malay); this email is how she learns of it, in HER language.
    'letter_issued': {
        'en': ('{programme}: a formal letter for you',
               'Dear {name},\n\nWe have issued a formal letter to you about your {programme}: '
               '"{letter_subject}".\n\nPlease read it on your My Bursary page and confirm you have received '
               'it by {response_due}:\n{link}\n\nIf you have a question, write to {support}.\n\n{signoff}'),
        'ms': ('{programme}: surat rasmi untuk anda',
               'Salam {name},\n\nKami telah mengeluarkan surat rasmi kepada anda mengenai {programme} anda: '
               '"{letter_subject}".\n\nSila bacanya di halaman Biasiswa Saya dan sahkan anda telah '
               'menerimanya sebelum {response_due}:\n{link}\n\nJika ada pertanyaan, tulis kepada {support}.'
               '\n\n{signoff}'),
        'ta': ('{programme}: உங்களுக்கு ஒரு முறையான கடிதம்',
               'அன்புள்ள {name},\n\n{programme} தொடர்பாக உங்களுக்கு ஒரு முறையான கடிதத்தை அனுப்பியுள்ளோம்: '
               '"{letter_subject}".\n\nஎனது உதவித்தொகை பக்கத்தில் அதைப் படித்து, {response_due}-க்குள் அது '
               'கிடைத்ததை உறுதிசெய்யுங்கள்:\n{link}\n\nகேள்விகள் இருந்தால் {support}-க்கு எழுதுங்கள்.'
               '\n\n{signoff}'),
    },
    # S7b: staff assigned or changed the student's mentor. Switchable (the catalogue): staff can still
    # tell the student themselves. Never sent to the mentor.
    'mentor_assigned': {
        'en': ('You have a mentor: {mentor_name}',
               'Dear {name},\n\nWe have found you a mentor for your {programme}: {mentor_name}.\n\n'
               'Area: {mentor_area}\nLanguages: {mentor_languages}\nContact: {mentor_contact}\n\n'
               'A mentor is someone who can guide you through your studies. You can read more about your '
               'mentor, and see your meetings, on your My Bursary page:\n{link}\n\n'
               'If you have a question, write to {support}.\n\n{signoff}'),
        'ms': ('Anda mempunyai mentor: {mentor_name}',
               'Salam {name},\n\nKami telah menetapkan seorang mentor untuk anda bagi {programme}: '
               '{mentor_name}.\n\nBidang: {mentor_area}\nBahasa: {mentor_languages}\nHubungi: '
               '{mentor_contact}\n\nMentor ialah seseorang yang boleh membimbing anda sepanjang pengajian. '
               'Anda boleh membaca lebih lanjut tentang mentor anda, dan melihat pertemuan anda, di halaman '
               'Biasiswa Saya:\n{link}\n\nJika ada pertanyaan, tulis kepada {support}.\n\n{signoff}'),
        'ta': ('உங்களுக்கு ஒரு வழிகாட்டி: {mentor_name}',
               'அன்புள்ள {name},\n\n{programme}-க்காக உங்களுக்கு ஒரு வழிகாட்டியை நியமித்துள்ளோம்: '
               '{mentor_name}.\n\nதுறை: {mentor_area}\nமொழிகள்: {mentor_languages}\nதொடர்புக்கு: '
               '{mentor_contact}\n\nவழிகாட்டி என்பவர் உங்கள் படிப்பில் ஆலோசனை கூறி உதவக்கூடியவர். உங்கள் '
               'வழிகாட்டியைப் பற்றி மேலும் அறியவும், உங்கள் சந்திப்புகளைப் பார்க்கவும் எனது உதவித்தொகை '
               'பக்கத்தைத் திறவுங்கள்:\n{link}\n\nகேள்விகள் இருந்தால் {support}-க்கு எழுதுங்கள்.'
               '\n\n{signoff}'),
    },
    # S8: an organisation's announcement to its scholars. Switchable (the catalogue): the news is on My
    # Bursary -> News either way. The title and message are the staff member's own, inserted as written.
    'announcement': {
        'en': ('{programme}: {announcement_title}',
               'Dear {name},\n\nThere is news for you from the {programme}:\n\n{announcement_title}\n\n'
               '{announcement_body}\n\nYou can read it again, with earlier news, under News on your My '
               'Bursary page:\n{link}\n\nIf you have a question, write to {support}.\n\n{signoff}'),
        'ms': ('{programme}: {announcement_title}',
               'Salam {name},\n\nAda berita untuk anda daripada {programme}:\n\n{announcement_title}\n\n'
               '{announcement_body}\n\nAnda boleh membacanya semula, bersama berita sebelum ini, di bawah '
               'Berita di halaman Biasiswa Saya:\n{link}\n\nJika ada pertanyaan, tulis kepada {support}.'
               '\n\n{signoff}'),
        'ta': ('{programme}: {announcement_title}',
               'அன்புள்ள {name},\n\n{programme}-இடமிருந்து உங்களுக்கு ஒரு செய்தி:\n\n{announcement_title}'
               '\n\n{announcement_body}\n\nஇதையும் முந்தைய செய்திகளையும் எனது உதவித்தொகை பக்கத்தின் '
               '"செய்திகள்" பகுதியில் மீண்டும் படிக்கலாம்:\n{link}\n\nகேள்விகள் இருந்தால் {support}-க்கு '
               'எழுதுங்கள்.\n\n{signoff}'),
    },
    # S9: a survey for her — the opening email and, 3 days before it closes, the reminder (the same
    # wording; `{survey_note}` says which). Switchable: the survey is on My Bursary -> Surveys either way.
    'survey_open': {
        'en': ('{programme}: {survey_title}',
               'Dear {name},\n\n{survey_note}\n\n{survey_title}\n\nYou can answer it on your My Bursary page, '
               'under Surveys, until {closes_on}:\n{link}\n\nYour answers go to the {programme} team. If you '
               'have a question, write to {support}.\n\n{signoff}'),
        'ms': ('{programme}: {survey_title}',
               'Salam {name},\n\n{survey_note}\n\n{survey_title}\n\nAnda boleh menjawabnya di halaman Biasiswa '
               'Saya, di bawah Tinjauan, sehingga {closes_on}:\n{link}\n\nJawapan anda dihantar kepada pasukan '
               '{programme}. Jika ada pertanyaan, tulis kepada {support}.\n\n{signoff}'),
        'ta': ('{programme}: {survey_title}',
               'அன்புள்ள {name},\n\n{survey_note}\n\n{survey_title}\n\nஎனது உதவித்தொகை பக்கத்தின் '
               '"கணக்கெடுப்புகள்" பகுதியில் {closes_on} வரை இதற்குப் பதிலளிக்கலாம்:\n{link}\n\nஉங்கள் பதில்கள் '
               '{programme} குழுவுக்குச் செல்லும். கேள்விகள் இருந்தால் {support}-க்கு எழுதுங்கள்.\n\n{signoff}'),
    },
    # S10: a development module for her — "it is ready" and, 3 days before its due date, the reminder (the same
    # wording; `{module_note}` says which). Switchable: the module is on My Bursary -> Growth either way.
    'module_published': {
        'en': ('{programme}: {module_title}',
               'Dear {name},\n\n{module_note}\n\n{module_title}\n{due_note}\n\nYou can do it on your My Bursary '
               'page, under Growth:\n{link}\n\nIf you have a question, write to {support}.\n\n{signoff}'),
        'ms': ('{programme}: {module_title}',
               'Salam {name},\n\n{module_note}\n\n{module_title}\n{due_note}\n\nAnda boleh melakukannya di '
               'halaman Biasiswa Saya, di bawah Perkembangan:\n{link}\n\nJika ada pertanyaan, tulis kepada '
               '{support}.\n\n{signoff}'),
        'ta': ('{programme}: {module_title}',
               'அன்புள்ள {name},\n\n{module_note}\n\n{module_title}\n{due_note}\n\nஎனது உதவித்தொகை பக்கத்தின் '
               '"வளர்ச்சி" பகுதியில் இதைச் செய்யலாம்:\n{link}\n\nகேள்விகள் இருந்தால் {support}-க்கு '
               'எழுதுங்கள்.\n\n{signoff}'),
    },
}


#: Month names for a date in a student's email, in her language ("31 January 2027").
MONTHS = {
    'en': ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
           'October', 'November', 'December'),
    'ms': ('Januari', 'Februari', 'Mac', 'April', 'Mei', 'Jun', 'Julai', 'Ogos', 'September',
           'Oktober', 'November', 'Disember'),
    'ta': ('ஜனவரி', 'பிப்ரவரி', 'மார்ச்', 'ஏப்ரல்', 'மே', 'ஜூன்', 'ஜூலை', 'ஆகஸ்ட்', 'செப்டம்பர்',
           'அக்டோபர்', 'நவம்பர்', 'டிசம்பர்'),
}


def format_day(day, lang):
    return f'{day.day} {MONTHS[lang][day.month - 1]} {day.year}'


#: The universal copy rules (tax, urgency) and nothing audience-specific yet.
BANNED = email_templates.UNIVERSAL_BANNED


class StudentCommsError(Exception):
    def __init__(self, code, detail=None):
        self.code, self.detail = code, detail
        super().__init__(code)


def enabled():
    return bool(getattr(settings, 'MAINTENANCE_REMINDERS_ENABLED', False))


def wording(organisation, kind, lang):
    """(subject, body, customised) — the organisation's own row, else the platform default."""
    row = (StudentEmailTemplate.objects.filter(organisation=organisation, kind=kind, language=lang).first()
           if organisation is not None else None)
    if row is not None:
        return row.subject, row.body, True
    subject, body = DEFAULTS[kind][lang]
    return subject, body, False


def templates_payload(organisation):
    """Every (kind, language) for the settings tab — ONE query for the organisation's rows."""
    own = {(r.kind, r.language): r for r in StudentEmailTemplate.objects.filter(organisation=organisation)}
    out = []
    for kind in KINDS:
        for lang in LANGUAGES:
            row = own.get((kind, lang))
            subject, body = DEFAULTS[kind][lang]
            out.append({'key': f'{kind}.{lang}', 'kind': kind, 'language': lang,
                        'subject': row.subject if row else subject, 'body': row.body if row else body,
                        'customised': row is not None, 'placeholders': list(PLACEHOLDERS[kind]),
                        'updated_by_email': row.updated_by_email if row else '',
                        'updated_at': row.updated_at if row else None})
    return out


def save(organisation, kind, lang, subject, body, *, by_email=''):
    """Store the organisation's wording for one (kind, language). Refuses an unknown kind or
    language, an empty subject or body, a token the kind does not supply, or a banned phrase."""
    if kind not in KINDS or lang not in LANGUAGES:
        raise StudentCommsError('unknown_template')
    subject, body = (subject or '').strip(), (body or '').strip()
    if not subject or not body:
        raise StudentCommsError('empty')
    if len(subject) > 255:
        raise StudentCommsError('subject_too_long')
    unknown = email_templates.unknown_placeholders(PLACEHOLDERS[kind], subject, body)
    if unknown:
        raise StudentCommsError('unknown_placeholders', list(unknown))
    banned = email_templates.banned_phrases(BANNED, subject, body)
    if banned:
        raise StudentCommsError('banned_phrase', list(banned))
    row, _ = StudentEmailTemplate.objects.update_or_create(
        organisation=organisation, kind=kind, language=lang,
        defaults={'subject': subject, 'body': body, 'updated_by_email': (by_email or '')[:254]})
    return row


def reset(organisation, kind, lang):
    """Back to the platform default (the organisation's row goes)."""
    StudentEmailTemplate.objects.filter(organisation=organisation, kind=kind, language=lang).delete()


def send_student_email(application, kind, **values):
    """Render `kind` for this student in her language and send it. Returns True when sent; False
    when a switch is off (the platform's `MAINTENANCE_REMINDERS_ENABLED` first, then the
    organisation's own — S6a), she has no address, or the send failed (logged by the sender).
    Every ATTEMPT leaves a `StudentEmailLog` row (the page's "last sent"); a switched-off or
    address-less one leaves none, because nothing was attempted.

    ⚠ The name starts `send_` on purpose: the meter (`emails.shared._meter_email`) names the row
    after the nearest `send_*` caller."""
    from . import student_email_catalogue
    if (kind in PLATFORM_SWITCHED and not enabled()) or not student_email_catalogue.may_send(application, kind):
        return False
    to = (application.notify_email or '').strip()
    if not to:
        return False
    from . import usage
    from .emails.sending import _html_email_shell, _send_html
    b, out_subject, text, html = _compose(application, kind, values)
    with usage.usage_context(application=application):
        ok = _send_html(to, out_subject, text, _html_email_shell(html),
                        from_email=b.email_from, reply_to=[b.email_reply_to])
    if application.owning_organisation_id:
        try:   # review L2: the email has gone; a failed log row must not turn that into an error
            from .models import StudentEmailLog
            StudentEmailLog.objects.create(organisation_id=application.owning_organisation_id,
                                           application=application, key=kind, recipient=to[:254], ok=bool(ok))
        except Exception:   # best-effort, as the docstring says
            import logging
            logging.getLogger('apps.scholarship.student_comms').exception(
                'StudentEmailLog write failed (app %s, %s)', application.id, kind)
    return ok


def language_of(application):
    from .emails.student_decisions import normalise_lang
    return normalise_lang(application.locale)


def _compose(application, kind, values):
    """(branding, subject, text, html) for this student, in her language — the ONE renderer the send
    and the issue dialog's preview share (so the preview cannot drift from the mail)."""
    from . import branding as _branding
    lang = language_of(application)
    b = _branding.for_application(application)
    subject, body, _custom = wording(application.owning_organisation, kind, lang)
    prof = getattr(application, 'profile', None)
    scalars = {'name': (getattr(prof, 'name', '') or '').strip() or '—',
               'programme': b.programme_name(lang), 'link': f'{b.frontend_url}/scholarship/bursary',
               'support': b.email_support, 'signoff': b.team_signoff(lang),
               **{k: _value(v, lang) for k, v in values.items()}}
    out_subject, text, html = email_templates.render(subject, body, scalars, {})
    return b, out_subject, text, html


def preview_student_email(application, kind, **values):
    """(subject, text) as she would receive it — sends nothing (the letters dialog, S6b)."""
    _b, subject, text, _html = _compose(application, kind, values)
    return subject, text


def _value(value, lang):
    import datetime
    if isinstance(value, datetime.date):
        return format_day(value, lang)
    return '' if value is None else str(value)


def send_after_commit(application, kind, **values):
    """Send once the surrounding transaction commits (a rolled-back review sends nothing)."""
    transaction.on_commit(lambda: send_student_email(application, kind, **values))
