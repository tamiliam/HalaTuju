"""The Action Centre's per-document checks behind ``resolution.doc_match_verdict``.

⚠ WHY THIS IS A MODULE (audit sprint A3.4, 2026-11-10). ``doc_match_verdict`` was a 177-line
if/elif chain on the long-function ledger. Each document type's branch moved here whole, as one
function, in the same order and with the same lines; ``resolution.doc_match_verdict`` keeps its
name, its docstring and the higher-results route (tests patch both there) and now only picks the
check for the document type. A check returns ``'mismatch'`` / ``'unreadable'`` / ``'pending'`` /
``'insufficient'``, or ``None`` where the old branch fell through to ``'ok'``.

Every collaborator a test patches at its source (``income_engine.*``, ``academic_engine.*``,
``pathway_engine.*``) is still imported INSIDE the function that calls it, as it was.
"""
from .income_str_ownership import str_check_names_a_stranger


def _results_slip(doc, dt):
    """The SPM results slip: a name or grade clash is red; the subject list is soft."""
    from .academic_engine import student_slip_check

    def red(chk, *keys):
        return any((chk or {}).get(k) == 'mismatch' for k in keys)

    chk = student_slip_check(doc) or {}
    # NOTE: 'subjects' is deliberately NOT a doc mismatch. A slip 'subjects' mismatch means
    # the OFFICIAL slip lists a subject the student didn't enter in their /profile — the slip
    # is genuine, the profile is just incomplete. That is a SOFT discrepancy: Gopal nudges the
    # student to add the subject(s) at /profile (help_engine 'slip_subjects_missing'), the
    # Academic tile shows it as 'review' (academic_missing_subjects), and Check 2 follows up —
    # but it must NOT block submission or red the document. A NAME or GRADE (results) mismatch
    # still does.
    if red(chk, 'name', 'results'):
        return 'mismatch'
    # An unreadable scan keeps the task open — and it's unreadable whether the NAME
    # or the SUBJECT TABLE couldn't be read (a blurry slip whose name happens to
    # read but whose grades don't is still a re-upload). Previously only the name
    # was checked, so such a slip slipped through as 'ok'.
    if chk.get('name') == 'unreadable' or chk.get('subjects') == 'unreadable':
        return 'unreadable'
    # Not scanned yet (extraction deferred/skipped) → hold, don't greenlight. Keyed
    # on name/subjects, NOT results: results=='pending' also means "no grades on file
    # to compare against" (the slip itself read fine), which must still accept.
    if chk.get('name') == 'pending' or chk.get('subjects') == 'pending':
        return 'pending'


def _offer_letter(doc, dt):
    """The offer letter: identity first, then a confirmed non-official offer."""
    from .doc_red_keys import person_red     # the person-red keys' one home (TD-110)
    from .pathway_engine import student_offer_check, offer_official_status
    chk = student_offer_check(doc) or {}
    if person_red(dt, chk):
        return 'mismatch'
    # V2 (#3): a NON-OFFICIAL offer (conditional / private-IPTS / a pemakluman or UPU-semakan
    # notification) must NOT resolve an "upload your official offer" request — the officer sees
    # red, so the student can't be told "done". Gate only on a CONFIRMED not-official read;
    # 'unknown' (genuineness not scored yet — flag off / AI outage / not re-run) defers to the
    # reviewer and never gates on our own gap. Runs after the name/IC mismatch so an
    # identity clash still wins.
    if offer_official_status(doc) == 'not_genuine':
        return 'mismatch'
    if chk.get('name') == 'unreadable':
        return 'unreadable'
    if chk.get('name') == 'pending':
        return 'pending'          # not read yet — hold the task


