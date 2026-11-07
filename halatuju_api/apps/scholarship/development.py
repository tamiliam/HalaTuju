"""Development modules — the rules (student maintenance Sprint 10, 2026-11-02; owner rulings in docs/decisions.md
the same day). Models: `models/development.py`; staff payloads (rows, progress, CSV, review, the scholar file's
Growth tab, the mentor's view): `development_progress.py`; files (keys, the type sniff, signed URLs):
`development_files.py`; the emails: `development_emails.py` (the hourly job:
`management/commands/send_module_emails.py`); the staff fence: `views_admin/development.py`; her Growth tab:
`views_bursary.py`. Sprint 9's surveys are the pattern (`surveys.py`): the same makers, the same audience rule,
the same claim-before-send email.

WHO MAKES ONE (`may_make`): a super, an organisation admin, an admin — inside their own organisation (the view's
fence). Nobody else. ONE helper, so a future permission key narrows it in one place.

THE STATUS (`module_status`): draft and archived are stored; a published module reads `scheduled` before
`publish_at`, then `published`. Publishing with a time in the past (or "now") goes live NOW.

WHO SEES ONE (`modules_for_file`) — decided when READ, never stored per scholar:
  * it has gone live (`publish_at` passed) and is published — or archived / her file closed, but ONLY when she
    has STARTED it (a `ModuleProgress` row): she keeps a read-only sight of her own work, nothing new;
  * her file belongs to the module's organisation, and the audience is everyone or her own gift (the
    application's `programme` OR its round's — the Sprint 8 rule);
  * never a draft, never a scheduled one, never another organisation's, never a non-scholar's.
A sponsor, partner or source never reads any of this; no module serving them imports it.

HER WORK (`mark_lesson_read`, `submit_task`): only while the module is published and her file is in maintenance.
"I have read this" is idempotent (one `LessonRead` per progress x lesson). The task comes after every current
lesson is read (409 `lessons_first`); she may change it until staff mark it reviewed (409 `reviewed`). Writes
run under a lock on the module row, so a staff edit of the lessons never interleaves with her read.

THE LOCKS (owner rulings): the TASK TYPE locks once any scholar has started (409 `task_locked`); so do the
audience, the publishing time and "back to draft" (409 `started_locked`). Lesson text may still be fixed, and
lessons may be ADDED or REMOVED after a start (recommended and built): progress is per lesson id, so "done" =
every CURRENT lesson read + the task sent. A removed lesson takes its reads with it. Delete only a draft or a
module nobody started (409 `archive_instead`); otherwise archive it.

⚠ OPTIONAL FOR SCHOLARS. Nothing here touches money, standing or eligibility. READS NEVER WRITE.
"""
import logging
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Q
from django.utils import dateparse, timezone

from .maintenance_scope import has_file, is_in_maintenance
from .models import DevelopmentModule, LessonRead, ModuleLesson, ModuleProgress

logger = logging.getLogger('apps.scholarship.development')

TITLE_MAX = 150
SUMMARY_MAX = 500
LESSON_TITLE_MAX = 150
LESSON_BODY_MAX = 10000
MAX_LESSONS = 20
PROMPT_MAX = 1000
REFLECTION_MAX = 5000
VIDEO_MAX = 500
TASK_KINDS = ('none', 'reflection', 'upload')
#: YouTube or Vimeo only (owner ruling): shown as a link that opens a new tab, never embedded.
VIDEO_HOSTS = frozenset({'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be',
                         'vimeo.com', 'www.vimeo.com', 'player.vimeo.com'})
ACTIONS = ('publish', 'draft')
EMAIL_KEY = 'module_published'
MYT = ZoneInfo('Asia/Kuala_Lumpur')


class DevelopmentError(Exception):
    def __init__(self, code, detail=None):
        self.code, self.detail = code, detail
        super().__init__(code)


def may_make(admin):
    """THE gate for every staff module door. A super, an organisation admin, an admin."""
    # Who may make one (owner, 2026-11-02). Team tables T5c: the v2 key `development.edit` (it implies
    # `.view`; this one door both reads and writes). Holders as T1: super, org_admin, the `admin` label.
    from apps.courses import staff_tables
    return staff_tables.opens_door(admin, 'development')


