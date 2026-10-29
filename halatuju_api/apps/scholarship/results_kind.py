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
#: when no kind marker above is printed and no SPM marker either, so every page the kind markers
#: answer today reads exactly as before — an STPM page above all, whose genuineness gate is
#: `detect(...) == 'stpm'` (`genuineness/stpm_doc.py`): an issuer never answers 'stpm'. Calibrated on
#: the corpus OCR: "POLITEKNIK" / "POLYTECHNIC" on 3 of the 4 polytechnic documents (the fourth, a
#: student-portal screenshot, prints neither) and on 0 of 151 STPM / SPM slips and certificates
#: (results_split + the results_slip corpus). JPPKK is on no transcript, so it is not a marker.
#: Matriculation needs none: its college prints "KOLEJ MATRIKULASI" / "MATRICULATION COLLEGE",
#: which the kind markers already catch.
_ISSUERS = {'diploma': (r'POLITEKNIK', r'POLYTECHNIC')}
#: The compulsory subject a Matriculation transcript prints (corpus OCR: 8 of 9 Matriculation pages,
#: no other document of any kind). Read from a stored read's SUBJECT rows only — the SPM card's
#: read keeps no institution, so this is all an "ACADEMIC TRANSCRIPT" there carries (BrightPath
#: #49). Same tier as the issuers.
_FIXED_SUBJECTS = {'matric': (r'PENGAJIAN\s+AM\s+MATRIKULASI', r'MATRICULATION\s+GENERAL\s+STUDIES')}
_MPM = r'MAJLIS\s+PEPERIKSAAN\s+MALAYSIA'
_MUET = r'MUET|MALAYSIAN\s+UNIVERSITY\s+ENGLISH\s+TEST'
#: A cumulative grade point average — printed on every tertiary result, never on an SPM slip.
_CGPA = r'PNGK|CGPA|PURATA\s+NILAI\s+GRED\s+KUMULATIF|CUMULATIVE\s+GRADE\s+POINT'


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


def _by_issuer(up, subjects_up):
    """The ONE kind a fixed issuer marker (in the text) or fixed subject (in the subject rows)
    points to, or '' (none, or two)."""
    kinds = {k for k, ps in _ISSUERS.items() if any(_has(p, up) for p in ps)}
    kinds |= {k for k, ps in _FIXED_SUBJECTS.items() if any(_has(p, subjects_up) for p in ps)}
    return kinds.pop() if len(kinds) == 1 else ''


def detect(text, subjects=()):
    """The kind of results ``text`` is, or '' when we cannot tell. ``subjects``: a stored read's
    subject names, for the fixed-subject tier (`detect_from_fields`); OCR text passes none.

    Exactly ONE tertiary kind printed → that kind. Two or more → '' (it points two ways). None, and
    no SPM marker → the one kind a fixed issuer / subject points to (M1). None, and an SPM marker
    with no CGPA label → 'spm' (an SPM slip prints grades, never a CGPA). Anything else → ''."""
    seen = kinds_seen(text)
    higher = [k for k in seen if k != 'spm']
    if len(higher) == 1:
        return higher[0]
    if higher:
        return ''
    up = (text or '').upper()
    if 'spm' not in seen:
        return _by_issuer(up, ' \n '.join(str(s or '') for s in subjects).upper())
    if not _has(_CGPA, up):
        return 'spm'
    return ''


def detect_from_fields(fields):
    """The same answer from a Gemini read — its ``exam`` title, qualification and institution
    (M1: an "ACADEMIC TRANSCRIPT" names its college there), and its subject rows for the fixed
    subject tier only. The fallback when the upload carried no OCR text, and the SPM card's witness
    (`wrong_slip.higher_kind`). '' when there is nothing to read."""
    if not isinstance(fields, dict):
        return ''
    title = ' '.join(str(fields.get(k) or '') for k in ('exam', 'qualification', 'institution'))
    rows = fields.get('results') if isinstance(fields.get('results'), list) else []
    return detect(title, [r.get('subject') for r in rows if isinstance(r, dict)])
