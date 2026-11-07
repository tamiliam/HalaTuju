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

EVERY DEGREE STUDENT MUST HAVE THEM (owner 2026-11-07, apps 158 / 168 / 247, widened the same day):
a student bound for a university degree — or already studying for one — must have STPM /
Matriculation / Asasi / Diploma results on file; Check 2 checks that she DECLARED them and asks for
the document. Exempt: a UA diploma and PISMP (SPM entry: `results_route.destination` POST_SPM, and
an offer read as 'diploma' / 'pismp'), and an intake that asks no higher results (D16c).

* **Declared** (`declared_kind`): the results held when tertiary, else a LEGACY row's entered higher
  results (STPM grades / CGPA, or a third-route CGPA under a third-route exam) whose recorded
  completion still reads SPM — #161 / #205 / #226 / #243 / #251 / #276's shape, which the #388 rule
  missed because `results_held` honours the recorded 'spm'. Owed with that kind: the upload ask as
  #388's, and the upload carries the kind (`upload_kind`) so the card compares her entered results.
* **Declared nothing** (`undeclared`: SPM only, no tertiary exam declared — a Form Six student
  keeps her semester ask): we do not know WHICH she holds, so `_owed` answers `UNSPECIFIED` (never
  one of the four kinds) and every reader names all four. The Academic reason is
  `UNDECLARED_NOTE_CODE` (params ``kind`` '' → the drawer's generic slot); the ask is
  `DECLARE_ASK_CODE` — enter the results AND upload the document (model principle: a document with
  nothing declared can never tick), closed only when both are done. Her upload lands in the higher
  card with a BLANK `results_kind` (a guessed kind would turn "cannot tell" into "kind matches").
  Once one is on file the card reads it but stays at best Unsure with `UNDECLARED_ON_FILE_CODE`
  (`cap_undeclared`) — also for an application frozen AFTER S3a that requires the upload.
* **Degree-bound** (`results_route.degree_bound`, promoted from here 2026-11-07 for the funding
  estimate and the award rule): `results_route.destination` DEGREE; or, with no catalogue
  `course_id`, the chosen programme's name reads as a degree even under a post-SPM pathway code
  (#251: a stale 'stpm' code over a degree course). `destination()` itself is unchanged.
"""
from __future__ import annotations

#: The Check-2 document request (student-visible; copy `scholarship.actionCentre.item.<code>`).
ASK_CODE = 'higher_results_requested'
#: The Academic fact's reason item (cockpit copy `admin.scholarship.verdict.item.<code>`). NOT a
#: `resolution.CODE_TO_TICKET` code on purpose: the ask is Check 2's, so no second system ticket.
#: Spelled as a literal at its one `_item` call (`cap`) so `test_verdict_item_i18n` can check its words.
NOTE_CODE = 'higher_results_not_on_file'
#: `_owed`'s answer for an SPM-only, degree-bound student: owed, kind unknown. Deliberately NOT one
#: of `wrong_slip.HIGHER_KINDS`, so no reader can mistake it for a declared kind.
UNSPECIFIED = 'unspecified'
#: The SPM-only arm's two Academic reason items (cockpit copy `admin.scholarship.verdict.item.<code>`):
#: owed with none on file (the drawer's Missing slot reads it too), and on file but undeclared.
UNDECLARED_NOTE_CODE = 'higher_results_not_declared'
UNDECLARED_ON_FILE_CODE = 'higher_results_undeclared'
#: The Check-2 ask for a student who declared NO higher results: enter them on her results page AND
#: upload the document (copy `scholarship.actionCentre.item.<code>`, the card's onboarding button).
DECLARE_ASK_CODE = 'higher_results_declare_requested'
#: The two asks' `check2_queries.DOC_SPECS` and `GOVERNED_BY` entries (ONE home, spread in there).
ASK_SPECS = {ASK_CODE: {'doc_type': 'higher_results', 'fact': 'academic'},
             DECLARE_ASK_CODE: {'doc_type': 'higher_results', 'fact': 'academic'}}
GOVERNED = {ASK_CODE: (('document', 'results_slip'),), DECLARE_ASK_CODE: (('document', 'results_slip'),)}
#: Owner, 2026-11-07: these two asks ALONE may also be raised (or re-opened) by the machine while the
#: case is with its reviewer or awaiting QC — an exception to the Completed-stage-only rule
#: (`services.querying.AUTO_QUERY_STATUSES`, 2026-07-13) and the post-interview lock (V3), because a
#: degree student without her higher results on file is a gap that must reach her: "Even if the
#: student doesn't respond, the reviewer or QC may pick it up." Recommended onward stays out.
LATE_ASK_STATUSES = ('interviewing', 'interviewed')


def may_raise(application, code, may_ask: bool) -> bool:
    """May Check 2 CREATE / RE-OPEN `code` now? The general rule (`may_ask`), or one of the two
    higher-results asks on a completed application in `LATE_ASK_STATUSES`."""
    return may_ask or (code in ASK_SPECS and application.profile_completed_at is not None
                       and application.status in LATE_ASK_STATUSES)


def declared_kind(application) -> str:
    """The higher results she DECLARED: the results held when tertiary, else a legacy row's entered
    STPM results ('stpm') or third-route CGPA under a third-route exam ('matric' …); '' = none."""
    from apps.courses.exam_questions import THIRD_ROUTE, has_stpm_results
    from . import results_route
    kind = results_route.held_kind(application)
    profile = getattr(application, 'profile', None)
    if kind or profile is None:
        return kind
    if has_stpm_results(profile):
        return 'stpm'
    exam = (getattr(profile, 'exam_type', '') or '').strip().lower()
    return exam if exam in THIRD_ROUTE and getattr(profile, 'higher_cgpa', None) is not None else ''


def _spm_only(application) -> bool:
    """Declared SPM results only: held 'spm', no higher results entered, and the exam she declared is
    not a tertiary one (a Form Six student has no STPM results yet; her semester ask is her route)."""
    from apps.courses.exam_questions import is_tertiary
    from . import results_route
    if results_route.held(application) != 'spm' or declared_kind(application):
        return False
    return not is_tertiary(getattr(getattr(application, 'profile', None), 'exam_type', '') or '')


def _needs_higher(application) -> bool:
    """SUBMITTED, on an intake that asks higher results (D16c), a programme that asks for results,
    degree-bound, and no higher result already sitting in the SPM card (S4's wrong slip, #43: they
    ARE on file — the card says so itself)."""
    from . import requirements, results_route
    if getattr(application, 'profile_completed_at', None) is None:
        return False
    if not results_route.gift_asks_higher(application):
        return False
    if requirements.resolve(application, 'document').get('results_slip', 'off') == 'off':
        return False
    if not results_route.degree_bound(application):
        return False
    from .verdict_engine import _latest_doc
    from .wrong_slip import higher_kind
    return not higher_kind(_latest_doc(application, 'results_slip'))


def _too_late(application) -> bool:
    """Owner 2026-11-07: Recommended or any later stage (`family.DECIDED_STATUSES`) is too late for
    the 2026-11-07 arms — no owed slot, cap or ask. #388's own shape (held tertiary, catalogue
    degree) is unchanged."""
    from .family import DECIDED_STATUSES
    return getattr(application, 'status', '') in DECIDED_STATUSES


def undeclared(application) -> bool:
    """A degree-bound application whose student declared NO higher results — whatever her snapshot
    froze — before Recommended. The declare + upload ask's gap, and `cap_undeclared`'s test."""
    return (getattr(application, 'profile_completed_at', None) is not None and not _too_late(application)
            and _spm_only(application) and _needs_higher(application))


def _owed(application) -> str:
    """The declared kind ('stpm' | 'matric' | 'asasi' | 'diploma') — or `UNSPECIFIED` when she
    declared none — when the higher results are owed over a frozen pre-S3 requirement, else ''."""
    from . import requirements
    if getattr(application, 'profile_completed_at', None) is None:
        return ''
    from . import results_route
    held = results_route.held_kind(application)
    kind = declared_kind(application) or (UNSPECIFIED if _spm_only(application) else '')
    if not kind or not _needs_higher(application):
        return ''
    if _too_late(application) and not (held and results_route.destination(application) == results_route.DEGREE):
        return ''                        # a 2026-11-07 arm, at Recommended or later: too late
    return '' if requirements.resolve(application, 'document').get('higher_results') == 'required' else kind


def upload_kind(application) -> str:
    """`results_route.upload_kind`'s last fallback: the DECLARED kind of a legacy row that owes them
    (held SPM, STPM results entered), so her upload compares what she entered; '' otherwise."""
    from .wrong_slip import HIGHER_KINDS
    kind = _owed(application)
    return kind if kind in HIGHER_KINDS else ''


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
    another name) and `higher_results.answers_higher_ask` — the ONE rule an officer's request for
    named results reads too (`results_requests.answers`): not an SPM slip, the FINAL result (M4b)."""
    from .higher_results import answers_higher_ask, match_verdict
    return any(match_verdict(d) == 'ok' and answers_higher_ask(d) for d in _live_higher(application))


def final_owed_kind(application) -> str:
    """Owner ruling B (2026-10-29, M4b): the kind whose FINAL result is still owed because the higher
    upload the Academic card reads (`higher_results.higher_doc`: any live final one first, review
    SF4) is not the final one (a semester slip, a polytechnic's portal page, a transcript printing an
    in-progress status), for a SUBMITTED application that ASKS for higher results — its intake asks
    for them (D16c) and its Academic card is about them (`anchors_on_higher`, review SF6) — else ''.
    The kind is the upload's own (an officer's request names it there, `results_route.upload_kind`),
    else the results held. The same ask as #388's."""
    from . import results_route
    from .higher_results import anchors_on_higher, final_owed, higher_doc
    from .wrong_slip import HIGHER_KINDS
    if getattr(application, 'profile_completed_at', None) is None:
        return ''
    held = results_route.held_kind(application)      # cheapest first: an SPM holder reads no document
    if not held:
        return ''
    doc = higher_doc(application)
    if doc is None or not final_owed(doc):
        return ''
    if not (results_route.gift_asks_higher(application) and anchors_on_higher(application)):
        return ''                                    # SF6: a voluntary upload on an SPM-only intake asks none
    named = getattr(doc, 'results_kind', '') or ''
    return named if named in HIGHER_KINDS else held


def ask_codes(application) -> set:
    """`check2_queries._gap_sets`' share: {DECLARE_ASK_CODE} while she has declared no higher results
    (2026-11-07; it stays the one card, once open, until a clean upload answers it); {ASK_CODE} while
    owed and not answered; else empty. The
    sync's own rules then apply — raised once, only in the Completed stage
    (`services.auto_queries_allowed`), auto-resolved when this empties, re-opened if it re-fires."""
    if undeclared(application):          # 2026-11-07: declare AND upload, until she has declared
        return {DECLARE_ASK_CODE}
    owed = (_owed(application) and not answered(application)) or final_owed_kind(application)
    if not owed:
        return set()
    return {DECLARE_ASK_CODE if _open(application, (DECLARE_ASK_CODE,)) else ASK_CODE}   # one card


def _open(application, codes) -> bool:
    from .models import ResolutionItem
    return ResolutionItem.objects.filter(application=application, source='check2', code__in=codes,
                                         status='open').exists()


def ask_owns_higher_tickets(application) -> bool:
    """`resolution._ticketable_unresolved`: is Check 2's ask OPEN for an application that owes the
    higher results? Then it is the one Action-Centre card for that document, and S3's own
    higher-results tickets (`higher_results_unreadable` …, raised on the `late_anchor` card) are not
    raised beside it. The reviewer still sees the reason on the Academic card."""
    return bool(_owed(application) or undeclared(application)) and _open(application, (ASK_CODE, DECLARE_ASK_CODE))


def owes_higher(application) -> bool:
    """`check2_queries._gap_sets`: while the higher results are owed and not yet answered, Check 2
    does not ALSO ask for a semester result (#254/#255/#265/#388 had both open — the pairing that
    put STPM certificates in the semester slot). An open semester ask then auto-resolves."""
    return bool(ask_codes(application))


def ask_params(application, code) -> dict:
    """The params put on the ask at creation: the kind held, so the copy reads "Please upload your
    STPM results"; the declare ask's ``doc_on_file`` (`refresh_params`). Every other one: none ({})."""
    if code == DECLARE_ASK_CODE:
        return {DOC_ON_FILE: True} if _live_higher(application) else {}
    return {'results_kind': _owed(application) or final_owed_kind(application)} if code == ASK_CODE else {}


#: 2026-11-07 (app 278): the declare ask's flag that her higher-results DOCUMENT is already on file,
#: so the card (and the cockpit's Check-2 line) asks her only to ENTER her results — copy
#: `scholarship.actionCentre.item.higher_results_declare_requested.onFile`, chosen at render by this flag.
DOC_ON_FILE = 'doc_on_file'


def refresh_params(application, item) -> None:
    """Keep the declare ask's ``doc_on_file`` true to the documents NOW — every Check-2 sync (the
    cockpit's and the Action Centre's reads run one), so it is right when the upload arrives AFTER
    the ask was raised, or is removed. Every other item is left untouched."""
    if item is None or item.code != DECLARE_ASK_CODE:
        return
    params = dict(item.params or {})
    params.pop(DOC_ON_FILE, None)
    params.update(ask_params(application, DECLARE_ASK_CODE))
    if params != (item.params or {}):
        item.params = params
        item.save(update_fields=['params'])


def cap(fact, kind):
    """The Academic fact of an application owing the higher results: at best Unsure — 'verified'
    (Certain) and 'review' (Probable) fall to 'recommend' (Unsure, amber); a worse band stands —
    with the reason named. Owner 2026-11-06 (#388): STPM / Matric / Diploma / Asasi results are a
    MUST for a university student, so a matching SPM slip cannot carry the card to Probable while
    they are not on file (it was capped at Probable from 2026-10-27)."""
    from apps.courses.exam_questions import QUALIFICATION_LABELS
    from .verdict_engine import _item
    if fact['status'] in ('verified', 'review'):
        fact['status'] = 'recommend'
    if kind == UNSPECIFIED:     # SPM only, bound for a degree (2026-11-07): all four, none named
        fact['unresolved'].append(_item('higher_results_not_declared', kind=''))
    else:
        fact['unresolved'].append(_item('higher_results_not_on_file', held=QUALIFICATION_LABELS.get(kind, kind), kind=kind))
    return fact


def cap_undeclared(application, fact):
    """The Academic fact of an SPM-only, degree-bound application once a higher upload is on file
    (owner 2026-11-07, decision 5: a tick only on a match). She declared no higher results, so there
    is nothing to check the upload against: at best Unsure — Certain and Probable fall to 'recommend';
    a worse band stands — with `UNDECLARED_ON_FILE_CODE` named, so the officer confirms it at
    interview. Every other application's fact is returned untouched."""
    if not undeclared(application) or not _live_higher(application):
        return fact
    from .verdict_engine import _item
    if fact['status'] in ('verified', 'review'):
        fact['status'] = 'recommend'
    fact['unresolved'].append(_item('higher_results_undeclared'))
    return fact
