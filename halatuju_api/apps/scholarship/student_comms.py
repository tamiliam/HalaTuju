"""The emails a FUNDED student receives about her results (student maintenance S4b, 2026-10-29).

Three kinds, each in the student's language (en / ms / ta), each the ORGANISATION's to word:

  * ``results_due``     — her next result is due soon (the daily `results-due-reminders` job);
  * ``results_overdue`` — a result is past its due date and the grace (the daily `results-overdue-flag`);
  * ``result_queried``  — an officer queried a result she sent, with the officer's note.

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

KINDS = ('results_due', 'results_overdue', 'result_queried')
LANGUAGES = ('en', 'ms', 'ta')

_COMMON = ('name', 'programme', 'link', 'support', 'signoff')
#: The tokens each kind may use — anything else refuses the save (`unknown_placeholders`).
PLACEHOLDERS = {
    'results_due': _COMMON + ('due_date',),
    'results_overdue': _COMMON + ('due_date',),
    'result_queried': _COMMON + ('semester', 'note'),
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
    if not enabled() or not student_email_catalogue.may_send(application, kind):
        return False
    to = (application.notify_email or '').strip()
    if not to:
        return False
    from . import branding as _branding, usage
    from .emails.sending import _html_email_shell, _send_html
    from .emails.student_decisions import normalise_lang
    lang = normalise_lang(application.locale)
    b = _branding.for_application(application)
    subject, body, _custom = wording(application.owning_organisation, kind, lang)
    prof = getattr(application, 'profile', None)
    scalars = {'name': (getattr(prof, 'name', '') or '').strip() or '—',
               'programme': b.programme_name(lang), 'link': f'{b.frontend_url}/scholarship/bursary',
               'support': b.email_support, 'signoff': b.team_signoff(lang),
               **{k: _value(v, lang) for k, v in values.items()}}
    out_subject, text, html = email_templates.render(subject, body, scalars, {})
    with usage.usage_context(application=application):
        ok = _send_html(to, out_subject, text, _html_email_shell(html),
                        from_email=b.email_from, reply_to=[b.email_reply_to])
    if application.owning_organisation_id:
        from .models import StudentEmailLog
        StudentEmailLog.objects.create(organisation_id=application.owning_organisation_id,
                                       application=application, key=kind, recipient=to[:254], ok=bool(ok))
    return ok


def _value(value, lang):
    import datetime
    if isinstance(value, datetime.date):
        return format_day(value, lang)
    return '' if value is None else str(value)


def send_after_commit(application, kind, **values):
    """Send once the surrounding transaction commits (a rolled-back review sends nothing)."""
    transaction.on_commit(lambda: send_student_email(application, kind, **values))
