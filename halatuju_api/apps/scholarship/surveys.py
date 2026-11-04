"""Surveys — the rules (student maintenance Sprint 9, 2026-11-02; owner rulings in docs/decisions.md the same
day). Models: `models/surveys.py`; the staff pages' payloads (results, CSV, the scholar file's tab):
`survey_results.py`; the emails: `survey_emails.py` (the hourly job: `management/commands/send_survey_emails.py`);
the staff fence: `views_admin/surveys.py`; her Surveys tab and her answers: `views_bursary.py`. Sprint 8's
announcements are the pattern (`announcements.py`): the same makers, the same audience rule, the same
claim-before-send email.

WHO MAKES ONE (`may_make`): a super, an organisation admin, an admin — inside their own organisation (the
view's fence). Nobody else. ONE helper, so a future admin permission key narrows it in one place.

THE STATUS IS READ FROM THE DATES (`effective_status`): draft (stored), else scheduled before `opens_at`,
open until `closes_at`, then closed. "Close now" sets `closes_at` to now.

WHO SEES ONE (`surveys_for_file`) — decided when READ, never stored per scholar:
  * it is published and its `opens_at` has passed;
  * the scholar's file belongs to the survey's organisation;
  * the audience is everyone, or the scholar's own gift (the application's `programme` OR its round's —
    the Sprint 8 rule);
  * the file is in maintenance and the survey is still open — OR the file already answered it (a closed
    survey, or a closed file, keeps a read-only sight of its own answers, never anything new).
A sponsor, partner or source never reads any of this; no module serving them imports it.

ANSWERS (`submit`): only while it is open and the file is in maintenance; validated per type (a choice is
one of the options, a rating 1-5, lengths, required ones present). ONE response row per survey x
application (unique); a change REPLACES the answers in one transaction, under a lock on the survey row
(so two submits, or a submit racing a staff edit of the questions, never interleave). A question marked
`mentor_only` is asked only of a scholar with a mentor NOW.

THE QUESTIONS LOCK at the first answer (`has_answers`): no add, remove, reorder or edit, and the audience and
opening time are fixed too. The title, introduction and closing date may still change. A survey with
answers is closed, never deleted.

THE EMAILS (`survey_emails.send_due_emails`, hourly; `survey_emails.remind_now`, the Results page's
button): only when staff asked
for each — "it is open" once it opens, and "you have not answered" 3 days before it closes, to those who
have not answered. Once per scholar per kind (a `SurveyEmail` row CLAIMED before the send — the job, a
second run and the button can never double), only while the organisation's `survey_open` switch is on
(`student_email_catalogue.may_send`), through `student_comms.send_student_email` (metered,
`StudentEmailLog`). Switched off when reached: nobody is emailed and each scholar's row says
`switched_off`, so switching it on later never sends an old one.

⚠ READS NEVER WRITE.
"""
import logging
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Q
from django.utils import dateparse, timezone

from .maintenance_scope import has_file, is_in_maintenance
from .models import Survey, SurveyAnswer, SurveyQuestion, SurveyResponse

logger = logging.getLogger('apps.scholarship.surveys')

TITLE_MAX = 150
INTRO_MAX = 1000
QUESTION_MAX = 300
HINT_MAX = 200
OPTION_MAX = 120
MIN_OPTIONS, MAX_OPTIONS = 2, 12
MAX_QUESTIONS = 30
SHORT_MAX = 300
LONG_MAX = 3000
KINDS = ('one', 'many', 'rating', 'yes_no', 'short', 'long')
CHOICE_KINDS = ('one', 'many')
ACTIONS = ('publish', 'draft')
EMAIL_KEY = 'survey_open'
MYT = ZoneInfo('Asia/Kuala_Lumpur')


class SurveyError(Exception):
    def __init__(self, code, detail=None):
        self.code, self.detail = code, detail
        super().__init__(code)


def may_make(admin):
    """THE gate for every staff survey door. A super, an organisation admin, an admin."""
    # Who may make one (owner, 2026-11-02). Team tables T5c: the v2 key `surveys.edit` (it implies
    # `.view`; this one door both reads and writes). Holders as T1: super, org_admin, the `admin` label.
    from apps.courses import staff_tables
    return staff_tables.opens_door(admin, 'surveys')


