"""Announcements — the rules (student maintenance Sprint 8, 2026-11-01; owner rulings in docs/decisions.md the
same day). Models: `models/announcements.py`; the staff fence: `views_admin/announcements.py`; her News tab:
`views_bursary.py`; the hourly email job: `management/commands/send_announcement_emails.py`.

WHO POSTS (`may_post`): a super, an organisation admin, an admin — inside their own organisation (the view's
fence). Nobody else. ONE helper, so a future admin permission key narrows it in one place.

WHO SEES ONE (`for_file`) — decided when READ, never stored per scholar:
  * it is LIVE: published, or scheduled with its time passed (`live_q` — visibility never waits for the job);
  * the scholar's file belongs to the announcement's organisation;
  * the audience is everyone, or the scholar's own gift (the Applications gift rule: the application's
    `programme` OR its round's — `programme` is set once, a round moved to another gift keeps the old one);
  * the file is in maintenance, OR it was CLOSED AFTER the announcement went out (read-only: a closed file
    keeps what it was shown, never anything newer).
A scholar who joins later sees the live ones of their audience. A sponsor, partner or source never reads
any of this; no module serving them imports it.

THE EMAIL (`send_due_emails`, hourly): only when staff asked for it, once per scholar (an
`AnnouncementEmail` row CLAIMED before the send), only while the organisation's `announcement` switch is on
(`student_email_catalogue.may_send`), through `student_comms.send_student_email` (metered,
`StudentEmailLog`). Switched off when the job reaches it: nobody is emailed and each scholar's row says
`switched_off`, so switching it on later never sends an old announcement. An edit never emails again; a
withdraw stops the scholars not yet reached.

⚠ READS NEVER WRITE. The job flips a due scheduled announcement to published; the readers do not need it to.
"""
import logging

from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.db.models.functions import Coalesce
from django.utils import dateparse, timezone

from .maintenance_scope import has_file, has_file_q, in_maintenance_q, is_in_maintenance
from .models import Announcement, AnnouncementEmail, AnnouncementRead, ScholarshipApplication

logger = logging.getLogger('apps.scholarship.announcements')

TITLE_MAX = 150
BODY_MAX = 5000
#: Who may post (owner, 2026-11-01). Reviewer, QC, finance, partner, source and mentor are refused.
POSTER_ROLES = ('org_admin', 'admin')
ACTIONS = ('publish', 'schedule', 'draft')
EMAIL_KEY = 'announcement'
#: How many ids one "mark read" may carry (her tab never shows more than this many at once).
MAX_READ_IDS = 200


class AnnouncementError(Exception):
    def __init__(self, code, detail=None):
        self.code, self.detail = code, detail
        super().__init__(code)


def may_post(admin):
    """THE gate for every staff announcement door. A super, an organisation admin, an admin."""
    return admin is not None and bool(admin.is_super or admin.role in POSTER_ROLES)


# ── What is live, and to whom ─────────────────────────────────────────────────────────────────────

def live_q(now):
    """Published, or scheduled with its time passed — the job's flip is never needed to SEE one."""
    return Q(status='published') | Q(status='scheduled', publish_at__lte=now)


def _with_shown_at(qs):
    """`shown_at` — when it went out: `published_at`, else (a scheduled one not yet flipped) `publish_at`."""
    return qs.annotate(shown_at=Coalesce('published_at', 'publish_at'))


def effective_status(a, now=None):
    now = now or timezone.now()
    if a.status == 'scheduled' and a.publish_at is not None and a.publish_at <= now:
        return 'published'
    return a.status


def shown_at(a):
    return a.published_at or (a.publish_at if a.status in ('scheduled', 'published', 'withdrawn') else None)


def _gift_q(programme_id):
    return Q(programme_id=programme_id) | Q(cohort__programme_id=programme_id)


def audience_apps(organisation_id, programme_id):
    """The scholars an announcement is FOR right now: the organisation's files in maintenance, in the gift."""
    qs = ScholarshipApplication.objects.filter(in_maintenance_q(), owning_organisation_id=organisation_id)
    return qs.filter(_gift_q(programme_id)) if programme_id else qs


def can_see_apps(a):
    """The files that may see ``a`` NOW — staff's "read N of M": the audience in maintenance, plus the files
    of the audience closed after it went out."""
    when = shown_at(a)
    if when is None:
        return audience_apps(a.organisation_id, a.programme_id)
    qs = ScholarshipApplication.objects.filter(owning_organisation_id=a.organisation_id).filter(
        in_maintenance_q() | (has_file_q() & Q(status='closed', closed_at__gt=when)))
    return qs.filter(_gift_q(a.programme_id)) if a.programme_id else qs