def _parent_ic(doc, dt):
    """A parent's IC: the person-red keys unless the IC-number chain vouched for the earner."""
    from . import income_engine
    from .doc_red_keys import person_red
    from .services import is_ic_decode_error
    chk = income_engine.student_income_ic_check(doc) or {}
    # IC-number chain verified the earner from the BC↔proof number match (#9) — a card that's
    # the wrong family member's is then a soft note, not a red block.
    if not chk.get('chain_verified') and person_red(dt, chk):
        return 'mismatch'
    ran = bool(getattr(doc, 'vision_run_at', None))
    err = getattr(doc, 'vision_error', '') or ''
    if not ran or chk.get('deferred'):
        return 'pending'          # not scanned yet, or (TD-390) its second opinion is owed by us
    # An OCR-service outage is not the student's fault — don't call it unreadable.
    if (not err or is_ic_decode_error(err)) and not chk.get('readable'):
        return 'unreadable'


def _income_proof(doc, dt):
    """A salary slip or EPF statement: a person-red clash, else hold an unread file."""
    from . import income_engine
    from .doc_red_keys import person_red
    if person_red(dt, income_engine.student_income_proof_check(doc)):
        return 'mismatch'
    # V2 (#4): a Gemini error / blank read used to fall through to 'ok' and resolve the request
    # UNVERIFIED. Hold instead: not scanned yet → 'pending'; read nothing/badly → 'unreadable'.
    sv = (getattr(doc, 'vision_fields', None) or {}).get('student_verdict', '')
    if sv in ('', 'review_manually'):
        return 'pending'
    if sv in ('wrong_doc', 'unreadable', 'incomplete'):
        return 'unreadable'


def _str(doc, dt):
    """The STR: a red currency state, or a person-red clash proven to be a stranger's."""
    from . import income_engine
    from .doc_red_keys import person_red
    chk = income_engine.student_str_check(doc) or {}
    matched = 'match' in (chk.get('name_status'), chk.get('nric_status'))   # TD-409, ruling A:
    if chk.get('current_status') in income_engine.STR_RED_STATES or person_red(dt, chk) and (  # an
            matched or str_check_names_a_stranger(chk, doc.application)):   # unmatched STR is red only if PROVEN a stranger's
        return 'mismatch'
    cs = chk.get('current_status')   # 'unknown' = not read yet / deferred by OUR outage; TD-403
    if cs in ('unknown', 'future'):  # 'future' = a LATER year's page: neither closes the ask, neither is red
        return 'pending' if cs == 'unknown' else 'insufficient'
    if not matched:
        return 'pending'             # ruling A: an STR no card matched (near-miss / cannot judge) closes nothing


def _birth_certificate(doc, dt):
    """The birth certificate: child + mother rows, else hold an unread file."""
    from . import income_engine
    from .doc_red_keys import person_red
    # The FATHER row is not a blocker (#23): it is checked against the patronymic in the
    # student's own name, and a father with no Malaysian IC must not stop a re-upload from
    # resolving. Child + mother still do.
    if person_red(dt, income_engine.student_bc_check(doc)):
        return 'mismatch'
    # V2 (#4): same hold — an errored/blank BC extraction must not resolve the request as read.
    sv = (getattr(doc, 'vision_fields', None) or {}).get('student_verdict', '')
    if sv in ('', 'review_manually'):
        return 'pending'
    if sv in ('wrong_doc', 'unreadable', 'incomplete'):
        return 'unreadable'


def _guardianship_letter(doc, dt):
    """The guardianship letter: the person-red keys, else hold a non-letter."""
    from . import income_engine
    from .doc_red_keys import person_red
    if person_red(dt, income_engine.student_guardianship_check(doc)):
        return 'mismatch'
    # V1 (#1): now that guardianship_letter actually field-extracts on upload, a file that
    # read NOTHING guardianship-shaped (a selfie / wrong document) must be HELD for
    # re-upload, not silently accepted. Before this wiring the extraction never ran, so
    # ANY file resolved an officer's guardianship-letter request.
    sv = (getattr(doc, 'vision_fields', None) or {}).get('student_verdict', '')
    if sv in ('', 'review_manually'):
        return 'pending'          # not read yet — hold, don't greenlight
    if sv == 'wrong_doc':
        return 'unreadable'       # nothing guardianship-shaped → re-upload