# ── Status, audience, who sees one ────────────────────────────────────────────────────────────────

def effective_status(s, now=None):
    now = now or timezone.now()
    if s.status == 'draft':
        return 'draft'
    if now < s.opens_at:
        return 'scheduled'
    if now < s.closes_at:
        return 'open'
    return 'closed'


def has_answers(s):
    return SurveyResponse.objects.filter(survey_id=s.pk).exists()


def has_mentor(app):
    from .models import MentorAssignment
    return MentorAssignment.objects.filter(application_id=app.pk, ended_at__isnull=True).exists()


def surveys_for_file(app, now=None):
    """Every survey ``app`` (her own file, already fenced) may see. Open ones (in maintenance only), and any
    she already answered (read-only once closed). Never a draft or a scheduled one."""
    if app is None or not app.owning_organisation_id or not has_file(app):
        return Survey.objects.none()
    now = now or timezone.now()
    gifts = [g for g in (app.programme_id, getattr(app.cohort, 'programme_id', None) if app.cohort_id else None)
             if g]
    answered = Q(pk__in=SurveyResponse.objects.filter(application_id=app.pk).values('survey_id'))
    qs = (Survey.objects.filter(organisation_id=app.owning_organisation_id, status='published', opens_at__lte=now)
          .filter(Q(programme__isnull=True) | Q(programme_id__in=gifts)))
    if is_in_maintenance(app):
        return qs.filter(Q(closes_at__gt=now) | answered)
    return qs.filter(answered)


def tab_state(app):
    """``(shown, to_answer)`` for her hub: the Surveys tab shows when one is hers (open or answered — the
    bursary "a tab appears when its module has something for her" rule); ``to_answer`` counts the open
    ones she has not answered (the red number)."""
    now = timezone.now()
    rows = list(surveys_for_file(app, now).values('id', 'closes_at'))
    if not rows:
        return False, 0
    if not is_in_maintenance(app):
        return True, 0
    done = set(SurveyResponse.objects.filter(application_id=app.pk, survey_id__in=[r['id'] for r in rows])
               .values_list('survey_id', flat=True))
    return True, sum(1 for r in rows if r['closes_at'] > now and r['id'] not in done)


def _asked_of(questions, mentor, answered_ids):
    """The questions THIS scholar is asked: a `mentor_only` one only with a mentor now (or one she has
    already answered — her answer is never hidden from her)."""
    return [q for q in questions if not q.mentor_only or mentor or q.id in answered_ids]


def _question_out(q):
    return {'id': q.id, 'kind': q.kind, 'text': q.text, 'hint': q.hint, 'required': q.required,
            'options': list(q.options or [])}


def student_surveys(app):
    """Her Surveys tab — an ALLOWLIST: title, introduction, dates, her questions and her own answers. Never
    who wrote it, the audience, a count, anybody else's answer or anything about the email. Open ones
    first (closing soonest), then closed ones, newest first."""
    now = timezone.now()
    surveys = list(surveys_for_file(app, now).prefetch_related('questions'))
    responses = {r.survey_id: r for r in SurveyResponse.objects.filter(
        application_id=app.pk, survey_id__in=[s.id for s in surveys]).prefetch_related('answers')}
    mentor = has_mentor(app) if any(q.mentor_only for s in surveys for q in s.questions.all()) else False
    live = is_in_maintenance(app)
    out = []
    for s in surveys:
        resp = responses.get(s.id)
        answers = {a.question_id: a.value for a in resp.answers.all()} if resp else {}
        status = effective_status(s, now)
        out.append({'id': s.id, 'title': s.title, 'intro': s.intro, 'status': status,
                    'opens_at': s.opens_at, 'closes_at': s.closes_at,
                    'can_answer': live and status == 'open',
                    'answered_at': resp.submitted_at if resp else None,
                    'updated_at': resp.updated_at if resp else None,
                    'questions': [_question_out(q) for q in _asked_of(list(s.questions.all()), mentor, set(answers))],
                    'answers': {str(k): v for k, v in answers.items()}})
    # Open ones first, closing soonest; then the closed ones, newest first.
    out.sort(key=lambda r: (r['status'] != 'open',
                            r['closes_at'] if r['status'] == 'open' else -r['closes_at'].timestamp()))
    return {'organisation': getattr(app.owning_organisation, 'name', '') or '', 'surveys': out}


