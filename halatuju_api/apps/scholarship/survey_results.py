"""Surveys — what the STAFF pages read (student maintenance Sprint 9, 2026-11-02): the list's rows, the "For"
picker, a survey's Results (summary, each scholar, not answered), its CSV, and the scholar file's Surveys tab.
The rules are `surveys.py`; the fence is `views_admin/surveys.py`.

⚠ STAFF ONLY. These carry the scholar's NAME beside each answer (owner ruling, 2026-11-02): no module serving a
sponsor, a partner or a source imports this one.
⚠ READS NEVER WRITE.
"""
import csv
import io

from django.db.models import Count
from django.utils import timezone

from apps.courses.csv_safe import csv_cell
# The Sprint 8 audience rule, ONE home: the organisation's files in maintenance, in the gift.
from .announcements import audience_apps
from .models import Survey, SurveyEmail, SurveyResponse
from .surveys import CHOICE_KINDS, MYT, _question_out, effective_status, surveys_for_file


def staff_rows(organisation, only_id=None):
    """Every survey of the organisation (or just ``only_id``), newest first, with its questions, audience
    size and how many answered."""
    from .mentoring_read import _people, _who
    now = timezone.now()
    qs = (Survey.objects.filter(organisation=organisation).select_related('programme')
          .prefetch_related('questions').annotate(answered=Count('responses', distinct=True)))
    rows = list(qs.filter(pk=only_id) if only_id is not None else qs)
    people = _people([s.created_by_email for s in rows])
    out = []
    for s in rows:
        status = effective_status(s, now)
        out.append({
            'id': s.id, 'title': s.title, 'intro': s.intro, 'status': status,
            'programme': ({'code': s.programme.code, 'name': s.programme.name_en} if s.programme_id else None),
            'opens_at': s.opens_at, 'closes_at': s.closes_at,
            'questions': [{**_question_out(q), 'mentor_only': q.mentor_only} for q in s.questions.all()],
            'audience_count': audience_apps(s.organisation_id, s.programme_id).count(),
            'answered_count': s.answered,
            'email_on_open': s.email_on_open, 'remind': s.remind_before_close,
            'opened_emailed_at': s.opened_emailed_at, 'reminded_at': s.reminded_at,
            'author': _who(people, s.created_by_email), 'created_at': s.created_at,
            'locked': s.answered > 0, 'can_delete': s.answered == 0, 'can_close': status == 'open',
        })
    return out


def audiences(organisation):
    """The "For" picker: everyone, then each gift — each with how many scholars it reaches today."""
    from .models import Programme
    out = [{'programme': None, 'name': '', 'count': audience_apps(organisation.id, None).count()}]
    for p in Programme.objects.filter(organisation=organisation).order_by('name_en', 'id'):
        out.append({'programme': p.code, 'name': p.name_en, 'count': audience_apps(organisation.id, p.id).count()})
    return out


def _scholar_name(app):
    return (getattr(app.profile, 'name', '') or '').strip() if app.profile_id else ''