def may_read(admin):
    """The READ of the staff module pages and the scholar file's Growth tab (A1.10a, TD-498):
    `development.view`. Today the same holders as `may_make`."""
    from apps.courses import staff_tables
    return staff_tables.opens_door(admin, 'development_read')


def today():
    return timezone.localtime(timezone.now(), MYT).date()


# ── Status, audience, who sees one ────────────────────────────────────────────────────────────────

def module_status(m, now=None):
    now = now or timezone.now()
    if m.status in ('draft', 'archived'):
        return m.status
    if m.publish_at is None or now < m.publish_at:
        return 'scheduled'
    return 'published'


def has_started(m):
    return ModuleProgress.objects.filter(module_id=m.pk).exists()


def modules_for_file(app, now=None):
    """Every module ``app`` (her own file, already fenced) may see: live ones while in maintenance, and any she
    started (read-only once archived or once her file closed). Never a draft or a scheduled one."""
    if app is None or not app.owning_organisation_id or not has_file(app):
        return DevelopmentModule.objects.none()
    now = now or timezone.now()
    gifts = [g for g in (app.programme_id, getattr(app.cohort, 'programme_id', None) if app.cohort_id else None)
             if g]
    started = Q(pk__in=ModuleProgress.objects.filter(application_id=app.pk).values('module_id'))
    qs = (DevelopmentModule.objects.filter(organisation_id=app.owning_organisation_id,
                                           status__in=('published', 'archived'), publish_at__lte=now)
          .filter(Q(programme__isnull=True) | Q(programme_id__in=gifts)))
    if is_in_maintenance(app):
        return qs.filter(Q(status='published') | started)
    return qs.filter(started)


def can_act(m, app, now=None):
    """She may read on and send her task: the module is live and her file is in maintenance."""
    return module_status(m, now) == 'published' and is_in_maintenance(app)


def is_done(m, lesson_ids, progress):
    """THE rule: every CURRENT lesson read, and the task sent when there is one."""
    if progress is None:
        return False
    read = {r.lesson_id for r in progress.reads.all()}
    return set(lesson_ids) <= read and (m.task_kind == 'none' or progress.task_sent_at is not None)


def _file_out(name, ctype, size):
    return {'name': name, 'type': ctype, 'size': size}


def visible_module(app, module_id, now=None):
    if isinstance(module_id, bool) or not isinstance(module_id, int):
        return None
    return modules_for_file(app, now).filter(pk=module_id).first()


def student_modules(app):
    """Her Growth tab — an ALLOWLIST: title, summary, due date, how far she is, whether staff reviewed it.
    Never who wrote it, the audience, a count, anybody else's work or anything about the email. The ones she
    can still do first (due soonest), then the rest, newest first."""
    now = timezone.now()
    mods = list(modules_for_file(app, now).prefetch_related('lessons'))
    progress = {p.module_id: p for p in ModuleProgress.objects.filter(
        application_id=app.pk, module_id__in=[m.id for m in mods]).prefetch_related('reads')}
    live = is_in_maintenance(app)
    out = []
    for m in mods:
        ids = [x.id for x in m.lessons.all()]
        p = progress.get(m.id)
        read = {r.lesson_id for r in p.reads.all()} if p else set()
        out.append({'id': m.id, 'title': m.title, 'summary': m.summary, 'due_on': m.due_on,
                    'task_kind': m.task_kind, 'lessons': len(ids), 'read': len(read & set(ids)),
                    'done': is_done(m, ids, p), 'started': p is not None,
                    'can_act': live and module_status(m, now) == 'published',
                    'task_sent_at': p.task_sent_at if p else None,
                    'reviewed': bool(p and p.reviewed_at), '_at': m.publish_at})
    out.sort(key=lambda r: (not (r['can_act'] and not r['done']), r['due_on'] is None,
                            r['due_on'] or today(), -r['_at'].timestamp()))
    for r in out:
        del r['_at']
    return {'organisation': getattr(app.owning_organisation, 'name', '') or '', 'modules': out}


