"""Development modules — what the STAFF pages and the MENTOR read (student maintenance Sprint 10, 2026-11-02):
the list's rows, a module's Progress (per scholar), its CSV, the review, the scholar file's Growth tab and the
mentor's own-student view. The rules are `development.py`; the fence is `views_admin/development.py` (and
`mentor_desk.py` for a mentor).

PROGRESS, PER SCHOLAR: lessons read x of y (the CURRENT lessons), the task's date, the current mentor, the
review, and "Late" — after the due date, when not done (never shown to her; never touches money).
The four tabs: To review (task sent, not reviewed — a view INSIDE Done), Done, In progress, Not started.
Who is listed: the audience today (the organisation's scholars in maintenance, in the gift) PLUS anybody who
started (a closed file keeps its work on the record).

⚠ WHO READS THIS: super / org_admin / admin of the organisation, and the scholar's CURRENT mentor through the
mentor's own page (`mentor_rows`, an allowlist). NEVER a sponsor, partner, reviewer, QC, finance, a source or
another mentor: no module serving them imports this one. ⚠ READS NEVER WRITE (except `review`).
"""
import csv
import io

from django.db import transaction
from django.utils import timezone

# The Sprint 8 audience rule, ONE home; the Sprint 9 CSV cell guard and audience picker, ONE home each.
from .announcements import audience_apps
from .development import MYT, DevelopmentError, module_status, is_done, modules_for_file, today
from .models import DevelopmentModule, MentorAssignment, ModuleEmail, ModuleProgress
from .survey_results import _cell

COMMENT_MAX = 1000
BUCKETS = ('to_review', 'done', 'in_progress', 'not_started')


def _lesson_out(x):
    return {'id': x.id, 'title': x.title, 'body': x.body, 'video_url': x.video_url,
            'file': {'name': x.file_name, 'type': x.file_type, 'size': x.file_size} if x.file_path else None}


def _counts(m, lesson_ids, rows):
    done = [p for p in rows if is_done(m, lesson_ids, p)]
    return {'started': len(rows), 'done': len(done),
            'to_review': sum(1 for p in done if p.task_sent_at and not p.reviewed_at and m.task_kind != 'none')}


def module_rows(organisation, only_id=None):
    """Every module of the organisation (or just ``only_id``), newest first, with its lessons, audience size and
    how many started / finished / wait for a review."""
    from .mentoring_read import _people, _who
    now = timezone.now()
    qs = (DevelopmentModule.objects.filter(organisation=organisation).select_related('programme')
          .prefetch_related('lessons', 'progress__reads'))
    rows = list(qs.filter(pk=only_id) if only_id is not None else qs)
    people = _people([m.created_by_email for m in rows])
    out = []
    for m in rows:
        status = module_status(m, now)
        lessons = list(m.lessons.all())
        counts = _counts(m, [x.id for x in lessons], list(m.progress.all()))
        out.append({
            'id': m.id, 'title': m.title, 'summary': m.summary, 'status': status,
            'programme': ({'code': m.programme.code, 'name': m.programme.name_en} if m.programme_id else None),
            'publish_at': m.publish_at, 'due_on': m.due_on, 'task_kind': m.task_kind, 'task_prompt': m.task_prompt,
            'lessons': [_lesson_out(x) for x in lessons],
            'audience_count': audience_apps(m.organisation_id, m.programme_id).count(),
            'started_count': counts['started'], 'done_count': counts['done'], 'to_review_count': counts['to_review'],
            'email_on_publish': m.email_on_publish, 'remind': m.remind_before_due,
            'published_emailed_at': m.published_emailed_at, 'reminded_at': m.reminded_at,
            'author': _who(people, m.created_by_email), 'created_at': m.created_at,
            'locked': counts['started'] > 0, 'can_delete': counts['started'] == 0,
            'can_archive': m.status == 'published', 'can_restore': m.status == 'archived',
        })
    return out