def results(s):
    """Staff's Results page: per question a summary (counts and who for a choice, the average for a
    rating, the written answers with names), each scholar's response, and who has not answered."""
    now = timezone.now()
    questions = list(s.questions.all())
    responses = list(SurveyResponse.objects.filter(survey=s).select_related('application__profile')
                     .prefetch_related('answers').order_by('submitted_at', 'id'))
    by_q = {q.id: [] for q in questions}
    each = []
    for r in responses:
        who = {'application_id': r.application_id, 'name': _scholar_name(r.application)}
        values = {}
        for a in r.answers.all():
            values[str(a.question_id)] = a.value
            if a.question_id in by_q:
                by_q[a.question_id].append((who, a.value))
        each.append({**who, 'submitted_at': r.submitted_at, 'updated_at': r.updated_at, 'answers': values})
    summary = []
    for q in questions:
        got = by_q[q.id]
        item = {'question_id': q.id, 'answered': len(got)}
        if q.kind in CHOICE_KINDS or q.kind == 'yes_no':
            options = [True, False] if q.kind == 'yes_no' else list(q.options)
            item['options'] = [{'option': o, 'count': 0, 'who': []} for o in options]
            slot = {o: item['options'][i] for i, o in enumerate(options)}
            for who, value in got:
                for v in (value if isinstance(value, list) else [value]):
                    if v in slot and (q.kind == 'yes_no') == isinstance(v, bool):
                        slot[v]['count'] += 1
                        slot[v]['who'].append(who)
        elif q.kind == 'rating':
            values = [v for _w, v in got if isinstance(v, int)]
            item['average'] = round(sum(values) / len(values), 1) if values else None
            item['options'] = [{'option': n, 'count': 0, 'who': []} for n in range(1, 6)]
            for who, v in got:
                if isinstance(v, int) and 1 <= v <= 5:
                    item['options'][v - 1]['count'] += 1
                    item['options'][v - 1]['who'].append(who)
        else:
            item['written'] = [{**who, 'text': v} for who, v in got]
        summary.append(item)
    answered_ids = {r.application_id for r in responses}
    status = effective_status(s, now)
    # "Reminded" = the reminder was dealt with for this scholar (sent, or no address / switched off): the
    # button would send them nothing, so it is not offered for them.
    reminded = set(SurveyEmail.objects.filter(survey=s, kind='reminder').values_list('application_id', flat=True))
    pending = [] if status == 'draft' else [
        {'application_id': a.id, 'name': _scholar_name(a), 'reminded': a.id in reminded}
        for a in audience_apps(s.organisation_id, s.programme_id).exclude(id__in=answered_ids)
        .select_related('profile').order_by('profile__name', 'id')]
    return {'summary': summary, 'responses': each, 'not_answered': pending,
            'can_remind': status == 'open' and any(not p['reminded'] for p in pending)}


# A CSV cell that a spreadsheet cannot run; its one home is apps.courses.csv_safe (TD-515, A1.9).
_cell = csv_cell


def _csv_value(q, value):
    if value is None:
        return ''
    if q.kind == 'many':
        return '; '.join(value) if isinstance(value, list) else str(value)
    if q.kind == 'yes_no':
        return 'Yes' if value is True else 'No' if value is False else ''
    return value


def results_csv(s):
    """One row per response, one column per question (staff only)."""
    questions = list(s.questions.all())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([_cell(c) for c in ['Scholar', 'Application', 'Sent', 'Last changed']
                + [f'{q.position}. {q.text}' for q in questions]])
    for r in (SurveyResponse.objects.filter(survey=s).select_related('application__profile')
              .prefetch_related('answers').order_by('submitted_at', 'id')):
        got = {a.question_id: a.value for a in r.answers.all()}
        w.writerow([_cell(v) for v in [
            _scholar_name(r.application), r.application_id,
            timezone.localtime(r.submitted_at, MYT).strftime('%Y-%m-%d %H:%M'),
            timezone.localtime(r.updated_at, MYT).strftime('%Y-%m-%d %H:%M')]
            + [_csv_value(q, got.get(q.id)) for q in questions]])
    return buf.getvalue()


def scholar_file_payload(app):
    """The scholar file's Surveys tab (staff): each survey this scholar answered, with the answers against
    the questions, and the open ones still waiting for them."""
    now = timezone.now()
    out = []
    for r in (SurveyResponse.objects.filter(application_id=app.pk).select_related('survey')
              .prefetch_related('answers', 'survey__questions').order_by('-submitted_at', '-id')):
        got = {a.question_id: a.value for a in r.answers.all()}
        out.append({'id': r.survey_id, 'title': r.survey.title, 'status': effective_status(r.survey, now),
                    'submitted_at': r.submitted_at, 'updated_at': r.updated_at,
                    'answers': [{'question_id': q.id, 'text': q.text, 'kind': q.kind, 'value': got.get(q.id)}
                                for q in r.survey.questions.all() if q.id in got]})
    answered = {x['id'] for x in out}
    still_open = surveys_for_file(app, now).filter(closes_at__gt=now).exclude(id__in=answered)
    waiting = [{'id': s.id, 'title': s.title, 'closes_at': s.closes_at} for s in still_open.order_by('closes_at')]
    return {'answered': out, 'waiting': waiting}
