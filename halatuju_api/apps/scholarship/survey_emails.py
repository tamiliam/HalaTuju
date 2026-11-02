"""Surveys — the two emails (student maintenance Sprint 9, 2026-11-02): "it is open" once a survey opens, and
"you have not answered" 3 days before it closes, each only when staff asked for it. The hourly job
(`management/commands/send_survey_emails.py`) calls `send_due_emails`; the Results page's button calls
`remind_now`.

Once per scholar per kind: a `SurveyEmail` row CLAIMED before the send (unique survey x application x kind),
so the job, a second run and the button can never double. Only while the organisation's `survey_open` switch is
on (`student_email_catalogue.may_send`); switched off when reached, each scholar's row says `switched_off` and
nobody is emailed, then or later. Sent through `student_comms.send_student_email` (metered, `StudentEmailLog`).
A survey closed or taken back to draft mid-run stops at once. Never to a sponsor, a partner or staff.
"""
import datetime
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

# The Sprint 8 audience rule, ONE home.
from .announcements import audience_apps
from .models import Survey, SurveyEmail, SurveyResponse
from .surveys import EMAIL_KEY, MYT, SurveyError, effective_status

logger = logging.getLogger('apps.scholarship.survey_emails')

REMIND_BEFORE = datetime.timedelta(days=3)

#: The line `{survey_note}` carries in the ONE survey email, in her language.
NOTES = {
    'open': {
        'en': 'A new survey is open for you. It takes a few minutes, and your answers help us support you.',
        'ms': 'Satu tinjauan baharu dibuka untuk anda. Ia mengambil masa beberapa minit, dan jawapan anda '
              'membantu kami menyokong anda.',
        'ta': 'உங்களுக்காக ஒரு புதிய கணக்கெடுப்பு திறக்கப்பட்டுள்ளது. இதற்குச் சில நிமிடங்களே ஆகும்; '
              'உங்கள் பதில்கள் உங்களுக்கு உதவ எங்களுக்குத் துணைபுரியும்.',
    },
    'reminder': {
        'en': 'A reminder: you have not answered this survey yet, and it closes soon.',
        'ms': 'Peringatan: anda belum menjawab tinjauan ini, dan ia akan ditutup tidak lama lagi.',
        'ta': 'நினைவூட்டல்: இந்தக் கணக்கெடுப்புக்கு நீங்கள் இன்னும் பதிலளிக்கவில்லை; இது விரைவில் மூடப்படும்.',
    },
}


def send_due_emails(now=None):
    """The hourly job: each survey's "it is open" email once it opens, and its reminder once it is within
    3 days of closing. Returns emails sent."""
    now = now or timezone.now()
    sent = 0
    for s in (Survey.objects.filter(status='published', email_on_open=True, opened_emailed_at__isnull=True,
                                    opens_at__lte=now).select_related('organisation').order_by('id')):
        try:
            if s.closes_at <= now:   # closed before the job reached it: nothing to open
                Survey.objects.filter(pk=s.pk).update(opened_emailed_at=now)
                continue
            sent += _send_kind(s, 'open', mark='opened_emailed_at')
        except Exception:   # one survey's failure must never stop the others (the cron never 500s)
            logger.exception('survey %s: opening emails failed', s.id)
    for s in (Survey.objects.filter(status='published', remind_before_close=True, reminded_at__isnull=True,
                                    opens_at__lte=now, closes_at__gt=now, closes_at__lte=now + REMIND_BEFORE)
              .select_related('organisation').order_by('id')):
        try:
            sent += _send_kind(s, 'reminder', mark='reminded_at')
        except Exception:
            logger.exception('survey %s: reminders failed', s.id)
    return sent


def remind_now(s, *, by_email=''):
    """The Results page's "Remind those who have not answered": the same reminder, now, to each scholar not
    yet reminded (the claim rows make it idempotent with the job — nobody is reminded twice)."""
    if effective_status(s) != 'open':
        raise SurveyError('not_open')
    from .student_email_catalogue import may_send
    if not may_send(s.organisation, EMAIL_KEY):
        # Review 2: the BUTTON writes nothing when the switch is off — `switched_off` rows would mark every
        # scholar "reminded" and the hourly reminder would never come. Only the job records switched_off.
        raise SurveyError('switched_off')
    sent = _send_kind(s, 'reminder', mark=None)
    logger.warning('AUDIT survey_reminded id=%s org=%s sent=%s by=%s', s.id, s.organisation_id, sent, by_email)
    return sent


def _claim(s, app, kind):
    try:
        with transaction.atomic():
            return SurveyEmail.objects.create(survey=s, application=app, kind=kind)
    except IntegrityError:
        return None   # already claimed by an earlier (or a parallel) run, or by the button: never twice


def _still_open(s):
    return Survey.objects.filter(pk=s.pk, status='published', closes_at__gt=timezone.now()).exists()


def _answered(s, app):
    return SurveyResponse.objects.filter(survey_id=s.pk, application_id=app.pk).exists()


def _send_kind(s, kind, *, mark):
    from . import student_comms
    from .student_email_catalogue import may_send
    apps = audience_apps(s.organisation_id, s.programme_id).select_related('profile', 'programme').order_by('id')
    if kind == 'reminder':
        apps = apps.exclude(id__in=SurveyResponse.objects.filter(survey_id=s.pk).values('application_id'))
    apps = list(apps)
    if not may_send(s.organisation, EMAIL_KEY):
        SurveyEmail.objects.bulk_create(
            [SurveyEmail(survey=s, application=app, kind=kind, outcome='switched_off') for app in apps],
            ignore_conflicts=True)
        if mark:
            Survey.objects.filter(pk=s.pk).update(**{mark: timezone.now()})
        logger.warning('AUDIT survey_email_skipped id=%s org=%s kind=%s reason=switched_off',
                       s.id, s.organisation_id, kind)
        return 0
    closes_on = timezone.localtime(s.closes_at, MYT).date()
    sent = 0
    for app in apps:
        if not _still_open(s):
            return sent   # closed or taken back mid-run: nobody else is emailed, and the mark stays empty
        if kind == 'reminder' and _answered(s, app):
            continue      # answered while the run was going: no reminder, and no claim
        row = _claim(s, app, kind)
        if row is None:
            continue
        if not (app.notify_email or '').strip():
            outcome = 'no_address'
        else:
            ok = student_comms.send_student_email(
                app, EMAIL_KEY, survey_title=s.title, closes_on=closes_on,
                survey_note=NOTES[kind][student_comms.language_of(app)],
                link=_surveys_link(app))
            outcome = 'sent' if ok else 'failed'
            sent += 1 if ok else 0
        SurveyEmail.objects.filter(pk=row.pk).update(outcome=outcome)
    if mark:
        Survey.objects.filter(pk=s.pk).update(**{mark: timezone.now()})
    logger.warning('AUDIT survey_emailed id=%s org=%s kind=%s sent=%s', s.id, s.organisation_id, kind, sent)
    return sent


def _surveys_link(app):
    from . import branding
    return f'{branding.for_application(app).frontend_url}/scholarship/bursary?tab=surveys'