# ── Her answers ───────────────────────────────────────────────────────────────────────────────────

def _written(raw, limit, qid):
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise SurveyError('bad_answer', qid)
    text = raw.strip().replace('\r\n', '\n').replace('\r', '\n')
    if not text:
        return None
    if len(text) > limit:
        raise SurveyError('answer_too_long', qid)
    return text


def clean_value(q, raw):
    """The stored value of one answer, or None when left empty. Raises `bad_answer` for a value its type
    cannot hold (a choice not among the options, a rating outside 1-5, the wrong shape)."""
    if q.kind == 'one':
        if raw in (None, ''):
            return None
        if not isinstance(raw, str) or raw not in q.options:
            raise SurveyError('bad_answer', q.id)
        return raw
    if q.kind == 'many':
        if raw in (None, []):
            return None
        if (not isinstance(raw, list) or not all(isinstance(v, str) and v in q.options for v in raw)
                or len(set(raw)) != len(raw)):
            raise SurveyError('bad_answer', q.id)
        return [o for o in q.options if o in raw]   # the options' own order
    if q.kind == 'rating':
        if raw is None:
            return None
        if isinstance(raw, bool) or not isinstance(raw, int) or not 1 <= raw <= 5:
            raise SurveyError('bad_answer', q.id)
        return raw
    if q.kind == 'yes_no':
        if raw is None:
            return None
        if not isinstance(raw, bool):
            raise SurveyError('bad_answer', q.id)
        return raw
    return _written(raw, SHORT_MAX if q.kind == 'short' else LONG_MAX, q.id)


def _locked_survey(pk):
    """The survey row under `select_for_update`, or `not_found` — it may have been deleted since the caller
    read it (review 3: `.get()` here turned that race into a 500)."""
    s = Survey.objects.filter(pk=pk).select_for_update().first()
    if s is None:
        raise SurveyError('not_found')
    return s


def submit(app, survey_id, answers):
    """Save (or change) her answers to one survey. Only one she may see, only while it is open and her file
    is in maintenance. Returns the response. Answers are replaced whole."""
    now = timezone.now()
    if isinstance(survey_id, bool) or not isinstance(survey_id, int):
        raise SurveyError('not_found')
    s = surveys_for_file(app, now).filter(pk=survey_id).first()
    if s is None:
        raise SurveyError('not_found')
    if effective_status(s, now) != 'open' or not is_in_maintenance(app):
        raise SurveyError('survey_closed')
    if not isinstance(answers, dict):
        raise SurveyError('bad_answers')
    with transaction.atomic():
        # The lock serialises her two submits AND a staff edit of the questions (`update`).
        s = _locked_survey(s.pk)
        # Review 3: who may see it is asked AGAIN under the lock (the audience or her file may have moved).
        if not surveys_for_file(app, timezone.now()).filter(pk=s.pk).exists():
            raise SurveyError('not_found')
        if s.status != 'published' or effective_status(s, timezone.now()) != 'open':
            raise SurveyError('survey_closed')
        resp = SurveyResponse.objects.filter(survey=s, application=app).first()
        before = set(resp.answers.values_list('question_id', flat=True)) if resp else set()
        questions = list(s.questions.all())
        asked = _asked_of(questions, has_mentor(app) if any(q.mentor_only for q in questions) else False, before)
        if not asked:
            raise SurveyError('no_questions')   # review 1: never an empty response that locks the survey
        by_id = {str(q.id): q for q in asked}
        if any(str(k) not in by_id for k in answers):
            raise SurveyError('bad_question')
        clean = {}
        for q in asked:
            value = clean_value(q, answers.get(str(q.id)))
            if value is None:
                if q.required:
                    raise SurveyError('required', q.id)
                continue
            clean[q.id] = value
        if resp is None:
            resp = SurveyResponse.objects.create(survey=s, application=app)
        else:
            resp.answers.all().delete()
            resp.save(update_fields=['updated_at'])
        SurveyAnswer.objects.bulk_create([SurveyAnswer(response=resp, question_id=k, value=v)
                                          for k, v in clean.items()])
    return resp