def for_file(app, now=None):
    """Every announcement ``app`` (her own file, already fenced) may see, pinned first, then newest."""
    if app is None or not app.owning_organisation_id or not has_file(app):
        return Announcement.objects.none()
    now = now or timezone.now()
    gifts = [g for g in (app.programme_id, getattr(app.cohort, 'programme_id', None) if app.cohort_id else None)
             if g]
    qs = _with_shown_at(Announcement.objects.filter(organisation_id=app.owning_organisation_id)
                        .filter(live_q(now)).filter(Q(programme__isnull=True) | Q(programme_id__in=gifts)))
    if not is_in_maintenance(app):
        # Closed (read-only): only what went out BEFORE the file closed.
        if app.closed_at is None:
            return Announcement.objects.none()
        qs = qs.filter(shown_at__lt=app.closed_at)
    return qs.order_by('-pinned', '-shown_at', '-id')


def tab_state(app):
    """``(shown, unread)`` for her hub: the News tab shows when at least one announcement is hers (the
    bursary page's "a tab appears when its module has something for her" rule); unread counts the ones
    never shown to her on the tab."""
    ids = list(for_file(app).values_list('id', flat=True))
    if not ids:
        return False, 0
    read = AnnouncementRead.objects.filter(application=app, announcement_id__in=ids).count()
    return True, len(ids) - read


def news_payload(app):
    """Her News tab — an ALLOWLIST: title, message, pinned, when, edited, new. Never who wrote it, the
    audience, a count or anything about the email."""
    rows = list(for_file(app))
    read = set(AnnouncementRead.objects.filter(application=app, announcement_id__in=[r.id for r in rows])
               .values_list('announcement_id', flat=True))
    return {'organisation': getattr(app.owning_organisation, 'name', '') or '',
            'announcements': [{'id': r.id, 'title': r.title, 'body': r.body, 'pinned': r.pinned,
                               'published_at': r.shown_at, 'edited_at': r.edited_at, 'new': r.id not in read}
                              for r in rows]}


def mark_read(app, ids):
    """Record that her tab showed these. ONLY the ids she may see count — an id guessed from another
    organisation, another gift, a draft or a withdrawn one is silently ignored. Idempotent."""
    if not isinstance(ids, list):
        raise AnnouncementError('bad_ids')
    clean = {i for i in ids[:MAX_READ_IDS] if isinstance(i, int) and not isinstance(i, bool)}
    visible = list(for_file(app).filter(id__in=clean).values_list('id', flat=True))
    AnnouncementRead.objects.bulk_create(
        [AnnouncementRead(announcement_id=i, application=app) for i in visible], ignore_conflicts=True)
    return len(visible)


# ── Writing one (staff) ─────────────────────────────────────────────────────────────────────────

def _clean_text(value, field, limit):
    text = value.strip() if isinstance(value, str) else ''
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if not text:
        raise AnnouncementError(f'{field}_required')
    if len(text) > limit:
        raise AnnouncementError(f'{field}_too_long')
    if field == 'title' and '\n' in text:
        raise AnnouncementError('title_newline')
    return text


def _programme(organisation, code):
    if code in (None, ''):
        return None
    from .models import Programme
    p = Programme.objects.filter(organisation=organisation, code=str(code)).first()
    if p is None:
        raise AnnouncementError('bad_audience')
    return p


def _when(raw, now):
    parsed = dateparse.parse_datetime(raw) if isinstance(raw, str) else None
    if parsed is None:
        raise AnnouncementError('bad_publish_at')
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    if parsed <= now:
        raise AnnouncementError('publish_at_past')
    return parsed


def _bool(data, key, default):
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise AnnouncementError(f'bad_{key}')
    return value


def _apply_action(a, action, data, now):
    if action not in ACTIONS:
        raise AnnouncementError('bad_action')
    if action == 'publish':
        a.status, a.publish_at, a.published_at = 'published', None, now
    elif action == 'schedule':
        a.status, a.publish_at, a.published_at = 'scheduled', _when(data.get('publish_at'), now), None
    else:
        a.status, a.published_at = 'draft', None
        raw = data.get('publish_at')
        a.publish_at = _when(raw, now) if raw else None


