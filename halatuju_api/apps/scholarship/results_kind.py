"""Which results a document IS — STPM / Matriculation / Asasi / Diploma / SPM — read from fixed
printed markers. Third results route S3b (2026-10-26; roadmap §5 S3, rulings D8 D13).

⚠ ROUTING ONLY. This answers "what kind of results slip is this?" so the Documents page can say
"This appears to be Matriculation results, but your application shows STPM" and the reviewer's
Academic card can say the same. It SCORES NOTHING: no genuineness, no probability, no band. That is
why it lives here and not in `genuineness/results_doc.py` (whose every change is a `MODEL_VERSION`
bump under the house rule) and why it reuses nothing from that file (`misfiled_as` /
`_MISFILE_FAMILIES` are a scorer's, and reusing them would make this a scorer change too).

⚠ "CANNOT TELL" IS NEVER A DISAGREEMENT. A note to a student is only worth showing when we are
sure, so the answer is '' whenever the markers are absent OR point two ways (a transcript naming
both "Asasi" and "Diploma", an STPM slip that also says "Matrikulasi" in a footer). Every reader
treats '' as "nothing to say" — never as a mismatch.

⚠ ONE READER GATES ON IT: `genuineness/stpm_doc.py` scores a higher-results page only when
`detect(ocr) == 'stpm'`. So a change here must never move an 'stpm' answer, or it is a genuineness
change (`MODEL_VERSION`). The issuer tier below (Matric/Diploma M1, 2026-10-29) cannot: it answers
only where no kind marker is printed, and never 'stpm'.

Pure: text in, a code out. The OCR text comes from the upload's one Vision read; when there is none
the Gemini read's own title, institution and subject rows are used instead (`detect_from_fields`).
"""
import re

#: The kinds this module can answer, in the vocabulary of `exam_questions.QUALIFICATIONS`.
KINDS = ('stpm', 'matric', 'asasi', 'diploma', 'spm')

# Fixed markers per kind, matched as whole words on the upper-cased text. Plain strings, never a
# model: each is a phrase the issuing body prints on its own results document.
_MARKERS = {
    # STPM — Majlis Peperiksaan Malaysia prints the certificate title in both languages. MPM also
    # issues MUET slips, so "MAJLIS PEPERIKSAAN MALAYSIA" counts only when MUET is not the subject.
    'stpm': (r'SIJIL\s+TINGGI\s+PERSEKOLAHAN\s+MALAYSIA', r'MALAYSIA\s+HIGHER\s+SCHOOL\s+CERTIFICATE',
             r'STPM'),
    'matric': (r'PROGRAM\s+MATRIKULASI', r'MATRIKULASI', r'MATRICULATION'),
    'asasi': (r'ASASI', r'FOUNDATION', r'ASASIPINTAR'),
    'diploma': (r'DIPLOMA',),
    # SPM — Lembaga Peperiksaan prints "SIJIL PELAJARAN MALAYSIA"; the STPM title above does not
    # contain that phrase ("SIJIL TINGGI PERSEKOLAHAN"), so the two cannot be confused.
    'spm': (r'SIJIL\s+PELAJARAN\s+MALAYSIA', r'MALAYSIAN\s+CERTIFICATE\s+OF\s+EDUCATION', r'SPM'),
}
#: Fixed ISSUER markers (Matric/Diploma M1, 2026-10-29): a body that issues one kind of results here
#: prints its own name on the transcript whatever the title says ("ACADEMIC TRANSCRIPT"). Read ONLY
#: when no kind marker is printed, no SPM marker either, AND the page reads as a RESULT (`_RESULT`: a
#: grade label or result wording printed; from a stored read, subject rows or a CGPA) — so an offer or enrolment letter naming a
#: polytechnic says nothing. Every page the kind markers answer reads exactly as before — an STPM
#: page above all, whose genuineness gate is `detect(...) == 'stpm'` (`genuineness/stpm_doc.py`): an
#: issuer never answers 'stpm'. Calibrated on the corpus OCR: "POLITEKNIK" / "POLYTECHNIC" on 3 of
#: the 4 polytechnic documents (the fourth, a student-portal screenshot, prints neither) and on 0 of
#: 151 STPM / SPM slips and certificates (results_split + the results_slip corpus). The department
#: "Jabatan Pendidikan Politeknik dan Kolej Komuniti" (JPPKK) also heads Kolej Komuniti papers, so it
#: is not a polytechnic marker (`_NOT_ISSUERS`). The Matriculation college matters only in a stored
#: read's `institution` (on the page its name already holds the kind word MATRIKULASI).
_ISSUERS = {'diploma': (r'POLITEKNIK', r'POLYTECHNIC'),
            'matric': (r'KOLEJ\s+MATRIKULASI', r'MATRICULATION\s+COLLEGE')}