def _mentors(app_ids):
    """`{application_id: mentor name}` for the CURRENT mentors (an open assignment) — ONE query."""
    from .mentoring import mentor_name
    rows = (MentorAssignment.objects.filter(application_id__in=list(app_ids), ended_at__isnull=True)
            .select_related('mentor'))
    return {a.application_id: mentor_name(a.mentor) for a in rows}


def _scholar_name(app):
    return (getattr(app.profile, 'name', '') or '').strip() if app.profile_id else ''


def _progress_row(m, lesson_ids, app, p, mentor, day):
    done = is_done(m, lesson_ids, p)
    read = len({r.lesson_id for r in p.reads.all()} & set(lesson_ids)) if p else 0
    bucket = ('not_started' if p is None else 'done' if done else 'in_progress')
    return {'application_id': app.id, 'name': _scholar_name(app), 'mentor': mentor or '',
            'bucket': bucket, 'to_review': bool(done and p.task_sent_at and not p.reviewed_at
                                                and m.task_kind != 'none'),
            'read': read, 'lessons': len(lesson_ids), 'started_at': p.started_at if p else None,
            'task_sent_at': p.task_sent_at if p else None, 'task_text': p.task_text if p else '',
            'task_file': ({'name': p.task_file_name, 'type': p.task_file_type, 'size': p.task_file_size}
                          if p and p.task_file_path else None),
            'reviewed_at': p.reviewed_at if p else None, 'reviewed_by': p.reviewed_by_email if p else '',
            'review_comment': p.review_comment if p else '',
            'late': bool(m.due_on and day > m.due_on and not done)}


def progress(m):
    """A module's Progress page: one row per scholar (the audience today + everybody who started), the four
    tabs' counts. Staff only."""
    lesson_ids = list(m.lessons.values_list('id', flat=True))
    started = {p.application_id: p for p in ModuleProgress.objects.filter(module=m)
               .select_related('application__profile').prefetch_related('reads')}
    audience = list(audience_apps(m.organisation_id, m.programme_id).exclude(id__in=list(started))
                    .select_related('profile'))
    apps = [p.application for p in started.values()] + audience
    mentors = _mentors(a.id for a in apps)
    day = today()
    rows = [_progress_row(m, lesson_ids, a, started.get(a.id), mentors.get(a.id), day) for a in apps]
    rows.sort(key=lambda r: (r['name'].lower(), r['application_id']))
    counts = {b: sum(1 for r in rows if (r['to_review'] if b == 'to_review' else r['bucket'] == b)) for b in BUCKETS}
    # The button reminds the AUDIENCE not done and not yet reminded (a closed file is never emailed; the claim
    # rows mean a second press sends nobody twice) — offered while any is left.
    live = ({a.id for a in audience_apps(m.organisation_id, m.programme_id)}
            - set(ModuleEmail.objects.filter(module=m, kind='reminder').values_list('application_id', flat=True)))
    return {'rows': rows, 'counts': counts,
            'can_remind': (module_status(m) == 'published' and m.due_on is not None
                           and any(r['bucket'] != 'done' and r['application_id'] in live for r in rows))}


def progress_csv(m):
    """One row per scholar (staff only); cells a spreadsheet could run are escaped (`survey_results._cell`)."""
    data = progress(m)['rows']
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([_cell(c) for c in ['Scholar', 'Application', 'Mentor', 'Status', 'Lessons read', 'Lessons',
                                   'Started', 'Task sent', 'Reflection', 'File', 'Reviewed', 'Comment', 'Late']])

    def when(v):
        return timezone.localtime(v, MYT).strftime('%Y-%m-%d %H:%M') if v else ''
    for r in data:
        w.writerow([_cell(v) for v in [
            r['name'], r['application_id'], r['mentor'], r['bucket'].replace('_', ' '), r['read'], r['lessons'],
            when(r['started_at']), when(r['task_sent_at']), r['task_text'],
            (r['task_file'] or {}).get('name', ''), when(r['reviewed_at']), r['review_comment'],
            'Late' if r['late'] else '']])
    return buf.getvalue()