# ── Writing one (staff) ───────────────────────────────────────────────────────────────────────────

def _clean_text(value, field, limit, *, required=True, one_line=False):
    text = value.strip() if isinstance(value, str) else ''
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if not text and required:
        raise SurveyError(f'{field}_required')
    if len(text) > limit:
        raise SurveyError(f'{field}_too_long')
    if one_line and '\n' in text:
        raise SurveyError(f'{field}_newline')
    return text


def _programme(organisation, code):
    if code in (None, ''):
        return None
    from .models import Programme
    p = Programme.objects.filter(organisation=organisation, code=str(code)).first()
    if p is None:
        raise SurveyError('bad_audience')
    return p


def _when(raw, field):
    parsed = dateparse.parse_datetime(raw) if isinstance(raw, str) else None
    if parsed is None:
        raise SurveyError(f'bad_{field}')
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, MYT)
    return parsed


def _bool(data, key, default):
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise SurveyError(f'bad_{key}')
    return value


def clean_questions(raw):
    """The question list as staff sent it, checked: up to 30; each a known type, its text (one line, <=
    300), an optional hint (<= 200), required (default yes), mentor_only (default no), and for a choice
    question 2-12 distinct options (<= 120 each)."""
    if not isinstance(raw, list):
        raise SurveyError('bad_questions')
    if len(raw) > MAX_QUESTIONS:
        raise SurveyError('too_many_questions')
    out = []
    for i, q in enumerate(raw):
        if not isinstance(q, dict) or q.get('kind') not in KINDS:
            raise SurveyError('bad_question_kind', i)
        try:
            text = _clean_text(q.get('text'), 'question', QUESTION_MAX, one_line=True)
            hint = _clean_text(q.get('hint') or '', 'hint', HINT_MAX, required=False, one_line=True)
            required, mentor_only = _bool(q, 'required', True), _bool(q, 'mentor_only', False)
        except SurveyError as e:
            raise SurveyError(e.code, i)
        options = []
        if q['kind'] in CHOICE_KINDS:
            raw_opts = q.get('options')
            if not isinstance(raw_opts, list) or not all(isinstance(o, str) for o in raw_opts):
                raise SurveyError('bad_options', i)
            options = [o.strip() for o in raw_opts]
            if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
                raise SurveyError('options_count', i)
            if any(not o or '\n' in o for o in options):
                raise SurveyError('option_required', i)
            if any(len(o) > OPTION_MAX for o in options):
                raise SurveyError('option_too_long', i)
            if len(set(options)) != len(options):
                raise SurveyError('option_duplicate', i)
        out.append({'kind': q['kind'], 'text': text, 'hint': hint, 'required': required,
                    'mentor_only': mentor_only, 'options': options})
    return out


def _same_questions(s, cleaned):
    have = [{'kind': q.kind, 'text': q.text, 'hint': q.hint, 'required': q.required,
             'mentor_only': q.mentor_only, 'options': list(q.options or [])} for q in s.questions.all()]
    return have == cleaned


def _replace_questions(s, cleaned):
    s.questions.all().delete()
    SurveyQuestion.objects.bulk_create([SurveyQuestion(survey=s, position=i + 1, **q) for i, q in enumerate(cleaned)])


def _check_dates(s, now, publishing):
    if publishing and s.closes_at <= now:
        raise SurveyError('closes_at_past')
    if s.closes_at <= s.opens_at:
        raise SurveyError('closes_before_opens')


def _publish(s, now):
    if not s.questions.exists():
        raise SurveyError('no_questions')
    s.status = 'published'
    if s.opens_at < now:
        s.opens_at = now   # "opens now": an earlier time would read as if it had been open all along
    _check_dates(s, now, True)