def student_module(app, module_id):
    """One module as she opens it (allowlist), or None (404): each lesson (with "read"), and the task with her
    own answer and — once staff reviewed it — their comment."""
    now = timezone.now()
    m = visible_module(app, module_id, now)
    if m is None:
        return None
    lessons = list(m.lessons.all())
    p = ModuleProgress.objects.filter(module=m, application=app).prefetch_related('reads').first()
    read = {r.lesson_id for r in p.reads.all()} if p else set()
    acting = can_act(m, app, now)
    reviewed = bool(p and p.reviewed_at)
    task = {'kind': m.task_kind, 'prompt': m.task_prompt if m.task_kind != 'none' else '',
            'text': p.task_text if p else '',
            'file': (_file_out(p.task_file_name, p.task_file_type, p.task_file_size)
                     if p and p.task_file_path else None),
            'sent_at': p.task_sent_at if p else None,
            'reviewed_at': p.reviewed_at if reviewed else None,
            'comment': p.review_comment if reviewed else '',
            'can_change': acting and m.task_kind != 'none' and not reviewed
            and {x.id for x in lessons} <= read}
    return {'id': m.id, 'title': m.title, 'summary': m.summary, 'due_on': m.due_on, 'can_act': acting,
            'done': is_done(m, [x.id for x in lessons], p),
            'lessons': [{'id': x.id, 'title': x.title, 'body': x.body, 'video_url': x.video_url,
                         'file': _file_out(x.file_name, x.file_type, x.file_size) if x.file_path else None,
                         'read': x.id in read} for x in lessons],
            'task': task}


def growth_tab_state(app):
    """``(shown, to_do)`` for her hub: the Growth tab shows when a module is hers (live, or one she started —
    the bursary "a tab appears when its module has something for her" rule); ``to_do`` counts the live ones
    she has not finished (the red number)."""
    data = student_modules(app)['modules']
    if not data:
        return False, 0
    return True, sum(1 for r in data if r['can_act'] and not r['done'])


# ── Her work ──────────────────────────────────────────────────────────────────────────────────────

def _locked_module(pk):
    """The module row under `select_for_update`, or `not_found` (deleted since the caller read it)."""
    m = DevelopmentModule.objects.filter(pk=pk).select_for_update().first()
    if m is None:
        raise DevelopmentError('not_found')
    return m


def _locked_live(app, module_id):
    """Inside a transaction: the module row locked, re-checked as hers (404) and live for her (409)."""
    m = _locked_module(module_id)
    if not modules_for_file(app).filter(pk=m.pk).exists():
        raise DevelopmentError('not_found')
    if not can_act(m, app):
        raise DevelopmentError('module_closed')
    return m


def _progress(m, app):
    """Her progress row, locked; made at her first act (the module row lock keeps it to one)."""
    p = ModuleProgress.objects.filter(module=m, application=app).select_for_update().first()
    return p or ModuleProgress.objects.create(module=m, application=app)


def mark_lesson_read(app, module_id, lesson_id):
    """"I have read this" — idempotent. Only a lesson of a module she may see (404 otherwise), only while it is
    live and her file is in maintenance (409 `module_closed`)."""
    if visible_module(app, module_id) is None:
        raise DevelopmentError('not_found')
    with transaction.atomic():
        m = _locked_live(app, module_id)
        lesson = ModuleLesson.objects.filter(pk=lesson_id, module=m).first() if isinstance(lesson_id, int) else None
        if lesson is None:
            raise DevelopmentError('not_found')
        p = _progress(m, app)
        LessonRead.objects.get_or_create(progress=p, lesson=lesson)
    return p


def _reflection(raw):
    text = raw.strip().replace('\r\n', '\n').replace('\r', '\n') if isinstance(raw, str) else ''
    if not text:
        raise DevelopmentError('text_required')
    if len(text) > REFLECTION_MAX:
        raise DevelopmentError('text_too_long')
    return text


def _may_send_task(m, p):
    if m.task_kind == 'none':
        raise DevelopmentError('no_task')
    if p is not None and p.reviewed_at is not None:
        raise DevelopmentError('reviewed')
    read = set(p.reads.values_list('lesson_id', flat=True)) if p is not None else set()
    if not set(m.lessons.values_list('id', flat=True)) <= read:
        raise DevelopmentError('lessons_first')


