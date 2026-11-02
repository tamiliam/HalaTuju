"""``GET /api/v1/scholarship/bursary/summary/`` — the student's own "My Bursary" hub (maintenance S3).

The signed-in student's OWN file: the newest of her applications that has one
(``maintenance_scope.has_file_q``). 404 when she has none — the same answer whether she never
applied, was never funded, or her pre-award case was closed (TD-352).

⚠ WHAT IT NEVER SERVES: no actor email, no activity row, no officer note, no sub-state word. The only
maintenance signal is ``support_paused`` (``maintenance.is_on_hold``) — probation and ready-to-close
are staff flags (S1 review L5). No standing is judged (Sprint 4). Money is HER money: what the
award is, what has reached her wallet, what remains (``payments._remaining`` — the funding summary's
own rule) and the last payment.

A separate module, not ``views.py``: that file is on the oversize ledger and may not grow.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated

from . import card_display
from .in_programme import can_record_results
from .maintenance import is_on_hold
from .maintenance_scope import has_file_q, is_in_maintenance
from .models import Disbursement, ScholarshipApplication, SemesterResult
from .results_expectations import late, next_due
from .scholars import _two


def summary_payload(app):
    """The hub's payload for ONE application the caller owns and that has a file."""
    from .payments import _remaining, paid_to_date
    last = (Disbursement.objects.filter(application=app, status__in=Disbursement.PAID)
            .order_by('-released_at', '-id').values('amount', 'released_at').first())
    latest = (SemesterResult.objects.filter(application=app).order_by('-created_at', '-id')
              .values('semester', 'cgpa', 'created_at', 'review_status').first())
    programme = getattr(app, 'programme', None)
    return {
        'application_id': app.id,
        'name': getattr(app.profile, 'name', '') or '',
        'gift': programme.name_en if programme is not None else '',
        # Her gift in each language, falling back to English (S3 review L3); the page picks hers.
        'gift_names': ({lang: (getattr(programme, f'name_{lang}', '') or programme.name_en)
                        for lang in ('en', 'ms', 'ta')} if programme is not None else {}),
        'course': card_display.resolve_course(app),
        'institution': card_display.resolve_institution(app),
        'status': app.status,
        'closure_reason': app.closure_reason,
        'in_maintenance': is_in_maintenance(app),
        'can_record_results': can_record_results(app),
        'support_paused': is_on_hold(app),
        'funds': {
            'award_amount': _two(app.award_amount),
            'received': _two(paid_to_date(app)),
            'remaining': _two(_remaining(app)),
            'last_payment': ({'amount': _two(last['amount']), 'at': last['released_at']}
                             if last else None),
        },
        # Her OWN latest result whatever its review — she sees it is awaiting review or queried.
        'latest_result': ({'semester': latest['semester'], 'cgpa': _two(latest['cgpa']),
                           'at': latest['created_at'], 'review_status': latest['review_status']}
                          if latest else None),
        # S4b: when her next result is due (her earliest open term; a past date means it is late).
        'next_result_due': next_due(app),
        # The SERVER says whether she is late (due date + the organisation's grace, nothing she sent
        # this term waiting for review) — the page never works it out (review L10).
        'next_result_overdue': late(app),
        # S6b: her letters — whether the tab shows, and how many still wait for her acknowledgement.
        'has_letters': app.letters.exists(),
        'letters_to_acknowledge': _letters_to_acknowledge(app),
        # S7b: whether the Mentoring tab shows (`mentoring_read.tab_shown`); its body is read lazily.
        'mentoring_tab': _mentoring_tab(app),
        # S8: whether the News tab shows (at least one announcement is hers) and how many she has not seen.
        **_news(app),
        # S9: whether the Surveys tab shows (an open one for her, or one she answered) and how many open
        # ones she has not answered yet (the red number).
        **_surveys(app),
        # S10: whether the Growth tab shows (a live module for her, or one she started) and how many live ones
        # she has not finished (the red number).
        **_growth(app),
    }


def _growth(app):
    from .development import growth_tab_state
    shown, to_do = growth_tab_state(app)
    return {'growth_tab': shown, 'growth_to_do': to_do}


def _surveys(app):
    from .surveys import tab_state
    shown, to_answer = tab_state(app)
    return {'surveys_tab': shown, 'surveys_to_answer': to_answer}


def _news(app):
    from .announcements import tab_state
    shown, unread = tab_state(app)
    return {'news_tab': shown, 'news_unread': unread}


def _mentoring_tab(app):
    from .mentoring_read import tab_shown
    return tab_shown(app)


def _letters_to_acknowledge(app):
    from .letters import to_acknowledge
    return to_acknowledge(app)


def _own_file(request):
    """Her newest application WITH a file, or None — the one door all three hub reads use."""
    return (ScholarshipApplication.objects.select_related('profile', 'programme')
            .filter(has_file_q(), profile_id=request.user_id).order_by('-id').first())


def _no_file():
    return Response({'error': 'Not found', 'code': 'no_file'}, status=status.HTTP_404_NOT_FOUND)


