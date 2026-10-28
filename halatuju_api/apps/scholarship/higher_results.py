"""The higher-results upload (STPM / Matriculation / Asasi / Diploma), read and checked.
Third results route S3a + S3b (2026-10-26; roadmap §5 S3, owner rulings D6 D9 D12 D13).

What this module owns, in the order a document meets it:

1. **The read** (`SCHEMA`, `HINT`, `extract`) — one Gemini read of the image for the name, the
   exam title, the CGPA and (STPM) the subject grades, plus the routing detection of
   `results_kind.py` from the upload's OCR text. Genuineness (STPM exact-read S3): an STPM page is
   scored in `vision` by `genuineness.stpm_doc.stpm_higher_genuineness` (+ ruling 1A); every other
   kind has no signature family yet, so its card shows "not checked" and the TD-114 floor holds the
   fact at Probable at best — never a "suspect" it has not earned.
2. **The student's check** (`student_higher_check`) — the facts the Documents card shows and the
   ONE note it may add (D13), each with one link:
     (D) an SPM slip in this card → "This appears to be your SPM results slip …" + "Move it to SPM
         results slip" (a misfile first), with "Don't have … results?" for the rare case;
     (B) a different higher kind than the results page → "This appears to be Matriculation
         results, but your application shows STPM." + "Update your results";
     (C) subjects / grades / CGPA that differ from those entered → "Some subjects or grades on this
         slip differ from those entered." + "Correct your STPM results".
   A note is NEVER a block (D13). "Cannot tell" (no detection, nothing read) says nothing.
3. **The gate's reading** (`match_verdict`) — the Action Centre / promotion verdict.
4. **The reviewer's Academic card** (`verdict_academic`, `red_chips`) — name + kind + CGPA (+ STPM
   grades) against the profile; the SPM slip compared only when one is on file (D9).

The SPM slip itself is untouched here: `academic_engine.student_slip_check` still reads it.
"""
from __future__ import annotations

import re

from apps.courses.exam_questions import spm_grades_for  # re-exported: one SPM-grade reader (S3b)

_STR = {'type': 'string'}

#: The Gemini schema for a higher-results document (registered in `vision._FIELD_SCHEMAS`).
SCHEMA = {'type': 'object', 'properties': {
    'candidate_name': _STR, 'exam': _STR, 'cgpa': _STR, 'cgpa_label': _STR, 'institution': _STR,
    'results': {'type': 'array', 'items': {'type': 'object',
                'properties': {'subject': _STR, 'grade': _STR}}},
    'warnings': {'type': 'array', 'items': _STR},
}}

#: The extraction hint (registered in `vision._DOC_HINTS`).
HINT = (' This is a Malaysian post-SPM results document — an STPM results slip or certificate '
        '(Sijil Tinggi Persekolahan Malaysia), a Matriculation results slip (Program Matrikulasi), '
        'an Asasi / Foundation transcript, or a Diploma transcript. Read: "candidate_name" = the '
        'student\'s full name; "exam" = the document\'s own title exactly as printed (e.g. "SIJIL '
        'TINGGI PERSEKOLAHAN MALAYSIA 2025" or "KEPUTUSAN PEPERIKSAAN PROGRAM MATRIKULASI"); '
        '"cgpa" = the CUMULATIVE grade point average (PNGK / CGPA) as a number like 3.67, or '
        'empty if none is printed — never a one-semester PNG / GPA; "cgpa_label" = the label '
        'printed beside that number exactly as printed (e.g. PNGK, CGPA, CUMULATIVE GPA); "institution" = the college / university, if printed; '
        '"results" = one {subject, grade} per subject row with the LETTER grade exactly as printed '
        '(A, A-, B+ …) — subject NAME only, no code. Ignore MUET lines and watermark text.')

