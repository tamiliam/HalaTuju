"""Development modules — the two emails (student maintenance Sprint 10, 2026-11-02): "a new module is ready"
once a module goes live, and "you have not finished it" 3 days before its due date, each only when staff asked
for it. The hourly job (`management/commands/send_module_emails.py`, cron `module-emails`) calls
`send_due_module_emails`; the Progress page's "Remind those not done" calls `remind_not_done`.

Sprint 9's `survey_emails.py`, the same shape:
- Once per scholar per kind: a `ModuleEmail` row CLAIMED before the send (unique module x application x kind),
  so the job, a second run and the button can never double.
- Only while the organisation's `module_published` switch is on (`student_email_catalogue.may_send`). The JOB,
  reaching a module with the switch off, records `switched_off` for each scholar and emails nobody, then or
  later. The BUTTON with the switch off refuses (409 `switched_off`) and writes NOTHING (Sprint 9's review
  lesson: rows written by the button would mark everyone "reminded" and the job's reminder would never come).
- Sent through `student_comms.send_student_email` (metered, `StudentEmailLog`), in her language, to the
  scholar only — never a sponsor, a partner or staff.
- The reminder skips anybody done; it needs a due date (no due date, no reminder — the job and the button
  alike). A module archived or taken back to draft mid-run stops at once.
"""
import datetime
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

# The Sprint 8 audience rule, ONE home.
from .announcements import audience_apps
from .development import EMAIL_KEY, MYT, DevelopmentError, is_done, module_status
from .models import DevelopmentModule, ModuleEmail, ModuleProgress

logger = logging.getLogger('apps.scholarship.development_emails')

REMIND_BEFORE = datetime.timedelta(days=3)

#: The line `{module_note}` carries in the ONE module email, in her language.
NOTES = {
    'published': {
        'en': 'A new development module is ready for you. It is optional, short, and made to help you grow.',
        'ms': 'Satu modul pembangunan baharu sedia untuk anda. Ia pilihan, ringkas, dan dibuat untuk membantu '
              'anda berkembang.',
        'ta': 'உங்களுக்காக ஒரு புதிய வளர்ச்சிப் பாடத்தொகுதி தயாராக உள்ளது. இது விருப்பத்தேர்வு; சுருக்கமானது; '
              'நீங்கள் வளர உதவுவதற்காக உருவாக்கப்பட்டது.',
    },
    'reminder': {
        'en': 'A reminder: you have not finished this module yet, and it is due soon.',
        'ms': 'Peringatan: anda belum menamatkan modul ini, dan tarikh akhirnya sudah hampir.',
        'ta': 'நினைவூட்டல்: இந்தப் பாடத்தொகுதியை நீங்கள் இன்னும் முடிக்கவில்லை; இதன் இறுதி நாள் நெருங்குகிறது.',
    },
}


def _reminder_due(m, day):
    return m.due_on is not None and m.due_on - REMIND_BEFORE <= day <= m.due_on


def send_due_module_emails(now=None):
    """The hourly job: each module's "it is ready" email once it is live, and its reminder within 3 days of
    its due date. Returns emails sent."""
    now = now or timezone.now()
    day = timezone.localtime(now, MYT).date()
    sent = 0
    for m in (DevelopmentModule.objects.filter(status='published', email_on_publish=True,
                                               published_emailed_at__isnull=True, publish_at__lte=now)
              .select_related('organisation').order_by('id')):
        try:
            sent += _send_module_kind(m, 'published', mark='published_emailed_at')
        except Exception:   # one module's failure must never stop the others (the cron never 500s)
            logger.exception('module %s: published emails failed', m.id)
    for m in (DevelopmentModule.objects.filter(status='published', remind_before_due=True, reminded_at__isnull=True,
                                               publish_at__lte=now, due_on__isnull=False)
              .select_related('organisation').order_by('id')):
        if not _reminder_due(m, day):
            continue
        try:
            sent += _send_module_kind(m, 'reminder', mark='reminded_at')
        except Exception:
            logger.exception('module %s: reminders failed', m.id)
    return sent