def review(m, application_id, comment, *, by_email=''):
    """"Mark reviewed" with an optional comment (<= 1000) she then sees. Records who and when. Only a task she
    has SENT (409 `nothing_to_review`); a second review replaces the comment (and the who / when)."""
    text = comment.strip().replace('\r\n', '\n') if isinstance(comment, str) else ''
    if len(text) > COMMENT_MAX:
        raise DevelopmentError('comment_too_long')
    with transaction.atomic():
        p = (ModuleProgress.objects.select_for_update()
             .filter(module=m, application_id=application_id).first())
        if p is None:
            raise DevelopmentError('not_found')
        if p.task_sent_at is None:
            raise DevelopmentError('nothing_to_review')
        p.reviewed_at, p.reviewed_by_email, p.review_comment = timezone.now(), (by_email or '')[:254], text
        p.save(update_fields=['reviewed_at', 'reviewed_by_email', 'review_comment', 'updated_at'])
    return p


def task_file_path(m, application_id):
    """The key of one scholar's uploaded task for THIS module, or ''."""
    return (ModuleProgress.objects.filter(module=m, application_id=application_id)
            .values_list('task_file_path', flat=True).first() or '')


def _work_rows(app, *, staff):
    """Each module this scholar can see (``staff``: or started), with their work. No file link: a file opens
    through its own door, signed on the tap (S10 review 1 — a link in a payload goes stale)."""
    now, day = timezone.now(), today()
    mods = list(modules_for_file(app, now).prefetch_related('lessons'))
    started = {p.module_id: p for p in ModuleProgress.objects.filter(application=app)
               .prefetch_related('reads')}
    if staff:
        for m in DevelopmentModule.objects.filter(pk__in=[k for k in started if k not in {x.id for x in mods}]):
            mods.append(m)   # started, but the audience moved: staff still see the work
    out = []
    for m in mods:
        ids = [x.id for x in m.lessons.all()]
        p = started.get(m.id)
        done = is_done(m, ids, p)
        row = {'id': m.id, 'title': m.title, 'status': module_status(m, now), 'due_on': m.due_on,
               'task_kind': m.task_kind, 'lessons': len(ids),
               'read': len({r.lesson_id for r in p.reads.all()} & set(ids)) if p else 0,
               'done': done, 'late': bool(m.due_on and day > m.due_on and not done),
               'task_sent_at': p.task_sent_at if p else None, 'task_text': p.task_text if p else '',
               'task_file': ({'name': p.task_file_name, 'type': p.task_file_type} if p and p.task_file_path
                             else None),
               'reviewed_at': p.reviewed_at if p else None, 'review_comment': p.review_comment if p else ''}
        out.append(row)
    out.sort(key=lambda r: (r['done'], r['due_on'] is None, r['due_on'] or day, -r['id']))
    return out


def scholar_file_payload(app):
    """The scholar file's Growth tab (staff): each module this scholar can see or started, with their work.
    A file opens through the Progress page's file door (`<module>/progress/<app>/file/`), on a tap."""
    return {'modules': _work_rows(app, staff=True)}


def mentor_rows(app):
    """The CURRENT mentor's view of their own student's modules (`mentor_desk.student_payload`): the same
    allowlist as the staff tab, for the modules the STUDENT can see. Never the author, the audience, other
    scholars, the email state, who reviewed or a file link (an upload opens through `file_task_path`'s
    door, `admin/mentor/students/<id>/modules/<module>/file/`, signed on the tap)."""
    return _work_rows(app, staff=False)


def file_task_path(app, module_id):
    """The key of the student's uploaded task for ONE module the student can see (or started), or '' (→ 404).
    The caller has already fenced the file: the mentor's CURRENT assignment (`views_admin/mentor_students.py`)
    or the scholar file's own fence (`views_admin/development.AdminScholarGrowthFileView`, S1)."""
    if modules_for_file(app).filter(pk=module_id).exists():
        return task_file_path(DevelopmentModule(pk=module_id), app.pk)
    return ''