#: The student tickets these codes raise (merged into `resolution.CODE_TO_TICKET`): a missing or
#: unreadable upload is the student's to fix in the Action Centre (the `_missing` / `_unreadable`
#: suffix puts both in `STUDENT_DOC_REQUEST_CODES`); another person's name is a doc ticket the
#: reviewer raises by hand, like the SPM slip's. The kind / CGPA / grade notes raise NO ticket —
#: the Documents card says them, the reviewer sees them, and none is a block (D13).
TICKETS = {
    'higher_results_missing': {'fact': 'academic', 'kind': 'doc', 'doc_type': 'higher_results'},
    'higher_results_unreadable': {'fact': 'academic', 'kind': 'doc', 'doc_type': 'higher_results'},
    'higher_results_name_mismatch': {'fact': 'academic', 'kind': 'doc', 'doc_type': 'higher_results'},
}

#: The results page that edits each kind (the web's `resultsEditPath`).
RESULTS_PAGE = {'stpm': '/onboarding/stpm-grades', 'matric': '/onboarding/higher-grades',
                'asasi': '/onboarding/higher-grades', 'diploma': '/onboarding/higher-grades'}

#: STPM subject keys (`stpm_grades`, the web's `STPM_SUBJECTS`) → the names a slip prints for
#: them, Malay and English. An unrecognised printed subject is IGNORED (cannot tell → no note).
_STPM_NAMES = {
    'PA': ('pengajian am', 'general studies'), 'MATH_T': ('matematik t', 'mathematics t'),
    'MATH_M': ('matematik m', 'mathematics m'), 'PHYSICS': ('fizik', 'physics'),
    'CHEMISTRY': ('kimia', 'chemistry'), 'BIOLOGY': ('biologi', 'biology'),
    'FURTHER_MATH': ('matematik lanjutan t', 'further mathematics t', 'further mathematics'),
    'ECONOMICS': ('ekonomi', 'economics'), 'ACCOUNTING': ('perakaunan', 'accounting'),
    'BUSINESS': ('pengajian perniagaan', 'business studies'), 'GEOGRAFI': ('geografi', 'geography'),
    'SEJARAH': ('sejarah', 'history'),
    'KESUSASTERAAN_MELAYU': ('kesusasteraan melayu', 'kesusasteraan melayu komunikatif',
                             'communicative malay literature'),
    'BAHASA_MELAYU': ('bahasa melayu',), 'BAHASA_CINA': ('bahasa cina', 'chinese language'),
    'BAHASA_TAMIL': ('bahasa tamil', 'tamil language'), 'SENI_VISUAL': ('seni visual', 'visual arts'),
    'SYARIAH': ('syariah', 'syariah islamiah', 'pengajian syariah'),
    'USULUDDIN': ('usuluddin', 'pengajian usuluddin'),
    'ICT': ('sains komputer', 'ict', 'information and communications technology', 'computing'),
    # STPM CGPA sprint C1 (2026-10-28): the rest of the MPM list (`courses/stpm_subjects.py`).
    'BAHASA_ARAB': ('bahasa arab', 'arabic language'),
    'LITERATURE_IN_ENGLISH': ('literature in english', 'kesusasteraan inggeris'),
    'TAHFIZ_AL_QURAN': ('tahfiz al-quran', 'tahfiz al quran'),
    'SAINS_SUKAN': ('sains sukan', 'sports science'),
}


