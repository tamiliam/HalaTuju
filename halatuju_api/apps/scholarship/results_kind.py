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

Pure: text in, a code out. The OCR text comes from the upload's one Vision read; when there is none
the Gemini read's own `exam` title is used instead (`detect_from_fields`).
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


def detect(text):
    """The kind of results ``text`` is, or '' when we cannot tell.

    Exactly ONE tertiary kind printed → that kind. Two or more → '' (it points two ways). None, and
    an SPM marker with no CGPA label → 'spm' (an SPM slip prints grades, never a CGPA). Anything
    else → ''."""
    seen = kinds_seen(text)
    higher = [k for k in seen if k != 'spm']
    if len(higher) == 1:
        return higher[0]
    if higher:
        return ''
    if 'spm' in seen and not _has(_CGPA, (text or '').upper()):
        return 'spm'
    return ''


def detect_from_fields(fields):
    """The same answer from a Gemini read's ``exam`` title (and qualification, if read) — the
    fallback when the upload carried no OCR text. '' when there is nothing to read."""
    if not isinstance(fields, dict):
        return ''
    title = ' '.join(str(fields.get(k) or '') for k in ('exam', 'qualification'))
    return detect(title)