class BursaryFundsView(APIView):
    """GET scholarship/bursary/funds/ — her Funds tab (S5b): award, received, remaining, her last 3
    payments and her spending as totals plus categories (`scholar_money.student_funds`; owner ruling
    (a), 2026-10-30 — no merchant, no transaction, no transaction date). Her OWN file only; a closed
    file reads the same."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from .scholar_money import student_funds
        return Response(student_funds(app))


class BursaryContractView(APIView):
    """GET scholarship/bursary/contract/ — her Contract tab (S5b): the platform-signed agreement
    (countersigned; the witness is optional), the parties (no IC number), or `{exists: false}`.
    `?link=1` mints a 300-second PDF link — only when she opens it. Not gated on the signing flag.
    Her OWN file only."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from .scholar_money import student_contract
        return Response(student_contract(app, with_link=request.query_params.get('link') == '1'))


class BursarySummaryView(APIView):
    """GET — the signed-in student's own hub. Never another student's data."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _own_file(request)
        if app is None:
            return _no_file()
        return Response(summary_payload(app))


# ── Her letters (student maintenance S6b, 2026-10-31) ──────────────────────────────────────────
# HER OWN file only (`_own_file`); a letter of any other application is 404. She reads the letter as
# it was issued (English or Malay), downloads its PDF (a 300-second link on her tap), and
# acknowledges it — which "does not mean you agree". A withdrawn letter reads but cannot be
# acknowledged. Never who issued it, the address it went to, or any staff note.

def _her_letter(app, lid):
    from .models import Letter
    return Letter.objects.filter(pk=lid, application=app).select_related('application').first()


class BursaryLettersView(APIView):
    """GET scholarship/bursary/letters/ — her letters, newest first."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from . import letters
        return Response({'organisation': getattr(app.owning_organisation, 'name', '') or '',
                         'letters': [letters.student_dict(r) for r in letters.for_file(app)]})


class BursaryLetterActionView(APIView):
    """POST scholarship/bursary/letters/<lid>/acknowledge/ or .../read/ — her own letter only."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request, lid, action):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from . import letters
        letter = _her_letter(app, lid)
        if letter is None or action not in ('acknowledge', 'read'):
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if action == 'read':
            letters.mark_read(letter)
            letter.refresh_from_db()
            return Response(letters.student_dict(letter))
        try:
            letter = letters.acknowledge(letter)
        except letters.LetterError as e:
            return Response({'error': e.code, 'code': e.code}, status=status.HTTP_409_CONFLICT)
        return Response(letters.student_dict(letter))


class BursaryLetterPdfView(APIView):
    """GET scholarship/bursary/letters/<lid>/pdf/ — a 300-second link to HER letter's PDF."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request, lid):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from . import letters
        letter = _her_letter(app, lid)
        url = letters.pdf_url(letter) if letter is not None else None
        if not url:
            return Response({'error': 'no_pdf', 'code': 'no_pdf'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'url': url, 'expires_in': 300})


# ── The student's mentor (student maintenance S7b, 2026-11-01) ────────────────────────────────────────────
class BursaryMentoringView(APIView):
    """GET scholarship/bursary/mentoring/ — the student's Mentoring tab, read when opened: the CURRENT
    mentor (name, area, languages, About, email, the phone only when the mentor shares it, since) and
    the meetings with them as date + how (`mentoring_read.student_payload`, an allowlist). Never a note, a
    next step, a reason, a past mentor or a photo. The student's OWN file only; a closed file reads the same."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from .mentoring_read import student_payload
        return Response(student_payload(app))


# ── Her News (student maintenance S8, 2026-11-01) ─────────────────────────────────────────────────────
# Her OWN file only. What she sees is `announcements.news_payload` (an allowlist): never who wrote
# it, the audience or the email. A closed file reads what went out before it closed.
class BursaryNewsView(APIView):
    """GET scholarship/bursary/news/ — her announcements, pinned first, then newest; each says `new`
    until her tab has shown it. Reading never writes: the tab POSTs `read/` with the ids it showed."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from .announcements import news_payload
        return Response(news_payload(app))


class BursaryNewsReadView(APIView):
    """POST scholarship/bursary/news/read/ `{ids: [..]}` — her tab showed these. Only the ones she may
    see are recorded (an id she cannot see is ignored, never an error that confirms it exists)."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from .announcements import AnnouncementError, mark_read, tab_state
        ids = request.data.get('ids') if isinstance(request.data, dict) else None
        try:
            marked = mark_read(app, ids)
        except AnnouncementError as e:
            return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'marked': marked, 'unread': tab_state(app)[1]})


# ── Her Surveys (student maintenance S9, 2026-11-02) ──────────────────────────────────────────────────
# Her OWN file only. What she sees is `surveys.student_surveys` (an allowlist): her questions and her own
# answers — never who wrote it, the audience, a count or anybody else's answer.
class BursarySurveysView(APIView):
    """GET scholarship/bursary/surveys/ — the open surveys for her (answered or not) and the closed ones she
    answered (read-only), each with her questions and her answers."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from .surveys import student_surveys
        return Response(student_surveys(app))


