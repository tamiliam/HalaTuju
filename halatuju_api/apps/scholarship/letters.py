"""Formal letters on a scholar's file (student maintenance Sprint 6b, 2026-10-31; owner rulings 2026-10-30).

THE DOORS (step 3b) — every way a letter is made, changed or read:
  * ISSUE    — `issue()`: the officer's dialog. Suspension / termination: super or org_admin only;
               general / discipline / close-out: anyone who may WRITE on the case. A typed FULL NAME
               confirms discipline and termination, checked HERE (never only on the page). A closed
               file takes only general and close-out letters.
  * PREVIEW  — `preview()`: renders, writes nothing.
  * WITHDRAW — `withdraw()`: super / org_admin, a reason required. The row stays; nothing is deleted.
  * RESEND   — `send_notice()`: the "a letter has been issued" email again; same rights as issuing.
  * ACKNOWLEDGE / READ — `acknowledge()` / `mark_read()`: the STUDENT, on her own file only
               (`views_bursary._own_file`), never on a withdrawn letter.
  * READERS  — the scholar file's Letters tab and Overview card, the activity log, her My Bursary
               Letters tab and Overview badge, the notice email. NEVER a sponsor or partner endpoint:
               no sponsor, source or partner payload imports this module.

⚠ DOCUMENTS ONLY (owner ruling). Nothing here writes `status`, `maintenance_substate`, a payment run,
a tranche or a sponsorship. A termination letter makes the file PROMPT "Close the file?"; the close is
the file's existing control (`closure.close_application`), with its own rules.

⚠ `emailed_at` is stamped only when the notice email actually went (`send_student_email` returns
True) — the lesson of 2026-10-06: read the best-effort sender's answer; never assume.
"""
import datetime
import logging
import re

from django.db import transaction
from django.utils import timezone

from . import email_templates, letter_defaults
from .models import Letter, LetterTemplate

logger = logging.getLogger('apps.scholarship.letters')

KINDS = ('general', 'discipline', 'suspension', 'termination', 'close_out')
LANGUAGES = ('en', 'ms')
#: Super / org_admin only (owner ruling).
SENIOR_KINDS = frozenset({'suspension', 'termination'})
#: The issuing officer types the student's full name (owner ruling); the server compares.
CONFIRM_KINDS = frozenset({'discipline', 'termination'})
#: What a CLOSED file may still be sent.
CLOSED_FILE_KINDS = frozenset({'general', 'close_out'})
CLAUSE_MAX, NOTE_MAX, REASON_MAX = 40, 2000, 500
#: A letter's wording (review 7): a body this long is not a letter, and a subject is ONE line.
BODY_MAX = 20000
ISSUE_KEY_MAX = 64
#: Resend at most once in this window per letter (review 6).
RESEND_EVERY = datetime.timedelta(minutes=10)
#: Kinds whose notice is not re-sent once the file is closed (review 6): only a general or close-out
#: letter still concerns a closed file.
NO_RESEND_WHEN_CLOSED = frozenset({'discipline', 'suspension', 'termination'})
BANNED = email_templates.UNIVERSAL_BANNED


class LetterError(Exception):
    def __init__(self, code, detail=None):
        self.code, self.detail = code, detail
        super().__init__(code)


# ── wording ─────────────────────────────────────────────────────────────────────────────────────
def letter_wording(organisation, kind, lang):
    """(subject, body, customised) — the organisation's own row, else the platform default."""
    row = (LetterTemplate.objects.filter(organisation=organisation, kind=kind, language=lang).first()
           if organisation is not None else None)
    if row is not None:
        return row.subject, row.body, True
    subject, body = letter_defaults.DEFAULTS[kind][lang]
    return subject, body, False