def task_upload_allowed(app, module_id):
    """The module IFF she may upload her task now — the SAME checks as sending it (S10 review 3): a module she
    may see (404), live and her file in maintenance (`module_closed`), an upload task (`no_task`), every
    current lesson read (`lessons_first`), not yet reviewed (`reviewed`). Nothing is signed otherwise."""
    m = visible_module(app, module_id)
    if m is None:
        raise DevelopmentError('not_found')
    if not can_act(m, app):
        raise DevelopmentError('module_closed')
    if m.task_kind != 'upload':
        raise DevelopmentError('no_task')
    _may_send_task(m, ModuleProgress.objects.filter(module=m, application=app).first())
    return m


def submit_task(app, module_id, data):
    """Send (or change) her task: a reflection `{text}` or a file `{storage_path, original_filename}` she PUT
    to the signed upload URL (`development_files.task_upload_url`). The file is checked by its BYTES (type and
    size) before anything is written. Refusals: not_found, module_closed, no_task, lessons_first, reviewed,
    text_required, text_too_long, bad_path, upload_incomplete, file_too_large, unsupported_format."""
    from . import development_files as files
    m = visible_module(app, module_id)
    if m is None:
        raise DevelopmentError('not_found')
    if not can_act(m, app):
        raise DevelopmentError('module_closed')
    data = data if isinstance(data, dict) else {}
    p = ModuleProgress.objects.filter(module=m, application=app).first()
    _may_send_task(m, p)
    text, upload = '', None
    if m.task_kind == 'reflection':
        text = _reflection(data.get('text'))
    else:
        path = data.get('storage_path')
        if not files.is_task_path(app, m, path):
            raise DevelopmentError('bad_path')
        ctype, size = files.verify(path)      # downloads and sniffs; a bad file is removed and refused
        upload = {'path': path, 'name': files.clean_name(data.get('original_filename')), 'type': ctype,
                  'size': size}
    old = ''
    try:
        with transaction.atomic():
            m = _locked_live(app, m.pk)
            p = _progress(m, app)
            _may_send_task(m, p)
            if upload is None:
                p.task_text = text
            else:
                old = p.task_file_path if p.task_file_path != upload['path'] else ''
                p.task_file_path, p.task_file_name = upload['path'], upload['name']
                p.task_file_type, p.task_file_size = upload['type'], upload['size']
            p.task_sent_at = timezone.now()
            p.save()
    except DevelopmentError:
        # Refused under the lock: the new object must not linger — unless it is the file already on record.
        if upload is not None and not ModuleProgress.objects.filter(task_file_path=upload['path']).exists():
            files.discard([upload['path']])
        raise
    if old:
        files.discard([old])                  # her replaced file goes (or the orphan sweep finds it)
    logger.info('AUDIT module_task_sent module=%s app=%s kind=%s', m.id, app.id, m.task_kind)
    return p


# ── Writing one (staff) ───────────────────────────────────────────────────────────────────────────

def _field_text(value, field, limit, *, required=True, one_line=False):
    text = value.strip() if isinstance(value, str) else ''
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if not text and required:
        raise DevelopmentError(f'{field}_required')
    if len(text) > limit:
        raise DevelopmentError(f'{field}_too_long')
    if one_line and '\n' in text:
        raise DevelopmentError(f'{field}_newline')
    return text


def clean_video(raw):
    """A YouTube or Vimeo `https` link, or ''. Anything else is `bad_video` — never a credential, a port, a
    look-alike host (`youtube.com.example`) or a backslash trick."""
    url = raw.strip() if isinstance(raw, str) else ''
    if not url:
        return ''
    if len(url) > VIDEO_MAX:
        raise DevelopmentError('video_too_long')
    if any(c.isspace() or c == '\\' or ord(c) < 32 for c in url):
        raise DevelopmentError('bad_video')
    try:
        parts = urlsplit(url)
        host, port = (parts.hostname or '').lower(), parts.port
    except ValueError:
        raise DevelopmentError('bad_video')
    if parts.scheme != 'https' or host not in VIDEO_HOSTS or parts.username or parts.password or port:
        raise DevelopmentError('bad_video')
    return url