def create(organisation, data, *, by_email=''):
    """A new draft, scheduled or published announcement from the form's fields."""
    now = timezone.now()
    a = Announcement(organisation=organisation, created_by_email=(by_email or '')[:254],
                     title=_clean_text(data.get('title'), 'title', TITLE_MAX),
                     body=_clean_text(data.get('body'), 'body', BODY_MAX),
                     programme=_programme(organisation, data.get('programme')),
                     pinned=_bool(data, 'pinned', False), email_requested=_bool(data, 'email', False))
    _apply_action(a, data.get('action'), data, now)
    a.save()
    return a


def _locked(a):
    return Announcement.objects.select_for_update().get(pk=a.pk)


def _flip_if_due(a, now):
    """Inside a write only: a scheduled one whose time has passed becomes published, dated its schedule."""
    if a.status == 'scheduled' and a.publish_at is not None and a.publish_at <= now:
        a.status, a.published_at = 'published', a.publish_at


#: What an edit AFTER publishing may not change: who it is for, whether it is emailed, when it went.
_FIXED_ONCE_OUT = ('programme', 'email', 'action', 'publish_at')


def update(a, data, *, by_email=''):
    """Edit. A draft or a scheduled one (not yet out) may change anything, including publishing it. Once
    it is out, only the title, the message and the pin — and the text change stamps "edited". A withdrawn
    one is final."""
    now = timezone.now()
    with transaction.atomic():
        a = _locked(a)
        _flip_if_due(a, now)
        if a.status == 'withdrawn':
            raise AnnouncementError('withdrawn')
        out = a.status == 'published'
        if out:
            if any(k in data and _changes(a, k, data[k]) for k in _FIXED_ONCE_OUT):
                raise AnnouncementError('published_locked')
        changed_text = False
        if 'title' in data:
            title = _clean_text(data['title'], 'title', TITLE_MAX)
            changed_text |= title != a.title
            a.title = title
        if 'body' in data:
            body = _clean_text(data['body'], 'body', BODY_MAX)
            changed_text |= body != a.body
            a.body = body
        if 'pinned' in data:
            a.pinned = _bool(data, 'pinned', a.pinned)
        if not out:
            if 'programme' in data:
                a.programme = _programme(a.organisation, data.get('programme'))
            if 'email' in data:
                a.email_requested = _bool(data, 'email', a.email_requested)
            if 'action' in data:
                _apply_action(a, data.get('action'), data, now)
        elif changed_text:
            a.edited_at = now
        a.save()
    return a


def _changes(a, key, value):
    if key == 'programme':
        return (value or None) != (a.programme.code if a.programme_id else None)
    if key == 'email':
        return value != a.email_requested
    if key == 'action':
        return value != 'publish'
    return True   # publish_at: a published one's time is history


def withdraw(a, *, by_email=''):
    """Hide a published one from scholars (it stays for staff under Withdrawn). Stops any email not yet sent."""
    now = timezone.now()
    with transaction.atomic():
        a = _locked(a)
        _flip_if_due(a, now)
        if a.status != 'published':
            raise AnnouncementError('not_published')
        a.status, a.withdrawn_at, a.withdrawn_by_email = 'withdrawn', now, (by_email or '')[:254]
        a.save()
    return a


def delete(a):
    """Only a draft or a scheduled one not yet out. A published one is withdrawn, never deleted."""
    now = timezone.now()
    with transaction.atomic():
        a = _locked(a)
        if effective_status(a, now) not in ('draft', 'scheduled'):
            raise AnnouncementError('withdraw_instead')
        a.delete()


# ── The staff page's payload ─────────────────────────────────────────────────────────────────────