def templates_payload(organisation):
    """Every (kind, language) for the settings page — one query for the organisation's rows."""
    own = {(r.kind, r.language): r for r in LetterTemplate.objects.filter(organisation=organisation)}
    out = []
    for kind in KINDS:
        for lang in LANGUAGES:
            row = own.get((kind, lang))
            subject, body = letter_defaults.DEFAULTS[kind][lang]
            out.append({'key': f'{kind}.{lang}', 'kind': kind, 'language': lang,
                        'subject': row.subject if row else subject, 'body': row.body if row else body,
                        'customised': row is not None, 'placeholders': list(letter_defaults.PLACEHOLDERS),
                        'updated_by_email': row.updated_by_email if row else '',
                        'updated_at': row.updated_at if row else None})
    return out


def save_template(organisation, kind, lang, subject, body, *, by_email=''):
    if kind not in KINDS or lang not in LANGUAGES:
        raise LetterError('unknown_template')
    subject, body = (subject or '').strip(), (body or '').strip()
    if not subject or not body:
        raise LetterError('empty')
    if len(subject) > 255:
        raise LetterError('subject_too_long')
    if '\r' in subject or '\n' in subject:
        raise LetterError('subject_newline')
    if len(body) > BODY_MAX:
        raise LetterError('body_too_long')
    unknown = email_templates.unknown_placeholders(letter_defaults.PLACEHOLDERS, subject, body)
    if unknown:
        raise LetterError('unknown_placeholders', list(unknown))
    banned = email_templates.banned_phrases(BANNED, subject, body)
    if banned:
        raise LetterError('banned_phrase', list(banned))
    LetterTemplate.objects.update_or_create(
        organisation=organisation, kind=kind, language=lang,
        defaults={'subject': subject, 'body': body, 'updated_by_email': (by_email or '')[:254]})


def reset_template(organisation, kind, lang):
    if kind not in KINDS or lang not in LANGUAGES:
        raise LetterError('unknown_template')
    LetterTemplate.objects.filter(organisation=organisation, kind=kind, language=lang).delete()


# ── rendering ───────────────────────────────────────────────────────────────────────────────────
def response_days(organisation):
    from apps.courses import org_config
    return org_config.value(organisation, 'letter_response_days')


def format_day(day, lang):
    return f'{day.day} {letter_defaults.MONTHS[lang][day.month - 1]} {day.year}'


def student_name(application):
    return (getattr(getattr(application, 'profile', None), 'name', '') or '').strip()


def _render(application, kind, lang, clause, note, *, today, due):
    """(subject, text_body, html_body) for one letter. Refuses wording that needs a clause it lacks."""
    from . import branding as _branding
    subject, body, _custom = letter_wording(application.owning_organisation, kind, lang)
    if not clause and re.search(r'\{clause\}', subject + body):
        raise LetterError('clause_required')
    b = _branding.for_application(application)
    org = application.owning_organisation
    scalars = {'name': student_name(application) or '—', 'programme': b.programme_name(lang),
               'organisation': getattr(org, 'name', '') or b.programme_name(lang),
               'clause': clause, 'date': format_day(today, lang),
               'response_due': format_day(due, lang), 'note': note}
    return email_templates.render(subject, body, scalars, {})


def _clean(clause, note):
    clause = ' '.join(str(clause or '').split())
    note = str(note or '').strip()
    if len(clause) > CLAUSE_MAX:
        raise LetterError('clause_too_long')
    if len(note) > NOTE_MAX:
        raise LetterError('note_too_long')
    return clause, note


def _check(application, kind, lang, allowed_kinds):
    if kind not in KINDS:
        raise LetterError('unknown_kind')
    if lang not in LANGUAGES:
        raise LetterError('unknown_language')
    if kind not in allowed_kinds:
        raise LetterError('forbidden')
    if application.status == 'closed' and kind not in CLOSED_FILE_KINDS:
        raise LetterError('file_closed')