_NOT_ISSUERS = re.compile(r'POLITEKNIK\s+DAN\s+KOLEJ\s+KOMUNITI|POLYTECHNICS?\s+AND\s+COMMUNITY\s+COLLEGES?')
#: The compulsory subject a Matriculation transcript prints (corpus OCR: 8 of 9 Matriculation pages,
#: no other document of any kind). Read from a stored read's SUBJECT rows only — the SPM card's
#: read keeps no institution, so this is all an "ACADEMIC TRANSCRIPT" there carries (BrightPath
#: #49). Same tier as the issuers. Rows are joined with " | " so a pattern never spans two rows.
_FIXED_SUBJECTS = {'matric': (r'PENGAJIAN\s+AM\s+MATRIKULASI', r'MATRICULATION\s+GENERAL\s+STUDIES')}
_MPM = r'MAJLIS\s+PEPERIKSAAN\s+MALAYSIA'
_MUET = r'MUET|MALAYSIAN\s+UNIVERSITY\s+ENGLISH\s+TEST'
#: A cumulative grade point average — printed on every tertiary result, never on an SPM slip.
_CGPA = r'PNGK|CGPA|PURATA\s+NILAI\s+GRED\s+KUMULATIF|CUMULATIVE\s+GRADE\s+POINT'
#: The issuer tier's "this page is a result" gate — a cumulative OR a semester grade label, or result
#: wording. NOT a CGPA alone (owner, 2026-10-29): a transcript may print its final CGPA on the LAST
#: page, and production OCRs only page 1 of a scanned PDF. Calibrated on page 1 of the corpus: every
#: one of the 17 Matriculation / Diploma pages carries one of these; none of the 39 offer letters
#: naming a polytechnic, Matriculation college or Kolej Komuniti does (bare "SEMESTER" is on 38 of
#: them, so it is not here). HPNM / NILAI MATA are the polytechnic's own labels. Kept apart from
#: `_CGPA`, so the SPM rule reads exactly as before.
_RESULT = _CGPA + (r'|HPNM|HIMPUNAN\s+PURATA\s+NILAI\s+MATA|NILAI\s+MATA|GPA|PNG|PURATA\s+NILAI\s+GRED'
                   r'|GRADE\s+POINT\s+AVERAGE|KEPUTUSAN\s+(?:PEPERIKSAAN|SEMESTER)|SEMESTER\s+RESULTS?'
                   r'|EXAMINATION\s+RESULTS?|RESULT\s+SLIP|TRANSCRIPT|TRANSKRIP')


def _has(pattern, text):
    return re.search(rf'(?<![A-Z]){pattern}(?![A-Z])', text) is not None


def kinds_seen(text):
    """Every kind whose marker is printed in ``text`` (upper-cased), lowest first. For the audit
    trail stored beside the answer, so a reviewer can see WHY a document read as it did."""
    up = (text or '').upper()
    seen = [k for k in KINDS if any(_has(p, up) for p in _MARKERS[k])]
    if 'stpm' not in seen and _has(_MPM, up) and not _has(_MUET, up):
        seen.insert(0, 'stpm')
    return seen


def _by_issuer(issuer_up, subjects):
    """(kind, marker) for the ONE kind a fixed issuer marker (in ``issuer_up``) or fixed subject (in
    the subject rows) points to — ('', '') for none or two. ``marker`` is the pattern that decided,
    for the audit trail."""
    issuer_up = _NOT_ISSUERS.sub(' ', issuer_up)
    rows_up = ' | '.join(str(s or '') for s in subjects).upper()
    hits = {}
    for table, hay in ((_ISSUERS, issuer_up), (_FIXED_SUBJECTS, rows_up)):
        for k, ps in table.items():
            p = next((p for p in ps if _has(p, hay)), None)
            if p and k not in hits:
                hits[k] = p
    if len(hits) != 1:
        return '', ''
    (kind, pattern), = hits.items()
    return kind, re.sub(r'\\s\+', ' ', pattern)


def _detect(text, *, issuer_text='', subjects=(), is_result=None):
    """(kind, issuer marker) — `detect`'s answer and, when the issuer tier gave it, what decided."""
    seen = kinds_seen(text)
    higher = [k for k in seen if k != 'spm']
    if len(higher) == 1:
        return higher[0], ''
    if higher:
        return '', ''
    up = (text or '').upper()
    if 'spm' not in seen:
        result = _has(_RESULT, up) if is_result is None else is_result
        return _by_issuer(f'{up} | {(issuer_text or "").upper()}', subjects) if result else ('', '')
    return ('spm' if not _has(_CGPA, up) else ''), ''


def detect(text):
    """The kind of results ``text`` is, or '' when we cannot tell.

    Exactly ONE tertiary kind printed → that kind. Two or more → '' (it points two ways). None, no
    SPM marker and the page reads as a result (`_RESULT`) → the one kind a fixed issuer points to (M1). None, and an
    SPM marker with no CGPA label → 'spm' (an SPM slip prints grades, never a CGPA). Else ''."""
    return _detect(text)[0]


def _fields_args(fields):
    """The stored read split the way the tiers read it: the KIND tier sees only the title and
    qualification (an institution like "MAJLIS PEPERIKSAAN MALAYSIA" or "… FOUNDATION …" is no
    title); the institution and the subject rows feed the issuer tier alone."""
    title = ' '.join(str(fields.get(k) or '') for k in ('exam', 'qualification'))
    rows = fields.get('results') if isinstance(fields.get('results'), list) else []
    subjects = [r.get('subject') for r in rows if isinstance(r, dict)]
    is_result = bool(subjects) or bool(str(fields.get('cgpa') or '').strip())
    return title, {'issuer_text': str(fields.get('institution') or ''), 'subjects': subjects,
                   'is_result': is_result}


def detect_from_fields(fields):
    """The same answer from a Gemini read: its ``exam`` title and qualification for the kind
    markers; its institution (M1: an "ACADEMIC TRANSCRIPT" names its college there) and subject
    rows for the issuer tier, on a read that holds a result (rows or a CGPA). The fallback when the
    upload carried no OCR text, and the SPM card's witness (`wrong_slip.higher_kind`)."""
    if not isinstance(fields, dict):
        return ''
    title, kw = _fields_args(fields)
    return _detect(title, **kw)[0]


def detection(text, fields):
    """(kind, issuer marker) for an upload: the OCR text first, else the stored read — the pair
    `higher_results.extract` stores (`results_kind_detected`, `results_kind_issuer`)."""
    kind, marker = _detect(text)
    if kind or not isinstance(fields, dict):
        return kind, marker
    title, kw = _fields_args(fields)
    return _detect(title, **kw)