def staff_rows(organisation, only_id=None):
    """Every announcement of the organisation (or just ``only_id``), newest first, with its audience size,
    reads and emails."""
    from .mentoring_read import _people, _who
    now = timezone.now()
    qs = Announcement.objects.filter(organisation=organisation).select_related('programme')
    rows = list(qs.filter(pk=only_id) if only_id is not None else qs)
    ids = [a.id for a in rows]
    emails = {}
    for r in (AnnouncementEmail.objects.filter(announcement_id__in=ids)
              .values('announcement_id', 'outcome').annotate(n=Count('id'))):
        emails.setdefault(r['announcement_id'], {})[r['outcome']] = r['n']
    people = _people([a.created_by_email for a in rows])
    out = []
    for a in rows:
        status = effective_status(a, now)
        seen_by = can_see_apps(a)
        e = emails.get(a.id, {})
        out.append({
            'id': a.id, 'title': a.title, 'body': a.body, 'status': status, 'pinned': a.pinned,
            'programme': ({'code': a.programme.code, 'name': a.programme.name_en} if a.programme_id else None),
            'audience_count': seen_by.count(),
            'read_count': (AnnouncementRead.objects.filter(announcement=a, application__in=seen_by).count()
                           if status in ('published', 'withdrawn') else 0),
            'email_requested': a.email_requested, 'emailed_at': a.emailed_at,
            'emailed_count': e.get('sent', 0), 'email_switched_off': e.get('switched_off', 0) > 0,
            'publish_at': a.publish_at, 'published_at': shown_at(a) if status != 'draft' else None,
            'edited_at': a.edited_at, 'withdrawn_at': a.withdrawn_at,
            'author': _who(people, a.created_by_email), 'created_at': a.created_at,
            'can_delete': status in ('draft', 'scheduled'), 'can_withdraw': status == 'published',
        })
    return out


def audiences(organisation):
    """The "For" picker: everyone, then each gift — each with how many scholars it reaches today."""
    from .models import Programme
    out = [{'programme': None, 'name': '', 'count': audience_apps(organisation.id, None).count()}]
    for p in Programme.objects.filter(organisation=organisation).order_by('name_en', 'id'):
        out.append({'programme': p.code, 'name': p.name_en, 'count': audience_apps(organisation.id, p.id).count()})
    return out


# ── The hourly email job ─────────────────────────────────────────────────────────────────────────

def flip_due(now=None):
    """Scheduled ones whose time has passed become published, dated their schedule. Idempotent."""
    now = now or timezone.now()
    return (Announcement.objects.filter(status='scheduled', publish_at__lte=now)
            .update(status='published', published_at=F('publish_at')))


def send_due_emails(now=None):
    """Every published announcement whose email was asked for and not yet done. Returns emails sent."""
    now = now or timezone.now()
    flip_due(now)
    sent = 0
    for a in (Announcement.objects.filter(status='published', email_requested=True, emailed_at__isnull=True)
              .select_related('organisation').order_by('id')):
        try:
            sent += _email_one(a)
        except Exception:   # one announcement's failure must never stop the others (the cron never 500s)
            logger.exception('announcement %s: emails failed', a.id)
    return sent


def _claim(a, app):
    try:
        with transaction.atomic():
            return AnnouncementEmail.objects.create(announcement=a, application=app)
    except IntegrityError:
        return None   # already claimed by an earlier (or a parallel) run: never twice


def _still_live(a):
    return Announcement.objects.filter(pk=a.pk, status='published').exists()


def _email_one(a):
    from . import student_comms
    from .student_email_catalogue import may_send
    apps = list(audience_apps(a.organisation_id, a.programme_id).select_related('profile', 'programme')
                .order_by('id'))
    if not may_send(a.organisation, EMAIL_KEY):
        AnnouncementEmail.objects.bulk_create(
            [AnnouncementEmail(announcement=a, application=app, outcome='switched_off') for app in apps],
            ignore_conflicts=True)
        Announcement.objects.filter(pk=a.pk, status='published').update(emailed_at=timezone.now())
        logger.warning('AUDIT announcement_email_skipped id=%s org=%s reason=switched_off', a.id, a.organisation_id)
        return 0
    sent = 0
    for app in apps:
        if not _still_live(a):
            return sent   # withdrawn mid-run: nobody else is emailed, and emailed_at stays empty
        row = _claim(a, app)
        if row is None:
            continue
        if not (app.notify_email or '').strip():
            outcome = 'no_address'
        else:
            ok = student_comms.send_student_email(
                app, EMAIL_KEY, announcement_title=a.title, announcement_body=a.body,
                link=f'{_frontend(app)}/scholarship/bursary?tab=news')
            outcome = 'sent' if ok else 'failed'
            sent += 1 if ok else 0
        AnnouncementEmail.objects.filter(pk=row.pk).update(outcome=outcome)
    Announcement.objects.filter(pk=a.pk, status='published').update(emailed_at=timezone.now())
    logger.warning('AUDIT announcement_emailed id=%s org=%s sent=%s', a.id, a.organisation_id, sent)
    return sent


def _frontend(app):
    from . import branding
    return branding.for_application(app).frontend_url