def clean_lessons(raw):
    """The lessons as staff sent them, in order: up to 20, each `{id?, title, body, video_url}` — a title (one
    line, <= 150), text (<= 10,000), an optional YouTube / Vimeo link."""
    if not isinstance(raw, list):
        raise DevelopmentError('bad_lessons')
    if len(raw) > MAX_LESSONS:
        raise DevelopmentError('too_many_lessons')
    out, seen = [], set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise DevelopmentError('bad_lessons', i)
        lid = item.get('id')
        if lid is not None and (isinstance(lid, bool) or not isinstance(lid, int) or lid in seen):
            raise DevelopmentError('bad_lesson', i)
        seen.add(lid)
        try:
            out.append({'id': lid,
                        'title': _field_text(item.get('title'), 'lesson_title', LESSON_TITLE_MAX, one_line=True),
                        'body': _field_text(item.get('body') or '', 'lesson_body', LESSON_BODY_MAX, required=False),
                        'video_url': clean_video(item.get('video_url'))})
        except DevelopmentError as e:
            raise DevelopmentError(e.code, i)
    return out


def _apply_lessons(m, cleaned):
    """Make the module's lessons exactly ``cleaned`` (kept by id, added, removed, reordered). Returns the file
    keys of removed lessons, for the caller to delete once the transaction commits."""
    have = {x.id: x for x in m.lessons.all()}
    if any(c['id'] is not None and c['id'] not in have for c in cleaned):
        raise DevelopmentError('bad_lesson')
    keep = {c['id'] for c in cleaned if c['id'] is not None}
    gone = [x for lid, x in have.items() if lid not in keep]
    for pos, c in enumerate(cleaned, start=1):
        lesson = have.get(c['id']) if c['id'] is not None else ModuleLesson(module=m)
        if c['video_url'] and lesson.file_path:
            raise DevelopmentError('video_or_file', pos - 1)
        lesson.position, lesson.title, lesson.body, lesson.video_url = pos, c['title'], c['body'], c['video_url']
        lesson.save()
    ModuleLesson.objects.filter(pk__in=[x.id for x in gone]).delete()
    return [x.file_path for x in gone if x.file_path]


def _gift(organisation, code):
    if code in (None, ''):
        return None
    from .models import Programme
    p = Programme.objects.filter(organisation=organisation, code=str(code)).first()
    if p is None:
        raise DevelopmentError('bad_audience')
    return p


def _publish_time(raw):
    parsed = dateparse.parse_datetime(raw) if isinstance(raw, str) else None
    if parsed is None:
        raise DevelopmentError('bad_publish_at')
    return timezone.make_aware(parsed, MYT) if timezone.is_naive(parsed) else parsed


def _due(raw):
    if raw in (None, ''):
        return None
    parsed = dateparse.parse_date(raw) if isinstance(raw, str) else None
    if parsed is None:
        raise DevelopmentError('bad_due_on')
    return parsed


def _flag(data, key, default):
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise DevelopmentError(f'bad_{key}')
    return value


def _check(m, now):
    """The whole module, before it is saved. A published (or scheduled) one has a lesson and, for a reflection,
    a prompt; a due date is never before it goes live; "remind" needs a due date."""
    if m.task_kind not in TASK_KINDS:
        raise DevelopmentError('bad_task_kind')
    if m.remind_before_due and m.due_on is None:
        raise DevelopmentError('remind_needs_due')
    if m.status != 'published':
        return
    if not m.lessons.exists():
        raise DevelopmentError('no_lessons')
    if m.task_kind == 'reflection' and not m.task_prompt:
        raise DevelopmentError('prompt_required')
    if m.due_on is not None and m.due_on < timezone.localtime(m.publish_at or now, MYT).date():
        raise DevelopmentError('due_before_publish')


def _publish(m, now):
    m.status = 'published'
    if m.publish_at is None or m.publish_at < now:
        m.publish_at = now   # "now": an earlier time would read as if it had been live all along


def create_module(organisation, data, *, by_email=''):
    """A new draft or published module from the form's fields (and its lessons)."""
    from . import development_files as files
    now = timezone.now()
    action = data.get('action')
    if action not in ACTIONS:
        raise DevelopmentError('bad_action')
    lessons = clean_lessons(data.get('lessons', []))
    if any(c['id'] is not None for c in lessons):
        raise DevelopmentError('bad_lesson')
    m = DevelopmentModule(
        organisation=organisation, created_by_email=(by_email or '')[:254],
        title=_field_text(data.get('title'), 'title', TITLE_MAX, one_line=True),
        summary=_field_text(data.get('summary') or '', 'summary', SUMMARY_MAX, required=False),
        programme=_gift(organisation, data.get('programme')),
        publish_at=_publish_time(data['publish_at']) if data.get('publish_at') else None,
        due_on=_due(data.get('due_on')), task_kind=data.get('task_kind') or 'none',
        task_prompt=_field_text(data.get('task_prompt') or '', 'prompt', PROMPT_MAX, required=False),
        email_on_publish=_flag(data, 'email_on_publish', False), remind_before_due=_flag(data, 'remind', False))
    if m.task_kind not in TASK_KINDS:
        raise DevelopmentError('bad_task_kind')
    if m.task_kind == 'none':
        m.task_prompt = ''
    with transaction.atomic():
        m.save()
        files.discard_after_commit(_apply_lessons(m, lessons))
        if action == 'publish':
            _publish(m, now)
        _check(m, now)
        m.save()
    return m