def preview(application, *, kind, language, clause='', note='', allowed_kinds=KINDS):
    """What the dialog shows before issuing — the letter and the notice email. Writes nothing."""
    _check(application, kind, language, allowed_kinds)
    clause, note = _clean(clause, note)
    today = timezone.localdate()
    due = today + datetime.timedelta(days=response_days(application.owning_organisation))
    subject, text, _html = _render(application, kind, language, clause, note, today=today, due=due)
    from . import student_comms
    email_subject, email_body = student_comms.preview_student_email(
        application, 'letter_issued', response_due=due, letter_subject=subject)
    return {'subject': subject, 'body': text, 'response_due_on': due.isoformat(),
            'email': {'language': student_comms.language_of(application),
                      'subject': email_subject, 'body': email_body},
            'needs_confirm': kind in CONFIRM_KINDS}


def names_match(typed, actual):
    """The typed confirm: the full name, ignoring case and runs of spaces. Never a partial match."""
    def norm(s):
        return ' '.join(str(s or '').split()).casefold()
    return bool(norm(actual)) and norm(typed) == norm(actual)


# ── issuing ─────────────────────────────────────────────────────────────────────────────────────
def issue(application, *, kind, language, clause='', note='', confirm_name='', by_admin, allowed_kinds,
          issue_key=None):
    """Issue ONE letter: frozen text, the PDF in the private bucket, an activity line — then, after
    the commit, the notice email (stamped only if it went). Returns `(letter, created)`.

    ⚠ ONCE PER PRESS (review 3): the application row is LOCKED for the issue, and a repeat with the
    same `issue_key` (the dialog's id for one press) returns the letter already issued — no second
    letter, PDF or email. Raises `LetterError` with a code."""
    key = str(issue_key).strip() if issue_key else ''
    if len(key) > ISSUE_KEY_MAX:
        raise LetterError('bad_issue_key')
    _check(application, kind, language, allowed_kinds)
    clause, note = _clean(clause, note)
    if kind in CONFIRM_KINDS and not names_match(confirm_name, student_name(application)):
        raise LetterError('confirm_mismatch')
    today = timezone.localdate()
    due = today + datetime.timedelta(days=response_days(application.owning_organisation))
    subject, text, html = _render(application, kind, language, clause, note, today=today, due=due)
    from . import activity, letters_pdf, storage
    from .models import ScholarshipApplication
    from .models.activity import EVENT_LETTER_ISSUED
    with transaction.atomic():
        ScholarshipApplication.objects.select_for_update().filter(pk=application.pk).first()
        if key:
            existing = Letter.objects.filter(application=application, issue_key=key).first()
            if existing is not None:
                return existing, False
        letter = Letter.objects.create(
            application=application, kind=kind, language=language, subject=subject[:255], body=text,
            clause=clause, note=note, response_due_on=due, issue_key=key or None,
            issued_by_email=(getattr(by_admin, 'email', '') or '')[:254],
            issued_by_name=(getattr(by_admin, 'name', '') or '')[:200],
            issued_by_role=('super' if getattr(by_admin, 'is_super', False)
                            else (getattr(by_admin, 'role', '') or ''))[:20])
        try:
            pdf = letters_pdf.render_pdf(letter, html_body=html)
        except Exception:
            logger.exception('letter PDF failed (app %s, %s)', application.id, kind)
            raise LetterError('pdf_failed')
        # `<org>/<app>/letters/<id>.pdf` — the application id is a SEGMENT (`build_doc_key` prefixes
        # only the organisation), so `scholar_money.own_path` recognises it as this file's own.
        path = storage.build_doc_key(application, application.id, 'letters', f'{letter.id}.pdf')
        if not storage.upload_object(path, pdf, 'application/pdf'):
            raise LetterError('storage_failed')
        letter.pdf_path = path
        letter.save(update_fields=['pdf_path'])
        activity.log_event(application, EVENT_LETTER_ISSUED, actor_email=letter.issued_by_email,
                           meta={'letter_id': letter.id, 'kind': kind, 'subject': letter.subject,
                                 'response_due_on': due.isoformat()})
        transaction.on_commit(lambda: _notice_after_commit(letter.pk))
    return letter, True