def remind_not_done(m, *, by_email=''):
    """The Progress page's "Remind those not done": the same reminder, now, to each scholar of the audience not
    yet reminded and not done (the claim rows make it idempotent with the job — nobody is reminded twice)."""
    if module_status(m) != 'published':
        raise DevelopmentError('not_live')
    if m.due_on is None:
        raise DevelopmentError('no_due_date')
    from .student_email_catalogue import may_send
    if not may_send(m.organisation, EMAIL_KEY):
        raise DevelopmentError('switched_off')   # writes NOTHING (see the module docstring)
    sent = _send_module_kind(m, 'reminder', mark=None)
    logger.warning('AUDIT module_reminded id=%s org=%s sent=%s by=%s', m.id, m.organisation_id, sent, by_email)
    return sent


def _claim_email(m, app, kind):
    try:
        with transaction.atomic():
            return ModuleEmail.objects.create(module=m, application=app, kind=kind)
    except IntegrityError:
        return None   # already claimed by an earlier (or a parallel) run, or by the button: never twice


def _live_still(m):
    return DevelopmentModule.objects.filter(pk=m.pk, status='published', publish_at__lte=timezone.now()).exists()


def _done_now(m, app):
    lesson_ids = list(m.lessons.values_list('id', flat=True))
    p = ModuleProgress.objects.filter(module=m, application=app).prefetch_related('reads').first()
    return is_done(m, lesson_ids, p)


def _send_module_kind(m, kind, *, mark):
    from . import student_comms
    from .student_email_catalogue import may_send
    apps = list(audience_apps(m.organisation_id, m.programme_id).select_related('profile', 'programme')
                .order_by('id'))
    if kind == 'reminder':
        apps = [a for a in apps if not _done_now(m, a)]
    if not may_send(m.organisation, EMAIL_KEY):
        ModuleEmail.objects.bulk_create(
            [ModuleEmail(module=m, application=a, kind=kind, outcome='switched_off') for a in apps],
            ignore_conflicts=True)
        if mark:
            DevelopmentModule.objects.filter(pk=m.pk).update(**{mark: timezone.now()})
        logger.warning('AUDIT module_email_skipped id=%s org=%s kind=%s reason=switched_off',
                       m.id, m.organisation_id, kind)
        return 0
    sent = 0
    for app in apps:
        if not _live_still(m):
            return sent   # archived or taken back mid-run: nobody else is emailed, and the mark stays empty
        if kind == 'reminder' and _done_now(m, app):
            continue      # finished while the run was going: no reminder, and no claim
        row = _claim_email(m, app, kind)
        if row is None:
            continue
        if not (app.notify_email or '').strip():
            outcome = 'no_address'
        else:
            ok = student_comms.send_student_email(
                app, EMAIL_KEY, module_title=m.title, due_note=_due_note(m, student_comms.language_of(app)),
                module_note=NOTES[kind][student_comms.language_of(app)], link=_growth_link(app))
            outcome = 'sent' if ok else 'failed'
            sent += 1 if ok else 0
        ModuleEmail.objects.filter(pk=row.pk).update(outcome=outcome)
    if mark:
        DevelopmentModule.objects.filter(pk=m.pk).update(**{mark: timezone.now()})
    logger.warning('AUDIT module_emailed id=%s org=%s kind=%s sent=%s', m.id, m.organisation_id, kind, sent)
    return sent


#: "Due by …" in her language — or nothing when the module has no due date.
DUE_LINES = {'en': 'Please finish it by {date}.', 'ms': 'Sila tamatkannya sebelum {date}.',
             'ta': '{date}-க்குள் இதை முடியுங்கள்.'}


def _due_note(m, lang):
    if m.due_on is None:
        return ''
    from .student_comms import format_day
    return DUE_LINES[lang].format(date=format_day(m.due_on, lang))


def _growth_link(app):
    from . import branding
    return f'{branding.for_application(app).frontend_url}/scholarship/bursary?tab=growth'