def _income_support_doc(doc, dt):
    """The declared-informal-income support document: hold a blank or wrong read."""
    # V1 (#2): the declared-informal-income supporting doc. A blank/wrong image reads no
    # fields → 'wrong_doc' → hold the task (re-upload). Not scanned yet → hold. A real
    # support document ('ok') accepts. (has_income_support_doc gates the verdict engine
    # in lockstep — mere presence no longer clears the declared-income gap.)
    sv = (getattr(doc, 'vision_fields', None) or {}).get('student_verdict', '')
    if sv in ('', 'review_manually'):
        return 'pending'
    if sv == 'wrong_doc':
        return 'unreadable'


def _academic_doc(doc, dt):
    """A school-leaving certificate or semester result: hold a blank or wrong read."""
    # V4: the promoted academic docs field-extract; a blank/wrong image is held for re-upload
    # rather than silently resolving its request. A real read ('ok') accepts.
    sv = (getattr(doc, 'vision_fields', None) or {}).get('student_verdict', '')
    if sv in ('', 'review_manually'):
        return 'pending'
    if sv == 'wrong_doc':
        return 'unreadable'


def _bank_statement(doc, dt):
    """The bank statement: the doc-assist verdict on the holder and the three fields."""
    # Reads the doc-assist verdict (holder==student + all 3 fields present), computed
    # deterministically from the Gemini-extracted fields. 'name_mismatch' = the account
    # is in someone else's name (a HARD problem → mismatch); 'incomplete'/'wrong_doc' =
    # a field couldn't be read clearly (re-upload → unreadable). Not yet scanned → hold.
    sv = (getattr(doc, 'vision_fields', None) or {}).get('student_verdict', '')
    if sv in ('', 'read', 'review_manually'):
        return 'pending'
    if sv == 'name_mismatch':
        return 'mismatch'
    if sv in ('incomplete', 'wrong_doc', 'unreadable'):
        return 'unreadable'


def _ic(doc, dt):
    """The student's own IC: not read, deferred, unreadable, or an NRIC / name clash."""
    from .services import is_ic_decode_error
    ran = bool(getattr(doc, 'vision_run_at', None))
    if not ran:
        return 'pending'          # not scanned yet — don't greenlight an unread IC
    err = getattr(doc, 'vision_error', '') or ''
    service_down = bool(err) and not is_ic_decode_error(err)
    if not service_down:
        from .read_errors import ic_second_opinion_deferred
        if ic_second_opinion_deferred(doc):
            return 'pending'      # TD-390: the read our outage left half-done neither fails nor passes
        from .vision import nric_match, name_match
        prof = getattr(doc.application, 'profile', None)
        if not doc.vision_nric or not doc.vision_name:
            return 'unreadable'
        if not nric_match(doc.vision_nric, getattr(prof, 'nric', '') or ''):
            return 'mismatch'
        if name_match(doc.vision_name, getattr(prof, 'name', '') or '') == 'mismatch':
            return 'mismatch'


#: document type → its check, in the order the old if/elif chain tested them. A type that is not
#: here (bills, statement of intent, photo, the soft documents) is accepted: ``'ok'``.
DOC_MATCH_CHECKS = {
    'results_slip': _results_slip,
    'offer_letter': _offer_letter,
    'parent_ic': _parent_ic,
    'salary_slip': _income_proof,
    'epf': _income_proof,
    'str': _str,
    'birth_certificate': _birth_certificate,
    'guardianship_letter': _guardianship_letter,
    'income_support_doc': _income_support_doc,
    'school_leaving_cert': _academic_doc,
    'semester_result': _academic_doc,
    'bank_statement': _bank_statement,
    'ic': _ic,
}