def _notice_after_commit(letter_id):
    """The notice email once the letter is saved — and NOTHING it does may raise (review 5): the
    letter IS issued, so a failure here must never turn the officer's request into an error that
    invites a second press. Logged; the row keeps `emailed_at` empty and the tab offers Resend."""
    try:
        letter = Letter.objects.select_related('application').get(pk=letter_id)
        send_notice(letter)
    except Exception:
        logger.exception('letter notice email failed after commit (letter %s)', letter_id)


def send_notice(letter):
    """The "a letter has been issued" email to her (always sent — the catalogue's lock). Stamps
    `emailed_at` / `emailed_to` ONLY when it went. Returns whether it went."""
    from . import student_comms
    application = letter.application
    ok = student_comms.send_student_email(application, 'letter_issued', response_due=letter.response_due_on,
                                          letter_subject=letter.subject)
    if ok:
        Letter.objects.filter(pk=letter.pk).update(
            emailed_at=timezone.now(), emailed_to=(application.notify_email or '').strip()[:254])
    return bool(ok)


def resend(letter, *, allowed_kinds):
    """Send the notice again (review 6): never a withdrawn letter; not a discipline, suspension or
    termination letter once the file is closed; at most once every 10 minutes per letter — the claim
    is ONE conditional update, so two quick presses cannot both send."""
    from django.db.models import Q
    if letter.withdrawn_at is not None:
        raise LetterError('withdrawn')
    if letter.kind not in allowed_kinds:
        raise LetterError('forbidden')
    if letter.application.status == 'closed' and letter.kind in NO_RESEND_WHEN_CLOSED:
        raise LetterError('file_closed')
    now = timezone.now()
    claimed = (Letter.objects.filter(pk=letter.pk)
               .filter(Q(last_resend_at__isnull=True) | Q(last_resend_at__lte=now - RESEND_EVERY))
               .update(last_resend_at=now))
    if not claimed:
        raise LetterError('resend_too_soon')
    return send_notice(letter)


def withdraw(letter, *, reason, by_admin):
    """Withdraw with a reason (super / org_admin — the view's fence). Nothing is deleted."""
    from . import activity
    from .models.activity import EVENT_LETTER_WITHDRAWN
    reason = str(reason or '').strip()
    if not reason:
        raise LetterError('reason_required')
    if len(reason) > REASON_MAX:
        raise LetterError('reason_too_long')
    with transaction.atomic():
        row = Letter.objects.select_for_update().get(pk=letter.pk)
        if row.withdrawn_at is not None:
            raise LetterError('withdrawn')
        row.withdrawn_at = timezone.now()
        row.withdrawn_by_email = (getattr(by_admin, 'email', '') or '')[:254]
        row.withdrawn_by_name = (getattr(by_admin, 'name', '') or '')[:200]
        row.withdrawn_reason = reason
        row.save(update_fields=['withdrawn_at', 'withdrawn_by_email', 'withdrawn_by_name', 'withdrawn_reason'])
        activity.log_event(row.application, EVENT_LETTER_WITHDRAWN, actor_email=row.withdrawn_by_email,
                           meta={'letter_id': row.id, 'kind': row.kind, 'subject': row.subject,
                                 'reason': reason})
    return row


# ── the student ─────────────────────────────────────────────────────────────────────────────────
def acknowledge(letter):
    """She has received and read it (it does not mean she agrees). Once; never a withdrawn letter."""
    from . import activity
    from .models.activity import EVENT_LETTER_ACKNOWLEDGED
    with transaction.atomic():
        row = Letter.objects.select_for_update().get(pk=letter.pk)
        if row.withdrawn_at is not None:
            raise LetterError('withdrawn')
        if row.acknowledged_at is not None:
            return row
        now = timezone.now()
        row.acknowledged_at = now
        row.read_at = row.read_at or now
        row.save(update_fields=['acknowledged_at', 'read_at'])
        activity.log_event(row.application, EVENT_LETTER_ACKNOWLEDGED,
                           meta={'letter_id': row.id, 'kind': row.kind, 'subject': row.subject})
    return row