def _squash(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


_STPM_BY_NAME = {_squash(n): key for key, names in _STPM_NAMES.items() for n in names}


def _fields(doc):
    vf = doc.vision_fields if isinstance(getattr(doc, 'vision_fields', None), dict) else {}
    f = vf.get('fields')
    return vf, (f if isinstance(f, dict) else {})


#: How far a slip's CGPA may sit from the one entered and still agree (review fix 7): a print
#: rounds to two places and some transcripts to one, so 0.01 read rounding as a mismatch.
CGPA_TOLERANCE = 0.05
#: A label that names a CUMULATIVE figure — the only one a mismatch may be asserted against. A bare
#: PNG / GPA is one semester's (review fix 7); an unlabelled number cannot be told apart.
_CUMULATIVE_LABEL = re.compile(r'PNGK|CGPA|KUMULATIF|CUMULATIVE|HIMPUNAN', re.IGNORECASE)


def _as_cgpa(v):
    try:
        x = float(str(v).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return None
    return x if 0 < x <= 4.0 else None


def entered_grade_value(g) -> str:
    """An ENTERED STPM grade as both readers compare it (`_compare_stpm` and the Exact reader)."""
    return (g or '').strip().upper()


def entered_lookup(grades):
    """`subject name → the student's normalised entry for it`, or None when there are no grades."""
    if not isinstance(grades, dict) or not grades:
        return None

    def lookup(subject):
        return entered_grade_value(grades.get(_STPM_BY_NAME.get(_squash(subject)))) or None
    lookup.count = sum(1 for g in grades.values() if entered_grade_value(g))   # subjects entered (stpm_parse 1.2.0)
    return lookup


def _entered_grade(doc):
    """The student's own STPM grades for the Exact reader's owner rule 2: an unclear grade letter
    or point may be completed from the scale only when the value read matches the entry."""
    profile = getattr(getattr(doc, 'application', None), 'profile', None)
    return entered_lookup(getattr(profile, 'stpm_grades', None))


# ── 1. The read ───────────────────────────────────────────────────────────────────────────────

#: A Gemini note that the institution is not printed ("The institution where the candidate studied
#: is not specified."). An STPM certificate or slip never prints one and nothing checks the field,
#: so the note only confuses the reviewer; it is dropped on an STPM read. Every other warning is kept.
_ABSENT = (r'(?:(?:is|was|are)\s+)?(?:not\s+(?:specified|printed|stated|shown|provided|mentioned|'
           r'found|visible|available|given|listed|indicated|present|included|identified)|missing|'
           r'unspecified|absent|unknown|unavailable)')
_NO_INSTITUTION = re.compile(
    rf'^\W*(?:the\s+)?(?:name\s+of\s+the\s+)?institution\b[^.;]*?\b{_ABSENT}\b[^.;]*\.?\s*$'
    rf'|^\W*(?:no|missing|unspecified|unknown)\s+institution\b[^.;]*\.?\s*$', re.IGNORECASE)

#: A second clause ("..., and the name does not match"; "..., which may mean it was cropped") is kept.
_SECOND_CLAUSE = re.compile(r'[,;:]|\b(?:and|but|which|while|although|though|however|or|so)\b',
                            re.IGNORECASE)


def _is_institution_noise(warning) -> bool:
    """Only a WHOLE short warning that says the institution is absent (one sentence, one clause) —
    a warning that goes on to say anything else (a mismatch, another field, cropping) is kept."""
    w = str(warning or '').strip()
    return not _SECOND_CLAUSE.search(w) and bool(_NO_INSTITUTION.match(w))



def extract(doc, ocr, image_fn, extract_fn):
    """The higher-results read for `vision._run_field_extraction_impl`. An STPM certificate, slip
    or transcript is read EXACT first (`stpm_parse`, from the OCR text / word boxes — STPM
    exact-read S2); anything it is unsure of goes to Gemini on the IMAGE as before (a transcript's
    table, like the SPM slip's, does not survive flat OCR). Then the routing detection from the
    upload's OCR text (fallback: the read's own exam title). Returns the usual `ex` dict. The
    detection is stored beside the fields — `results_kind_detected` and the markers seen."""
    from .results_kind import detect, detect_from_fields, kinds_seen
    text = ((ocr or {}).get('text') if isinstance(ocr, dict) else '') or ''
    if ocr is None:          # a caller with no shared read (never the upload, which passes one)
        from .vision import ocr_document
        text = (ocr_document(doc) or {}).get('text', '') or ''
    try:                     # the Exact reader must never break a read: any failure → Gemini
        from .stpm_parse import PARSER_VERSION, parse as stpm_parse
        exact = stpm_parse(text, (ocr or {}).get('words') if isinstance(ocr, dict) else None,
                           entered=_entered_grade(doc))
    except Exception:
        exact = None
    if exact is not None:    # the reader's version is stored beside `capture`, never in the fields
        ex = {'fields': exact, 'warnings': [], 'error': '', 'capture': 'deterministic',
              'parser_version': f'stpm_parse {PARSER_VERSION}',
              'stpm_rows_from_entry': exact.pop('_rows_from_entry', []),   # audit: rule-2 rows
              'stpm_rows_sign_from_point': exact.pop('_rows_sign_from_point', [])}   # ruling B rows
    else:
        image = image_fn()
        if image is not None:
            ex = extract_fn('', doc.doc_type, image=image, content_type=doc.content_type)
        else:
            ex = extract_fn(text, doc.doc_type)
        ex['capture'] = 'ai'
    fields = ex.get('fields')
    if isinstance(fields, dict) and fields and not ex.get('error'):
        fields['results_kind_detected'] = detect(text) or detect_from_fields(fields)
        fields['results_kind_markers'] = kinds_seen(text)
        if ex['capture'] == 'ai' and fields['results_kind_detected'] == 'stpm':   # STPM prints none
            ex['warnings'] = [w for w in ex.get('warnings') or [] if not _is_institution_noise(w)]
    return ex


# ── 2. The student's check ─────────────────────────────────────────────────────────────────────


def _entered_cgpa(profile, kind):
    """The CGPA the student ENTERED for this kind, on the slip's own scale: STPM — the PNGK of the
    entered grades, Pengajian Am + the best three others (`stpm_pngk.pngk_from_grades`, CGPA sprint
    C2: the certificate's own rule; until then a plain average of every grade, which disagreed
    with every certificate of a five-subject candidate), None with fewer than PA + three; the
    third route — the CGPA as entered (`higher_cgpa`). None when nothing was entered."""
    if profile is None:
        return None
    if kind == 'stpm':
        from apps.courses.stpm_pngk import pngk_from_grades
        return pngk_from_grades(getattr(profile, 'stpm_grades', None))
    return _as_cgpa(getattr(profile, 'higher_cgpa', None))


def _compare_stpm(profile, fields):
    """(missing, mismatched) — printed STPM subjects the student did not enter, and entered
    grades that differ from the slip's. Unrecognised printed subjects are ignored."""
    entered = {k: entered_grade_value(g) for k, g in (getattr(profile, 'stpm_grades', None) or {}).items()}
    missing, mismatched = [], []
    for row in fields.get('results') or []:
        if not isinstance(row, dict):
            continue
        name = (row.get('subject') or '').strip()
        key = _STPM_BY_NAME.get(_squash(re.sub(r'^\d+\s*', '', name)))   # "950 MATEMATIK (T)"
        if key is None:
            continue
        slip = re.sub(r'\s+', '', (row.get('grade') or '')).upper()
        if key not in entered:
            missing.append(name)
        elif slip and slip != entered[key]:
            mismatched.append({'subject': name, 'typed': entered[key], 'slip': slip})
    return missing, mismatched


def student_higher_check(doc) -> dict:
    """The facts of ONE higher-results document against the student's own profile — the single
    source the Documents card, the gates and the Academic card read, so none can disagree.

    ``{name, candidate_name, exam, kind_held, kind_detected, kind_status, cgpa_slip,
    cgpa_entered, cgpa_status, grades_status, missing, mismatched, readable, note, note_kind,
    note_path, actions_open}``.
    Statuses: 'match' / 'mismatch' / 'unreadable' / 'pending' ('' when not applicable).
    `kind_status`: 'match' | 'different' | 'spm' | '' (cannot tell). `readable` is None until
    read. `note`: 'spm_slip' | 'kind_differs' | 'grades_differ' | '' — the ONE note to show (D13),
    in that order; `note_kind` is the results page the note's link opens."""
    from apps.courses.exam_questions import is_tertiary, results_held
    from .academic_engine import _slip_name_status
    vf, f = _fields(doc)
    sv = vf.get('student_verdict')
    read = bool(sv) and sv != 'review_manually'
    profile = getattr(getattr(doc, 'application', None), 'profile', None)
    held = results_held(profile)
    kind_held = held if is_tertiary(held) else (getattr(doc, 'results_kind', '') or '')
    detected = (f.get('results_kind_detected') or '') if read else ''
    kind_status = ('' if not detected or not kind_held else 'spm' if detected == 'spm'
                   else 'match' if detected == kind_held else 'different')
    slip_cgpa = _as_cgpa(f.get('cgpa'))
    entered = _entered_cgpa(profile, kind_held)
    if not read:
        cgpa_status = 'pending'
    elif slip_cgpa is None:
        cgpa_status = 'unreadable'
    elif entered is None:
        cgpa_status = 'pending'
    elif abs(slip_cgpa - entered) <= CGPA_TOLERANCE:
        cgpa_status = 'match'
    elif _CUMULATIVE_LABEL.search(str(f.get('cgpa_label') or '')):
        cgpa_status = 'mismatch'
    else:
        cgpa_status = 'pending'       # a figure we cannot tell is cumulative: never a note (fix 7)
    missing, mismatched = ([], [])
    grades_status = ''
    if kind_held == 'stpm' and read and kind_status != 'spm':
        missing, mismatched = _compare_stpm(profile, f)
        grades_status = 'mismatch' if (missing or mismatched) else (
            'match' if f.get('results') else 'pending')
    readable = None if not read else bool(
        sv not in ('wrong_doc', 'unreadable') and (slip_cgpa is not None or f.get('results')
                                                   or (f.get('candidate_name') or '').strip()))
    if kind_status == 'spm':
        note, note_kind = 'spm_slip', kind_held
    elif kind_status == 'different':
        note, note_kind = 'kind_differs', detected
    elif grades_status == 'mismatch' or cgpa_status == 'mismatch':
        note, note_kind = 'grades_differ', kind_held
    else:
        note, note_kind = '', ''
    return {
        'name': _slip_name_status(doc), 'candidate_name': f.get('candidate_name') or '',
        'exam': (f.get('exam') or '').strip(), 'kind_held': kind_held, 'kind_detected': detected,
        'kind_status': kind_status, 'cgpa_slip': slip_cgpa, 'cgpa_entered': entered,
        'cgpa_status': cgpa_status, 'grades_status': grades_status, 'missing': missing,
        'mismatched': mismatched, 'readable': readable, 'note': note, 'note_kind': note_kind,
        'note_path': RESULTS_PAGE.get(note_kind, ''),
        # The note's two ACTIONS (move it / SPM only) are open only before the Step-4 Submit
        # (review fix 1+2); after it the reviewer's own request route is the way.
        'actions_open': getattr(getattr(doc, 'application', None), 'profile_completed_at', 1) is None,
    }


# ── 3. The gate's reading ──────────────────────────────────────────────────────────────────────


def match_verdict(doc) -> str:
    """`resolution.doc_match_verdict` for a higher-results upload: 'mismatch' (another person's
    name), 'unreadable' (nothing usable read), 'pending' (not read yet) or 'ok'. A kind / grades
    note is NOT a mismatch (D13: a note is never a block) — so an SPM slip filed here is still
    promoted into the card, where its note can offer to move it."""
    chk = student_higher_check(doc)
    if chk['name'] == 'mismatch':
        return 'mismatch'
    if chk['readable'] is None:
        return 'pending'
    return 'ok' if chk['readable'] else 'unreadable'


# ── 4. The reviewer's Academic card ────────────────────────────────────────────────────────────


def anchors_on_higher(application) -> bool:
    """Is the Academic fact about the higher results? When they are the REQUIRED upload (live D12
    rule, or frozen at submit) — or, for an application submitted before S3a that OWES them (#388,
    `higher_owed`), once a higher-results upload is on file. Every other application submitted
    before S3a, and every SPM route, keeps the SPM card unchanged."""
    from . import higher_owed, requirements
    return (requirements.resolve(application, 'document').get('higher_results') == 'required'
            or higher_owed.late_anchor(application))


def academic_fact(application, spm_fact):
    """`verdict_engine._verdict_academic`'s card choice. `spm_fact()` builds the SPM card's own
    answer (called once). The higher card when it anchors (S3); else the SPM card — capped at
    Probable with the reason named while the higher results are owed and none is on file (#388)."""
    from . import higher_owed
    if anchors_on_higher(application):
        return verdict_academic(application, spm_fact())
    kind = higher_owed.owed_kind(application)
    return higher_owed.cap(spm_fact(), kind) if kind else spm_fact()


def verdict_academic(application, spm_fact):
    """The Academic fact for a higher-results applicant. `spm_fact` is the SPM card's own answer
    (`verdict_engine._verdict_academic(spm_only=True)`), folded in ONLY when an SPM slip is on file
    (D9: optional — a missing one is no gap and asks nothing)."""
    from .verdict_engine import _fact, _item, _latest_doc
    doc = _latest_doc(application, 'higher_results')
    if doc is None:
        return _fact('academic', 'gap', [], [_item('higher_results_missing')])
    chk = student_higher_check(doc)
    evidence, unresolved = [], []
    if chk['name'] == 'mismatch':
        unresolved.append(_item('higher_results_name_mismatch'))
    elif chk['name'] == 'match':
        evidence.append(_item('higher_results_name_ok'))
    if chk['readable'] is None:
        unresolved.append(_item('higher_results_unverified'))
    elif not chk['readable']:
        unresolved.append(_item('higher_results_unreadable'))
    from apps.courses.exam_questions import QUALIFICATION_LABELS as name   # the sponsor line's words
    kind = name.get(chk['kind_held'], chk['kind_held'])
    if chk['kind_status'] == 'spm':
        unresolved.append(_item('higher_results_is_spm', held=kind))
    elif chk['kind_status'] == 'different':
        unresolved.append(_item('higher_results_kind_differs', held=kind,
                                seen=name.get(chk['kind_detected'], chk['kind_detected'])))
    elif chk['kind_status'] == 'match':
        evidence.append(_item('higher_results_kind_ok', held=kind))
    if chk['cgpa_status'] == 'match':
        evidence.append(_item('higher_results_cgpa_ok', cgpa=f"{chk['cgpa_slip']:.2f}"))
    elif chk['cgpa_status'] == 'mismatch':
        unresolved.append(_item('higher_results_cgpa_mismatch', entered=f"{chk['cgpa_entered']:.2f}",
                                slip=f"{chk['cgpa_slip']:.2f}"))
    elif chk['cgpa_status'] == 'unreadable':
        unresolved.append(_item('higher_results_cgpa_unread'))
    if chk['missing']:
        unresolved.append(_item('higher_results_subjects_missing', subjects=', '.join(chk['missing'])))
    for m in chk['mismatched']:
        unresolved.append(_item('higher_results_grade_mismatch', **m))
    if not _scored(doc):     # S3: an STPM page is scored; the ladder says why when it is not genuine
        evidence.append(_item('higher_results_not_checked'))
    clean = (chk['name'] == 'match' and chk['readable'] and chk['kind_status'] == 'match'
             and chk['cgpa_status'] == 'match' and chk['grades_status'] in ('', 'match'))
    if spm_fact is not None and _latest_doc(application, 'results_slip') is not None:
        evidence += spm_fact['evidence']
        unresolved += spm_fact['unresolved']
        clean = clean and spm_fact['status'] == 'verified'
    return _fact('academic', 'verified' if clean else 'review', evidence, unresolved)


def _scored(doc) -> bool:
    """Does this upload carry a genuineness signal (STPM exact-read S3)? The same reading the ladder
    takes (`canonical_status`): a stored NOT CHECKED or no block at all is no signal."""
    from .genuineness.bands import canonical_status, stored_status
    return bool(canonical_status(stored_status(doc.vision_fields), 'higher_results'))


def red_chips(application) -> int:
    """RED academic chips for the higher card — Name, Kind (another kind / an SPM slip), Results
    (CGPA or STPM grades that differ). 0-3. Unread / cannot-tell are grey, never red."""
    from .verdict_engine import _latest_doc
    doc = _latest_doc(application, 'higher_results')
    if doc is None:
        return 0
    chk = student_higher_check(doc)
    return ((1 if chk['name'] == 'mismatch' else 0)
            + (1 if chk['kind_status'] in ('spm', 'different') else 0)
            + (1 if 'mismatch' in (chk['cgpa_status'], chk['grades_status']) or chk['missing'] else 0))