def update_module(m, data, *, by_email=''):
    """Edit. Before anybody starts, anything may change (and a draft may be published, a published one taken
    back to draft, an archived one put back). From the first start the task type, the audience, the
    publishing time and "back to draft" are locked; titles, texts, lessons, the due date, the prompt and the
    email choices still change."""
    from . import development_files as files
    now = timezone.now()
    with transaction.atomic():
        m = _locked_module(m.pk)
        started = has_started(m)
        if 'title' in data:
            m.title = _field_text(data['title'], 'title', TITLE_MAX, one_line=True)
        if 'summary' in data:
            m.summary = _field_text(data['summary'] or '', 'summary', SUMMARY_MAX, required=False)
        if 'task_kind' in data and data['task_kind'] != m.task_kind:
            if data['task_kind'] not in TASK_KINDS:
                raise DevelopmentError('bad_task_kind')
            if started:
                raise DevelopmentError('task_locked')
            m.task_kind = data['task_kind']
        if 'task_prompt' in data:
            m.task_prompt = _field_text(data['task_prompt'] or '', 'prompt', PROMPT_MAX, required=False)
        if m.task_kind == 'none':
            m.task_prompt = ''
        if 'due_on' in data:
            m.due_on = _due(data['due_on'])
        if 'email_on_publish' in data:
            m.email_on_publish = _flag(data, 'email_on_publish', m.email_on_publish)
        if 'remind' in data:
            m.remind_before_due = _flag(data, 'remind', m.remind_before_due)
        if 'programme' in data:
            programme = _gift(m.organisation, data.get('programme'))
            if programme != m.programme:
                if started:
                    raise DevelopmentError('started_locked')
                m.programme = programme
        if data.get('publish_at') or data.get('publish_now') is True:
            when = now if data.get('publish_now') is True else _publish_time(data['publish_at'])
            if when != m.publish_at and module_status(m, now) != 'published':
                if started:
                    raise DevelopmentError('started_locked')
                m.publish_at = when
        if 'lessons' in data:
            files.discard_after_commit(_apply_lessons(m, clean_lessons(data['lessons'])))
        action = data.get('action')
        if action is not None and action not in ACTIONS:
            raise DevelopmentError('bad_action')
        if action == 'publish' and m.status in ('draft', 'archived'):
            if m.status == 'archived':
                m.status, m.archived_at = 'published', None   # put back: live again, at its old time
            else:
                _publish(m, now)
        elif action == 'draft' and m.status != 'draft':
            if started:
                raise DevelopmentError('started_locked')
            m.status, m.archived_at = 'draft', None
        _check(m, now)
        m.save()
    return m


def archive(m, *, by_email=''):
    """A published (or scheduled) module leaves the scholars who have not started; those who did keep a
    read-only sight of their own work."""
    with transaction.atomic():
        m = _locked_module(m.pk)
        if m.status != 'published':
            raise DevelopmentError('not_published')
        m.status, m.archived_at = 'archived', timezone.now()
        m.save(update_fields=['status', 'archived_at', 'updated_at'])
    return m


def delete_module(m):
    """A draft, or any module nobody has started. One with work in it is archived, never deleted. Its lesson
    files go once the row has gone."""
    from . import development_files as files
    with transaction.atomic():
        m = _locked_module(m.pk)
        if has_started(m):   # her work is a record (a started module can never be a draft: `update_module`)
            raise DevelopmentError('archive_instead')
        paths = [p for p in m.lessons.values_list('file_path', flat=True) if p]
        m.delete()
        files.discard_after_commit(paths)
