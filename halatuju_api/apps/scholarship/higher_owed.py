"""Higher results OWED by a submitted application whose frozen requirement predates them.
Third results route follow-up (2026-10-27; owner option A, application #388).

#388 was submitted shortly before S3a shipped, so its `requirements_snapshot` froze "SPM slip
required" with no `higher_results` key. The student holds STPM results and chose a degree (D12:
the higher results are the required upload), but uploaded only her SPM slip — and the cockpit
showed nothing missing while Academic read Certain on the SPM slip alone.

⚠ THIS NEVER TOUCHES A GATE. The frozen snapshot stays exactly as it was: `requirements.resolve`,
`application_completeness`, `revert_if_profile_incomplete`, the blockers and the consent gate are
not read or changed here, so no submitted application can be sent back to the wizard by this. It
is a display + verdict + ask concern only:

* **Show the gap** — the Academic fact carries ``higher_results_not_on_file`` (the cockpit's
  Documents drawer draws the "STPM results" slot as Missing from it, the value served, never
  re-derived in the browser).
* **Verdict** — that fact cannot be Certain: capped at Probable ('review'), with the reason named.
* **Ask** — one system Check-2 document request (`ASK_CODE`, `check2_queries.DOC_SPECS`), raised
  by the sync's own stage rules (machine asks only in the Completed stage) and closed by the
  sync's housekeeping once a live higher-results upload ANSWERS it (`answered`, S4's
  `results_requests.answers` rule: anything but an SPM slip, read clean). The upload lands in the
  higher-results card with the held kind (`results_route.upload_kind` — the results held, which
  `owed_kind` requires to be tertiary). No SPM ask, ever (D9 unchanged).

Who it applies to (`_owed`): SUBMITTED; results held tertiary (`exam_questions.is_tertiary`,
incl. D1's read-time promotion); bound for a university degree (`results_route.destination`); a
programme that asks for results at all; a frozen requirement that does NOT already require the
higher results (those already read the higher card and raise their own S3 ticket); and no higher
result already sitting in the SPM card (S4's wrong-slip note speaks for that one).
"""
from __future__ import annotations

#: The Check-2 document request (student-visible; copy `scholarship.actionCentre.item.<code>`).
ASK_CODE = 'higher_results_requested'
#: The Academic fact's reason item (cockpit copy `admin.scholarship.verdict.item.<code>`). NOT a
#: `resolution.CODE_TO_TICKET` code on purpose: the ask is Check 2's, so no second system ticket.
#: Spelled as a literal at its one `_item` call (`cap`) so `test_verdict_item_i18n` can check its words.
NOTE_CODE = 'higher_results_not_on_file'


def _owed(application) -> str:
    """The held kind ('stpm' | 'matric' | 'asasi' | 'diploma') when the higher results are owed
    over a frozen pre-S3 requirement, else ''. Cheapest test first: an SPM holder (most rows)
    stops at the second line and reads nothing."""
    from . import requirements, results_route
    if getattr(application, 'profile_completed_at', None) is None:
        return ''
    kind = results_route.held_kind(application)
    if not kind:
        return ''
    if not results_route.gift_asks_higher(application):        # D16c: an SPM-only intake asks none
        return ''
    docs = requirements.resolve(application, 'document')        # the FROZEN copy once submitted
    if docs.get('higher_results') == 'required' or docs.get('results_slip', 'off') == 'off':
        return ''
    if results_route.destination(application) != results_route.DEGREE:
        return ''
    # Her higher results already sit in the SPM card (S4's wrong slip, #43): they ARE on file — the
    # card says so itself — so asking for them again would ask for what she sent.
    from .verdict_engine import _latest_doc
    from .wrong_slip import higher_kind
    return '' if higher_kind(_latest_doc(application, 'results_slip')) else kind


def _live_higher(application):
    from .document_snapshot import live_docs
    return list(live_docs(application, 'higher_results'))


def owed_kind(application) -> str:
    """The kind owed when NO higher-results document is on file at all — the drawer's Missing slot
    and the Academic cap. Once one is uploaded, `late_anchor` makes the higher card read it."""
    kind = _owed(application)
    return kind if kind and not _live_higher(application) else ''


def late_anchor(application) -> bool:
    """A higher-results upload is on file for an application that owes them: the Academic fact is
    about it (`higher_results.anchors_on_higher`), as for one frozen with them required."""
    return bool(_owed(application)) and bool(_live_higher(application))


def answered(application) -> bool:
    """Does a live higher-results upload answer the ask? Read clean (not pending, unreadable or in
    another name), not an SPM slip — the S4 rule `results_requests.answers` applies to an
    officer's request for named results — and the FINAL result (owner ruling B, M4b)."""
    from .higher_results import final_owed, match_verdict, student_higher_check
    return any(match_verdict(d) == 'ok' and student_higher_check(d)['kind_status'] != 'spm'
               and not final_owed(d) for d in _live_higher(application))


def final_owed_kind(application) -> str:
    """Owner ruling B (2026-10-29, M4b): the kind whose FINAL result is still owed because the live
    higher-results upload is not the final one (a semester slip, the portal page, a transcript with
    no completion status), for a SUBMITTED application — else ''. The same ask as #388's."""
    from . import results_route
    from .higher_results import final_owed
    if getattr(application, 'profile_completed_at', None) is None:
        return ''
    kind = results_route.held_kind(application)      # cheapest first: an SPM holder reads no document
    if not kind:
        return ''
    live = _live_higher(application)
    return kind if live and all(final_owed(d) for d in live) else ''


def ask_codes(application) -> set:
    """`check2_queries._gap_sets`' share: {ASK_CODE} while owed and not answered, else empty. The
    sync's own rules then apply — raised once, only in the Completed stage
    (`services.auto_queries_allowed`), auto-resolved when this empties, re-opened if it re-fires."""
    owed = (_owed(application) and not answered(application)) or final_owed_kind(application)
    return {ASK_CODE} if owed else set()


def ask_owns_higher_tickets(application) -> bool:
    """`resolution._ticketable_unresolved`: is Check 2's ask OPEN for an application that owes the
    higher results? Then it is the one Action-Centre card for that document, and S3's own
    higher-results tickets (`higher_results_unreadable` …, raised on the `late_anchor` card) are not
    raised beside it. The reviewer still sees the reason on the Academic card."""
    from .models import ResolutionItem
    return bool(_owed(application)) and ResolutionItem.objects.filter(
        application=application, source='check2', code=ASK_CODE, status='open').exists()


def owes_higher(application) -> bool:
    """`check2_queries._gap_sets`: while the higher results are owed and not yet answered, Check 2
    does not ALSO ask for a semester result (#254/#255/#265/#388 had both open — the pairing that
    put STPM certificates in the semester slot). An open semester ask then auto-resolves."""
    return bool(ask_codes(application))


def ask_params(application, code) -> dict:
    """The params frozen onto the ask at creation: the kind held, so the copy reads "Please upload
    your STPM results." Every other Check-2 document request carries none ({})."""
    return {'results_kind': _owed(application) or final_owed_kind(application)} if code == ASK_CODE else {}


def cap(fact, kind):
    """The Academic fact of an application owing the higher results: never Certain — 'verified'
    falls to 'review' (Probable); a worse band stands — with the reason named."""
    from apps.courses.exam_questions import QUALIFICATION_LABELS
    from .verdict_engine import _item
    if fact['status'] == 'verified':
        fact['status'] = 'review'
    fact['unresolved'].append(_item('higher_results_not_on_file', held=QUALIFICATION_LABELS.get(kind, kind), kind=kind))
    return fact