def mark_read(letter):
    if letter.read_at is None:
        Letter.objects.filter(pk=letter.pk, read_at__isnull=True).update(read_at=timezone.now())


# ── readers ─────────────────────────────────────────────────────────────────────────────────────
def state(letter, today=None):
    """withdrawn | acknowledged | overdue | awaiting — the ONE judgement every surface shows."""
    today = today or timezone.localdate()
    if letter.withdrawn_at is not None:
        return 'withdrawn'
    if letter.acknowledged_at is not None:
        return 'acknowledged'
    return 'overdue' if today > letter.response_due_on else 'awaiting'


def mask_email(address):
    """`a…@gmail.com` — the file shows THAT it went and where, not the whole address."""
    local, _, domain = (address or '').partition('@')
    return f'{local[:1]}…@{domain}' if local and domain else ''


def admin_dict(letter, today=None):
    return {'id': letter.id, 'kind': letter.kind, 'language': letter.language, 'subject': letter.subject,
            'body': letter.body, 'clause': letter.clause, 'issued_at': letter.issued_at,
            'issued_by_name': letter.issued_by_name or letter.issued_by_email,
            'issued_by_role': letter.issued_by_role, 'response_due_on': letter.response_due_on,
            'emailed_at': letter.emailed_at, 'emailed_to': mask_email(letter.emailed_to or ''),
            'acknowledged_at': letter.acknowledged_at, 'withdrawn_at': letter.withdrawn_at,
            'withdrawn_by_name': letter.withdrawn_by_name or letter.withdrawn_by_email,
            'withdrawn_reason': letter.withdrawn_reason, 'state': state(letter, today),
            'has_pdf': bool(letter.pdf_path)}


def student_dict(letter, today=None):
    """HER view: the letter as issued; never who issued it, the email address or a staff note."""
    return {'id': letter.id, 'kind': letter.kind, 'language': letter.language, 'subject': letter.subject,
            'body': letter.body, 'issued_at': letter.issued_at, 'response_due_on': letter.response_due_on,
            'acknowledged_at': letter.acknowledged_at, 'withdrawn_at': letter.withdrawn_at,
            'read': letter.read_at is not None, 'state': state(letter, today),
            'has_pdf': bool(letter.pdf_path)}


def for_file(application):
    return list(Letter.objects.filter(application=application).order_by('-issued_at', '-id'))


def prompt_close(application, letters=None):
    """Show "Close the file?" — a termination letter stands (not withdrawn) and the file is open."""
    rows = letters if letters is not None else for_file(application)
    return application.status != 'closed' and any(
        r.kind == 'termination' and r.withdrawn_at is None for r in rows)


def to_acknowledge(application):
    """How many letters she still has to acknowledge (her Overview badge)."""
    return Letter.objects.filter(application=application, withdrawn_at__isnull=True,
                                 acknowledged_at__isnull=True).count()


def pdf_url(letter):
    """A 300-second signed link to the PDF — only for THIS application's own path (S5a's rule)."""
    from .scholar_money import PDF_URL_SECONDS, own_path
    from .storage import create_signed_download_url
    if not letter.pdf_path or not own_path(letter.pdf_path, letter.application):
        return None
    return create_signed_download_url(letter.pdf_path, expires_in=PDF_URL_SECONDS)


def summary(application):
    """The scholar file's Overview card: counts and the newest three."""
    rows = for_file(application)
    today = timezone.localdate()
    return {'count': len(rows),
            'awaiting': sum(1 for r in rows if state(r, today) in ('awaiting', 'overdue')),
            'overdue': sum(1 for r in rows if state(r, today) == 'overdue'),
            'latest': [{'kind': r.kind, 'subject': r.subject, 'issued_at': r.issued_at,
                        'state': state(r, today)} for r in rows[:3]]}
