"""Check 3 — the interview agenda, the findings a reviewer records, and the session itself.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.

⚠ TWO SPANS of the old root (lines 138-143 and 735-952). They were not adjacent there, but
they are one domain, and each span is byte-identical to the lines it came from.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from ..anomaly_engine import detect_anomalies
from ..models import InterviewSession
from ..serializers_admin import AdminApplicationDetailSerializer, InterviewSessionSerializer
from ..services import submit_interview

from .base import _AdminBase


# '' = an in-progress finding: the reviewer typed a one-line "what you found" but
# hasn't classified it (resolved/still_unclear/new_concern). The cockpit produces this
# for any gap whose verdict button wasn't clicked — rejecting it 400'd the whole
# Save-draft and lost the reviewer's notes. A draft finding may carry just a rationale.
_VALID_VERDICTS = {'', 'resolved', 'still_unclear', 'new_concern', 'deleted'}
_RATIONALE_MAX = 140


# ── Phase C: interview capture + request-more-documentation ──────────────────

def _interview_agenda(application):
    """The anomaly codes that form the interview agenda (same flags the admin
    'Pre-interview flags' card shows). Flat list — kept stable for the AdminInterviewView
    scaffold + its FE. V3 (#9) adds the richer folded agenda in ``interview_agenda_full``."""
    return [a['code'] for a in detect_anomalies(application)]


# V3 (#9): the verdict items that explicitly say "confirm at interview" — folded onto the agenda
# by ITEM CODE (not fact status) so they don't evaporate at Check 3. NB since V5, `income_above_
# b40_line` rides on a RED ('gap') income fact, not an amber one — the folding is code-keyed, so
# it's still picked up; the historical name is kept. Over-the-line income is phrased for the
# INTERVIEWER only (never a student message — owner decision 4).
_NEEDS_INTERVIEW_AMBERS = ('income_unverified_needs_interview', 'income_above_b40_line',
                           'academic_grade_uncertain', 'ic_service_down')


def interview_agenda_full(application):
    """The interviewer's talking-point agenda for Check 3. Returns ``[{code, kind, params}]`` where
    kind is one of:
      - ``anomaly``        — the deterministic pre-interview flags (as before);
      - ``needs_interview``— the verdict ambers that say "confirm at interview"
                             (``_NEEDS_INTERVIEW_AMBERS``); over-the-line income is interviewer-only;
      - ``motivation``     — a STANDING 'Motivation & grit' section, always present, ``seeded``
                             rich when the statement of intent / aspirations is thin
                             (``motivation_missing``). Motivation stays a human judgement
                             (owner decision 3) — no student query, structured for Check 3.
    Deduped across kinds by (kind, code). The FE resolves copy per (kind, code).

    NOTE (owner, 2026-07-06): open Check-2 queries / doc-requests are NO LONGER echoed here as
    "carried-over" items. They stay in Check-2 Outstanding (a pending upload isn't an interview
    talking point, and the generic echo was noise the reviewer deleted every time). V3 #9's "nothing
    evaporates" is served by Check-2 remaining open — not by duplicating it onto the agenda."""
    from ..submission_review import completeness_gaps as _submission_gaps
    from ..verdict_engine import build_verdict
    agenda = [{'code': a['code'], 'kind': 'anomaly', 'params': a.get('params', {})}
              for a in detect_anomalies(application)]
    seen = {(e['kind'], e['code']) for e in agenda}

    def _add(kind, code, params):
        if (kind, code) not in seen:
            agenda.append({'code': code, 'kind': kind, 'params': params or {}})
            seen.add((kind, code))

    # the "needs interview" verdict ambers.
    for fact in build_verdict(application):
        for item in fact.get('unresolved', []):
            if item['code'] in _NEEDS_INTERVIEW_AMBERS:
                _add('needs_interview', item['code'], item.get('params', {}))
    # (c) the standing Motivation & grit section (seeded rich when the statement of intent is thin).
    thin = any(g['code'] == 'motivation_missing' for g in _submission_gaps(application))
    _add('motivation', 'motivation_grit', {'seeded': thin})
    return agenda


def _is_authoring(old_findings, new_findings, old_note, new_note):
    """Did this save ADD INTERVIEW CONTENT, as opposed to housekeeping? (TD-216, owner 2026-08-13)

    This decides who the interview is credited to. Before it existed, the credit went to whoever
    caused the session row to exist — and clearing an AI agenda question causes that, because a
    delete is a decision and must survive a reload, so it writes the whole session. Three students
    ended up with an interview attributed to somebody who had only tidied their agenda; a reviewer
    typing findings into one of those afterwards would have had the work recorded under that other
    name, silently.

    ⚠ **CONTENT IS THE PER-ITEM FINDINGS *AND* THE MAIN NOTE, DELIBERATELY.** The owner's rule was
    "whoever writes or edits the findings", and the screen has one free-text box that carries both
    the findings and the conclusion (its own placeholder says so). Keying on the per-item lines
    alone would leave **31 of 83** submitted interviews with no interviewer at all — the reviewers
    who write everything in the main box. Owner chose this reading on 2026-08-13 knowing the
    trade: somebody who rewrites only the conclusion does take the credit, because nothing in the
    data can distinguish that from rewriting the findings. Splitting the box is the fix for that
    and was deferred.

    ⚠ **A DELETION IS NEVER AUTHORSHIP**, however much of the findings dict it changes. That is the
    whole origin of the bug and is checked explicitly — a plain "did the findings change?" test
    would still stamp the person who cleared a question.
    """
    if (new_note or '').strip() != (old_note or '').strip():
        return True
    old = old_findings if isinstance(old_findings, dict) else {}
    for code, value in (new_findings or {}).items():
        if not isinstance(value, dict):
            continue
        if value.get('verdict') == 'deleted':
            continue
        if old.get(code) != value:
            return True
    return False


def _validate_findings(findings):
    """Validate a findings dict: each value must have a valid verdict + a rationale
    within length. Returns an error string or None."""
    if not isinstance(findings, dict):
        return 'findings must be an object'
    for code, val in findings.items():
        if not isinstance(val, dict):
            return f'finding {code} must be an object'
        if val.get('verdict') not in _VALID_VERDICTS:
            return f'finding {code} has an invalid verdict'
        if len(val.get('rationale', '') or '') > _RATIONALE_MAX:
            return f'finding {code} rationale exceeds {_RATIONALE_MAX} chars'
    return None


class AdminInterviewView(_AdminBase):
    """
    GET  .../<pk>/interview/ — the latest interview session, or an empty scaffold
         (status null) carrying the agenda codes from the anomaly engine.
    POST .../<pk>/interview/ — create/update the DRAFT session (findings/rubric/
         note). Saving a draft does NOT change the application status — 'interviewing'
         is reached only by proposing times (the forward trigger) or, for an offline
         interview, by SUBMITTING the session; both require an assigned reviewer.
    Reviewer/super only.
    """
    def get(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
        session = app.interview_sessions.first()  # ordering = -created_at
        data = InterviewSessionSerializer(session).data if session else None
        return Response({'session': data, 'agenda': _interview_agenda(app)})

    def post(self, request, pk):
        app, admin, err = self._require_open_case(request, pk)
        if err:
            return err
        findings = request.data.get('findings', {}) or {}
        err = _validate_findings(findings)
        if err:
            return Response({'error': err, 'code': 'bad_findings'},
                            status=status.HTTP_400_BAD_REQUEST)
        session = app.interview_sessions.filter(status='draft').first()
        if session is None and app.decision_reopened_at is not None:
            # Decision reopened → edit the SUBMITTED session IN PLACE (reopen it as a draft)
            # instead of spawning a second session (the duplicate-draft trap, app #15).
            session = app.interview_sessions.filter(status='submitted').order_by('-submitted_at').first()
            if session is not None:
                session.status = 'draft'
        note = request.data.get('overall_note', '') or ''
        if session is None:
            # ⚠ NO interviewer here. The row must exist for a DELETE to persist, but causing a row
            # to exist is not conducting an interview — see `_is_authoring` and TD-216.
            session = InterviewSession(application=app, started_at=timezone.now())
        # Decided BEFORE the new values are written over the old ones.
        authored = _is_authoring(session.findings, findings, session.overall_note, note)
        session.findings = findings
        session.rubric = request.data.get('rubric', {}) or {}
        session.overall_note = note
        if authored:
            # ⚠ THE CREDIT MOVES TO WHOEVER WROTE THE CONTENT, EVERY TIME (owner, 2026-08-13).
            # One field, overwritten — an earlier contributor's name is expunged, which the owner
            # considered and accepted. Somebody who only re-saves, or only submits, keeps the
            # existing name: that is the case this exists to protect (A interviews, B submits →
            # the record must still read A).
            session.interviewer = admin
        session.save()
        # A draft save does NOT advance the funnel. 'interviewing' means the interview
        # process is genuinely underway for an accountable reviewer — reached by proposing
        # times (scheduling.propose_slots) or submitting the session (offline fallback),
        # both assignment-gated. Advancing on ANY draft save (incl. an agenda-item delete)
        # was a Phase-C leftover that mis-fired once V3 folded the agenda into the draft
        # (four live apps flipped on early triage). See docs/decisions.md.
        return Response(InterviewSessionSerializer(session).data)


class AdminInterviewSubmitView(_AdminBase):
    """POST .../<pk>/interview/submit/ — finalise the draft session and advance the
    application → interviewed. Reviewer/super only."""
    def post(self, request, pk):
        app, admin, err = self._require_open_case(request, pk)
        if err:
            return err
        session = app.interview_sessions.filter(status='draft').first()
        if session is None:
            return Response({'error': 'No draft interview to submit.', 'code': 'no_draft'},
                            status=status.HTTP_400_BAD_REQUEST)
        err = _validate_findings(session.findings or {})
        if err:
            return Response({'error': err, 'code': 'bad_findings'},
                            status=status.HTTP_400_BAD_REQUEST)
        if session.interviewer_id is None:
            session.interviewer = admin
            session.save(update_fields=['interviewer'])
        submit_interview(session)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminInterviewReopenView(_AdminBase):
    """POST .../<pk>/interview/reopen/ — the assigned reviewer reopens a SUBMITTED
    interview to add/edit a forgotten finding. Un-submits the latest session (→ draft)
    and reverts status interviewed→interviewing, which reopens BOTH the Interview Stage
    AND Check 2, and switches Approve/Decline off until it's re-submitted. Reviewer/super.
    Only valid BEFORE a decision is recorded — once decided, use the Decision panel's
    Reopen (super-only, holds the profile from the pool)."""
    def post(self, request, pk):
        app, admin, err = self._require_open_case(request, pk)
        if err:
            return err
        if app.verdict_decided_at is not None:
            return Response(
                {'error': 'A decision is recorded — reopen the decision instead.',
                 'code': 'decision_recorded'}, status=status.HTTP_400_BAD_REQUEST)
        session = app.interview_sessions.filter(status='submitted').order_by('-submitted_at').first()
        if session is None:
            return Response({'error': 'No submitted interview to reopen.', 'code': 'no_submitted'},
                            status=status.HTTP_400_BAD_REQUEST)
        session.status = 'draft'
        session.save(update_fields=['status', 'updated_at'])
        if app.status == 'interviewed':   # back a step so Check 2 + the decision gate reopen
            app.status = 'interviewing'
            app.save(update_fields=['status'])
        return Response(AdminApplicationDetailSerializer(app).data)