class BursarySurveyAnswersView(APIView):
    """POST scholarship/bursary/surveys/<pk>/answers/ `{answers: {question_id: value}}` — send, or change, her
    answers while the survey is open. A survey she may not see is 404 (never a refusal that confirms it
    exists); a closed one is 409 `survey_closed`; a bad value is 400 with the question's id in `detail`."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request, pk):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from .surveys import SurveyError, student_surveys, submit, tab_state
        answers = request.data.get('answers') if isinstance(request.data, dict) else None
        try:
            submit(app, pk, answers)
        except SurveyError as e:
            if e.code == 'not_found':
                return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
            code = (status.HTTP_409_CONFLICT if e.code in ('survey_closed', 'no_questions')
                    else status.HTTP_400_BAD_REQUEST)
            body = {'error': e.code, 'code': e.code}
            if e.detail is not None:
                body['detail'] = e.detail
            return Response(body, status=code)
        mine = next((x for x in student_surveys(app)['surveys'] if x['id'] == pk), None)
        return Response({'survey': mine, 'to_answer': tab_state(app)[1]})


# ── Her Growth tab: development modules (student maintenance S10, 2026-11-02) ─────────────────────────
# Her OWN file only (`_own_file`). What she sees is `development.student_modules` / `student_module` (an
# allowlist): never who wrote it, the audience, a count or anybody else's work. A module she may not see — a
# draft, a scheduled one, another organisation's, another gift's, an archived one she never started, or a
# lesson of another module — is 404, never a refusal that confirms it exists. Files: a 300-second signed link
# to a lesson file of a module she may see, or to HER OWN upload — nothing else.
def _growth_refusal(e):
    if e.code == 'not_found':
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    code = (status.HTTP_409_CONFLICT if e.code in ('module_closed', 'lessons_first', 'reviewed', 'no_task')
            else status.HTTP_503_SERVICE_UNAVAILABLE if e.code == 'storage_unavailable'
            else status.HTTP_400_BAD_REQUEST)
    return Response({'error': e.code, 'code': e.code}, status=code)


def _her_module(app, pk):
    from .development import growth_tab_state, student_module
    return {'module': student_module(app, pk), 'to_do': growth_tab_state(app)[1]}


class BursaryGrowthView(APIView):
    """GET scholarship/bursary/growth/ — her modules: the live ones and the ones she started (read-only once
    archived or her file closed). GET .../growth/<pk>/ — one module, its lessons and her task."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request, pk=None):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from .development import student_module, student_modules
        if pk is None:
            return Response(student_modules(app))
        body = student_module(app, pk)
        if body is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(body)


class BursaryGrowthLessonView(APIView):
    """POST scholarship/bursary/growth/<pk>/lessons/<lid>/read/ — "I have read this" (idempotent; 409
    `module_closed`). GET .../lessons/<lid>/file/ — a 300-second link to the lesson's file."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request, pk, lid, action):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from . import development, development_files
        m = development.visible_module(app, pk) if action == 'file' else None
        lesson = m.lessons.filter(pk=lid).first() if m is not None else None
        url = development_files.signed_url(lesson.file_path) if lesson is not None else None
        if not url:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'url': url, 'expires_in': development_files.SIGNED_FOR})

    def post(self, request, pk, lid, action):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from .development import DevelopmentError, mark_lesson_read
        if action != 'read':
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            mark_lesson_read(app, pk, lid)
        except DevelopmentError as e:
            return _growth_refusal(e)
        return Response(_her_module(app, pk))


class BursaryGrowthTaskView(APIView):
    """POST scholarship/bursary/growth/<pk>/task/ — send or change her task: `{text}` (a reflection, <= 5,000)
    or `{storage_path, original_filename}` (a PDF / JPEG / PNG up to 10 MB she PUT to the signed URL; checked
    by its bytes). 409 `lessons_first` / `reviewed` / `module_closed` / `no_task`. POST .../task/sign/ `{size}`
    → `{upload_url, storage_path}` under HER own path. GET .../task/file/ → a 300-second link to HER file."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request, pk, step=None):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from . import development, development_files
        from .models import ModuleProgress
        m = development.visible_module(app, pk) if step == 'file' else None
        path = (ModuleProgress.objects.filter(module=m, application=app).values_list('task_file_path', flat=True)
                .first() if m is not None else '')
        url = development_files.signed_url(path) if path else None
        if not url:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'url': url, 'expires_in': development_files.SIGNED_FOR})

    def post(self, request, pk, step=None):
        app = _own_file(request)
        if app is None:
            return _no_file()
        from . import development, development_files
        data = request.data if isinstance(request.data, dict) else {}
        try:
            if step == 'sign':
                m = development.visible_module(app, pk)
                if m is None:
                    raise development.DevelopmentError('not_found')
                if not development.can_act(m, app):
                    raise development.DevelopmentError('module_closed')
                if m.task_kind != 'upload':
                    raise development.DevelopmentError('no_task')
                return Response(development_files.task_upload_url(app, m, data.get('size')))
            if step is not None:
                raise development.DevelopmentError('not_found')
            development.submit_task(app, pk, data)
        except development.DevelopmentError as e:
            return _growth_refusal(e)
        return Response(_her_module(app, pk))