def create(organisation, data, *, by_email=''):
    """A new draft or published survey from the form's fields (and its questions)."""
    now = timezone.now()
    action = data.get('action')
    if action not in ACTIONS:
        raise SurveyError('bad_action')
    questions = clean_questions(data.get('questions', []))
    s = Survey(organisation=organisation, created_by_email=(by_email or '')[:254],
               title=_clean_text(data.get('title'), 'title', TITLE_MAX, one_line=True),
               intro=_clean_text(data.get('intro') or '', 'intro', INTRO_MAX, required=False),
               programme=_programme(organisation, data.get('programme')),
               opens_at=_when(data['opens_at'], 'opens_at') if data.get('opens_at') else now,
               closes_at=_when(data.get('closes_at'), 'closes_at'),
               email_on_open=_bool(data, 'email_on_open', False),
               remind_before_close=_bool(data, 'remind', False))
    _check_dates(s, now, action == 'publish')
    with transaction.atomic():
        s.save()
        _replace_questions(s, questions)
        if action == 'publish':
            _publish(s, now)
            s.save()
    return s


def update(s, data, *, by_email=''):
    """Edit. Before the first answer anything may change (and a draft may be published, or a published
    one taken back to draft). From the first answer, only the title, the introduction, the closing date
    and the two email choices; the questions, the audience and the opening time are locked."""
    now = timezone.now()
    with transaction.atomic():
        s = _locked_survey(s.pk)
        locked = has_answers(s)
        if 'questions' in data:
            cleaned = clean_questions(data['questions'])
            if not _same_questions(s, cleaned):
                if locked:
                    raise SurveyError('questions_locked')
                _replace_questions(s, cleaned)
        if 'title' in data:
            s.title = _clean_text(data['title'], 'title', TITLE_MAX, one_line=True)
        if 'intro' in data:
            s.intro = _clean_text(data['intro'] or '', 'intro', INTRO_MAX, required=False)
        if 'email_on_open' in data:
            s.email_on_open = _bool(data, 'email_on_open', s.email_on_open)
        if 'remind' in data:
            s.remind_before_close = _bool(data, 'remind', s.remind_before_close)
        if 'programme' in data:
            programme = _programme(s.organisation, data.get('programme'))
            if programme != s.programme:
                if locked:
                    raise SurveyError('answered_locked')
                s.programme = programme
        if data.get('opens_at'):
            opens = _when(data['opens_at'], 'opens_at')
            if opens != s.opens_at:
                if locked:
                    raise SurveyError('answered_locked')
                s.opens_at = opens
        closes_changed = False
        if data.get('closes_at'):
            closes = _when(data['closes_at'], 'closes_at')
            closes_changed = closes != s.closes_at
            s.closes_at = closes
        action = data.get('action')
        if action is not None and action not in ACTIONS:
            raise SurveyError('bad_action')
        if action == 'publish' and s.status == 'draft':
            _publish(s, now)
        elif action == 'draft' and s.status == 'published':
            if locked:
                raise SurveyError('answered_locked')
            s.status = 'draft'
        # Review 4: "opens now" on a draft or a scheduled one — the opening time becomes now, not the time
        # an earlier save left (which would publish it as scheduled).
        if data.get('opens_now') is True and s.opens_at > now:
            if locked:
                raise SurveyError('answered_locked')
            s.opens_at = now
        # Review 1: a published survey always has a question (an empty one could take an empty response).
        if s.status == 'published' and not s.questions.exists():
            raise SurveyError('no_questions')
        _check_dates(s, now, s.status == 'published' and (closes_changed or action == 'publish'))
        s.save()
    return s


def close_now(s, *, by_email=''):
    """"Close now": an open survey's closing time becomes now. Answers stop; what she sent stays."""
    now = timezone.now()
    with transaction.atomic():
        s = _locked_survey(s.pk)
        if effective_status(s, now) != 'open':
            raise SurveyError('not_open')
        s.closes_at = now
        s.save(update_fields=['closes_at', 'updated_at'])
    return s


def delete(s):
    """A draft, or any survey nobody has answered. One with answers is closed, never deleted."""
    with transaction.atomic():
        s = _locked_survey(s.pk)
        if has_answers(s):
            raise SurveyError('close_instead')
        s.delete()
