"""Deterministic parse of the STANDARDISED government offer letters (STPM / Matrikulasi /
Polytechnic) from OCR text — the 'Exact read' path for offers, replacing the Gemini image read
for these fixed-format issuers.

Background: an earlier text-based offer parser (doc_parse P5) was retired 2026-06-18 because the
offer's 2-D label/value layout doesn't survive flattened OCR. This retry is narrower + issuer-aware:
the IDENTITY (name/NRIC) and PATHWAY/INTAKE sit on same lines or in the title (easy), and the
info-block fields are read by ONE shared block reader (`_read_block`, S5): every label's value is
taken by its SHAPE, in letter order, whatever the layout (label block then value block, label and
value interleaved, label and value glued on one line). CONSERVATIVE: returns None (→ Gemini) unless
it locks a coherent read incl. the fields the verdict needs. University (ua_offer) offers vary and
stay on Gemini. PISMP deferred (new format).

Output mirrors the Gemini offer schema fields read by pathway_engine.student_offer_check:
  candidate_name, candidate_nric, candidate_nric_source, programme, programme_code, institution,
  campus (always ''), stream, intake, reporting_date, reporting_date_label, offer_date, issuer.
Pure + deterministic; never raises. The IC guard and the merge over a prior read live in
`offer_exact` (S5) — the one entry point production and the eval call.
"""
from __future__ import annotations

import re

#: An IC is ASCII digits only (second review: a fullwidth or Arabic-Indic digit matched `\d` and locked
#: an IC). `_IC_END`: no further digit after the twelve, even one space / dash away ("080923-06-0355-1").
_IC = r'([0-9]{6}[- ]?[0-9]{2}[- ]?[0-9]{4})'
_IC_END = r'(?![ \t-]?\d)'
_NRIC_RE = re.compile(r'(?<!\d)(?<!\d[ \t-])' + _IC + _IC_END)
_MALAY_MONTH = (r'(?:JAN\w*|FEB\w*|MAC\w*|APR\w*|MEI|JUN\w*|JUL\w*|OGOS?|OKT\w*|NOV\w*|DIS\w*|'
                r'MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPT?\w*|OCTOBER|DECEMBER)')
_DMY_RE = re.compile(r'(\d{1,2}\s+' + _MALAY_MONTH + r'\s+20\d{2})', re.IGNORECASE)
_NUM_DATE_RE = re.compile(r'(?<!\d)(\d{1,2}[/-]\d{1,2}[/-]20\d{2})(?!\d)')
#: A day range ("8 HINGGA 9 JUN 2026", "13 MEI HINGGA 6 JUN 2026") — the reporting date is its FIRST
#: day (the answers' convention and `pathway_engine.parse_reporting_date`'s); 1.3.0 took the last.
#: ⚠ Every whitespace run in these patterns is BOUNDED ({0,3}) wherever two runs could meet: two
#: unbounded overlapping runs are polynomial backtracking on a long space run (review M1, 2026-11-03:
#: "SESI" + 2,000 spaces took 41 s). `tests/test_offer_parse_s5.py` times every family on such a run.
_RANGE_RE = re.compile(r'(\d{1,2})(?:\s{1,3}(' + _MALAY_MONTH + r'))?\s{0,3}(?:SE)?HINGGA\s{0,3}\d{1,2}\s{1,3}('
                       + _MALAY_MONTH + r')\s{1,3}(20\d{2})', re.IGNORECASE)
_NAME_MARKER = re.compile(r'\b(A\s*/\s*[LP]|BIN|BINTI)\b', re.IGNORECASE)
#: A person's name as these letters print it: letters, spaces and . ' @ / - only (no digit, no colon).
_NAME_SHAPE = re.compile(r"^[A-Za-z][A-Za-z .'’@/-]*[A-Za-z.]$")
#: Template words that can sit where a name is expected (a header line, a salutation) — never a name.
_NOT_NAME = re.compile(r'\b(MALAYSIA|PUTRAJAYA|KEMENTERIAN|PENDIDIKAN|BAHAGIAN|MATRIKULASI|POLITEKNIK|'
                       r'JABATAN|TARIKH|RUJUKAN|SAUDARA|SAUDARI|TUAN|PUAN|KAMI|NO|NAMA|KOLEJ|SEKOLAH|'
                       r'JALAN|TAMAN|KAMPUNG|LORONG|SURAT|TAWARAN|PROGRAM)\b', re.IGNORECASE)


def _decimal_digits(s: str) -> str:
    """Every ASCII digit 0-9 in `s`, in order. '' for a blank.

    ⚠ NOT `text.digits_only`, and not a candidate to become it. That one filters on
    `str.isdigit()`, which also admits superscripts and other digit-LIKE characters; this one keeps
    ASCII 0-9 only — not even `\\d`, which in Python also matches fullwidth and Arabic-Indic digits
    (S5 second review: such a digit locked an IC). The input here is raw OCR text on its way to becoming an
    NRIC, and the difference is not academic: a stray `³` in a scan would be KEPT by the other
    rule, could carry the string to twelve characters, and would be written onto an application
    as part of somebody's identity number. Dropping it is the only safe answer for this caller.

    Code health H7 merged the other two copies of `_digits` and deliberately left this one.
    """
    return re.sub(r'[^0-9]', '', s or '')


def _norm_nric(raw: str) -> str:
    d = _decimal_digits(raw)
    return f'{d[:6]}-{d[6:8]}-{d[8:12]}' if len(d) == 12 else ''


def _first_ic_anywhere(lines) -> str:
    m = _NRIC_RE.search('\n'.join(lines))
    return _norm_nric(m.group(1)) if m else ''


def first_date(s: str) -> str:
    """The date at the START of a value, as printed and DATE ONLY: a range's first day, else a
    'D Month YYYY', else a numeric date. A time window after it ("(8.30 PAGI - 11.30 TENGAHARI)",
    "8.00 PETANG") is never part of it (owner ruling 2026-11-03). '' when the value holds none."""
    s = s or ''
    rm = _RANGE_RE.search(s)
    if rm:
        return f'{rm.group(1)} {(rm.group(2) or rm.group(3)).upper()} {rm.group(4)}'
    m = _DMY_RE.search(s) or _NUM_DATE_RE.search(s)
    return m.group(1).strip() if m else ''


#: The issue date: a "Tarikh" that is NOT "Tarikh dan Masa Daftar" / "Tarikh Daftar" / "Tarikh Lapor
#: Diri" / "Tarikh Kemasukan…" / "Tarikh Cetakan" — i.e. "Tarikh" followed straight by a date (with
#: or without a colon), glued after the reference number too. 1.3.0 matched "Tarikh dan Masa Daftar"
#: and so read the polytechnic REGISTRATION date as the offer date (16 of 20 locks).
_OFFER_DATE_RE = re.compile(r'(?<![A-Za-z])Tarikh[ \t]{0,3}:?[ \t]{0,3}(?=\d)(.{6,30})', re.IGNORECASE)
_OFFER_DATE_ALONE = re.compile(r'^\s*Tarikh[ \t]{0,3}:?\s*$', re.IGNORECASE)


def _offer_date(lines):
    for i, ln in enumerate(lines):
        m = _OFFER_DATE_RE.search(ln)
        if m and first_date(m.group(1)):
            return first_date(m.group(1))
        if _OFFER_DATE_ALONE.match(ln):                         # "Tarikh:" / its date on the next line
            nxt = next((x.strip() for x in lines[i + 1:i + 3] if x.strip()), '')
            if first_date(nxt) and len(nxt) <= 20:
                return first_date(nxt)
    return ''


def _detect(up: str):
    if 'TINGKATAN ENAM' in up and ('SEKTOR OPERASI SEKOLAH' in up or 'KEMASUKAN KE TINGKATAN ENAM' in up):
        return 'stpm'
    if 'PROGRAM MATRIKULASI' in up or 'BAHAGIAN MATRIKULASI' in up:
        return 'matriculation'
    if 'POLITEKNIK' in up and ('JABATAN PENDIDIKAN POLITEKNIK' in up or 'SURAT TAWARAN PENGAJIAN' in up):
        return 'polytechnic'
    return ''


#: The OFFER's own title, per family — a lock requirement since 2.0.0, so a portal page, a slip or a
#: printout that names the family but is not the offer never locks (it goes to the AI reader).
#: Review M2: the title must START a line and be printed in CAPITALS (a portal page says "Tahniah! Anda
#: layak menerima Tawaran Kemasukan Program Matrikulasi" mid-sentence), and a page carrying a portal's
#: own words (`_PORTAL_TELL`) never locks. Checked on the glue-split lines (a glued layer's title follows
#: "Saudara," on one line).
_TITLE = {
    'stpm': re.compile(r'^[ \t]{0,8}TAWARAN\s{1,3}KEMASUKAN\s{1,3}KE\s{1,3}TINGKATAN\s{1,3}ENAM', re.M),
    'matriculation': re.compile(r'^[ \t]{0,8}(?:TAWARAN\s{1,3}KEMASUKAN\s{1,3}PROGRAM|'
                                r'KEPUTUSAN\s{1,3}PERTUKARAN\s{1,3}PROGRAM)', re.M),
    'polytechnic': re.compile(r'^[ \t]{0,8}SURAT\s{1,3}TAWARAN\s{1,3}PENGAJIAN', re.M),
}
#: Second review: also "Tahniah," / "TAHNIAH." + "anda ditawarkan" / "layak", a spaced or underscored
#: "S E M A K A N" / "Semakan_Keputusan", and wider whitespace. A real polytechnic letter's "Tahniah dan
#: sukacita dimaklumkan" is no tell.
#: "Semakan" alone is NOT a tell — a real polytechnic letter says it in its body ("skrin semakan"); the
#: portal's own phrases are (measured on the corpus, 2026-11-03).
_PORTAL_TELL = re.compile(r'(?<![A-Z])S[\s_]{1,2}E[\s_]{1,2}M[\s_]{1,2}A[\s_]{1,2}K[\s_]{1,2}A[\s_]{1,2}N(?![A-Z])|'
                          r'\bSEMAKAN[\s_]{1,3}(?:KEPUTUSAN|TAWARAN|STATUS|PANGGILAN)\b|'
                          r'\b(?:TARIKH|PORTAL)[\s_]{1,3}SEMAKAN\b|^[ \t]{0,8}SEMAKAN[ \t]{0,8}$|'
                          r'\bLAYAK\s{1,5}MENERIMA\b|\bSILA[\s_]{1,5}CETAK\b|\bTAHNIAH\s{0,3}!|'
                          r'\bTAHNIAH\s{0,3}[,.]\s{0,5}(?:ANDA\s{1,5})?(?:DITAWARKAN|LAYAK)\b', re.I | re.M)
#: Zero-width characters a pasted or exported page can hide inside a word (stripped before any match).
_ZERO_WIDTH = re.compile('[\u200b\u200c\u200d\ufeff]')


def _name_ok(name: str) -> bool:
    """A strict name shape: letters and . ' @ / - only, at least 3 letters, no template word. One word
    of more than 10 letters is two words the OCR glued together ("ABUBAKARSIDEK"), not a name to lock."""
    name = (name or '').strip()
    return (bool(_NAME_SHAPE.match(name)) and sum(c.isalpha() for c in name) >= 3
            and not _NOT_NAME.search(name) and (' ' in name or len(name) <= 10))


# ── The shared block reader ──────────────────────────────────────────────────────────────────
# ⚠ THE LABEL→VALUE PAIRING USED TO BE POSITIONAL, SO IT COULD SHIP BY ONE AND NOTHING OBJECTED.
# #125 (polytechnic) and #142 (matriculation) were the same fault: a zip of the labels to the value
# lines BY INDEX put the institution in the programme slot, a date in the Jurusan slot. Each was
# patched in one family's helper, and the same bug came back through the other door. Decision
# 2026-09-10 deferred a shifted block to Gemini and said: "revisit if the deferral rate climbs:
# per-label recovery written ONCE, shared". This is that reader (S5): ONE function for all three
# families, and every label's value must have the label's SHAPE (a date is a date, an institution
# starts "KOLEJ MATRIKULASI"…). The exit guards in `parse_govt_offer` stay as they were.
def _label(pattern):
    """A label at the start of a line, optionally numbered ("2.4."), its value (if any) after it. A
    value on the label's own line counts only after a colon or a clause number (so a body sentence
    that happens to start with the label word is never read as a value)."""
    return re.compile(r'^\s*(?P<num>\d+(?:\.\d+)*\.?\s*)?(?:' + pattern
                      + r')(?![A-Za-z])(?P<colon>[ \t]{0,5}:)?(?P<tail>.*)$', re.IGNORECASE)


#: More label lines than any offer's info block prints (the longest has 8).
MAX_BLOCK_LABELS = 40
_CLAUSE_ONLY = re.compile(r'^\s*\(?\d+(?:\.\d+)*\)?\.?\s*$')


def _hit(pat, ln):
    """The label match on a LABEL line: the label alone, or the label + colon / clause number + value.
    "KOLEJ MATRIKULASI PAHANG" is a value that starts with a label word, not the "Kolej:" label."""
    m = pat.match(ln)
    return m if m and (not m.group('tail').strip() or m.group('colon') or m.group('num')) else None


def _tokens(lines, spec, fillers=()):
    """The info block as a stream: ('L', key) for a label, ('V', text) for a value line. Starts at the
    first label; ends 12 lines after the last one. A bare clause number or a filler label is dropped."""
    first = last = None
    for i, ln in enumerate(lines):
        if any(_hit(pat, ln) for _k, pat, _s in spec) or any(_hit(f, ln) for f in fillers):
            first = i if first is None else first
            last = i
    if first is None:
        return []
    out = []
    for ln in lines[first:last + 13]:
        hit = next(((k, m) for k, pat, _s in spec for m in [_hit(pat, ln)] if m), None)
        if hit:
            key, m = hit
            out.append(('L', key))
            tail = m.group('tail').strip(' :').strip()
            if tail:
                out.append(('V', tail))
        elif any(_hit(f, ln) for f in fillers) or _CLAUSE_ONLY.match(ln) or not ln.strip():
            continue
        else:
            out.append(('V', re.sub(r'^\s*:\s*', '', ln).strip()))
    return out


#: One word that is never the end of a wrapped name: an address word or a state.
_NOT_WRAP = re.compile(r'^(?:JALAN|LORONG|TAMAN|KAMPUNG|KG|KM|BATU|PETI|PERSIARAN|LEBUH|LEBUHRAYA|BANDAR|'
                       r'PULAU|PERAK|SELANGOR|JOHOR|KEDAH|KELANTAN|TERENGGANU|PAHANG|MELAKA|PERLIS|SABAH|'
                       r'SARAWAK|LABUAN|PUTRAJAYA|MALAYSIA|NEGERI|SEMBILAN|PINANG)$')


def _wrapped(line, later):
    """True when ``line`` is the wrapped end of the value above it (a long school / programme name
    printed on two lines): ONE capitalised word, no digit, no address word or state, and not the
    shape of a later label's value."""
    w = (line or '').strip()
    return (bool(re.fullmatch(r"[A-Z][A-Z'’.-]+", w)) and not _NOT_WRAP.match(w)
            and not any(s(w) for s in later))


def _read_block(lines, spec, fillers=(), wraps=(), max_skip=8):
    """{key: value} by SHAPE, in letter order: for each label (as the letter orders them), the next
    value line after it that has the label's shape. A line with the shape of a LATER label means this
    label has no value (it stays ''); a line with no label's shape is skipped (an address line under
    an institution), at most `max_skip` of them. A key in ``wraps`` takes the next line too when
    that line is its wrapped end (`_wrapped`). A real block holds a handful of labels: past
    `MAX_BLOCK_LABELS` label lines it is not an offer's block and reads as nothing (second review: the
    scan was quadratic on "Program" x 8,000). Each label is tried once, and the scan only moves forward."""
    toks = _tokens(lines, spec, fillers)
    shape = {k: s for k, _p, s in spec}
    order = [(i, k) for i, (t, k) in enumerate(toks) if t == 'L']
    if len(order) > MAX_BLOCK_LABELS:
        return {}
    vals = [(i, v) for i, (t, v) in enumerate(toks) if t == 'V']
    out, cur, tried = {}, 0, set()
    for n, (pos, key) in enumerate(order):
        if key in tried:                        # a label printed twice is read once
            continue
        tried.add(key)
        later = [shape[k] for _p, k in order[n + 1:] if k != key]
        j = cur
        while j < len(vals) and vals[j][0] < pos:
            j += 1
        for j in range(j, min(len(vals), j + max_skip + 1)):
            v = vals[j][1]
            if shape[key](v):
                cur = j + 1
                if key in wraps and cur < len(vals) and vals[cur][0] == vals[j][0] + 1 \
                        and _wrapped(vals[cur][1], later):
                    v, cur = f'{v} {vals[cur][1].strip()}', cur + 1
                out[key] = v
                break
            if any(s(v) for s in later):        # the next label's value: this label has none
                break
    return out


def _date_shape(v):
    return bool(re.match(r'\s{0,3}\d{1,2}(?:\s{0,3}[/-]|\s{1,3}' + _MALAY_MONTH + r'|\s{0,3}(?:SE)?HINGGA)',
                         v or '', re.I)
                and first_date(v))


def _words_shape(*words):
    allowed = {w.upper() for w in words}
    return lambda v: bool(v) and len(v.split()) <= 3 and all(w.upper() in allowed for w in v.split())


_STREAM_SHAPE = _words_shape('SAINS', 'SOSIAL', 'PERAKAUNAN', 'KEJURUTERAAN', 'KOMPUTER', 'TEKNIKAL',
                             'SASTERA', 'HAYAT', 'FIZIKAL')


def _starts(pattern):
    rx = re.compile(r'^\s*(?:' + pattern + r')\b', re.IGNORECASE)
    return lambda v: bool(rx.match(v or ''))


def _has(pattern):
    rx = re.compile(pattern, re.IGNORECASE)
    return lambda v: bool(rx.search(v or ''))


def _split_glued(text: str, labels) -> str:
    """A glued text layer (the whole letter on one line, labels run into values) → one label per line:
    a line break goes in front of every known label that sits mid-line (class B, #117)."""
    for pat in labels:
        text = re.sub(r'(?<=\S)[ \t]{0,8}(?=' + pat + r')', '\n', text)
    return text


# The verdict-critical fields a lock REQUIRES (so switching off Gemini can't drop them). 2.0.0: the
# institution too, and STPM / matriculation need their stream (the scorer's programme for them, and
# the pathway check's track axis).
_REQUIRED = ('candidate_name', 'candidate_nric', 'programme', 'intake', 'institution')
_REQUIRED_STREAM = ('stpm', 'matriculation')

# Parser version — bump on ANY change to the deterministic capture (doc-recognition versioning
# rule) so re-runs are traceable. 1.1.0: poly slot-guard for the #125 block-misalignment.
# 1.2.0: reject a clause-number stream/institution/programme (#47) → defer to Gemini.
# 1.3.0 (2026-09-10) — the matriculation Jurusan is emitted as `stream` (its home per the Gemini
# schema) as well as inside `programme`, and a shifted label→value pairing now defers to Gemini
# instead of shipping a date as a jurusan.
# 2.0.0 (S5, 2026-11-03) — the output shape changes: one shared block reader by shape (classes A-E);
# `candidate_nric_source`, `programme_code` (the polytechnic code leaves `programme`), `campus` '';
# the intake keeps its words ("SEMESTER 1 TAHUN 2026", "SESI 2026/2027", "SESI I : 2026/2027"); a
# range's FIRST day; the offer date never the registration date; dates carry no time; the offer
# title is required; identity from page 1 (`page1_text`).
PARSER_VERSION = '2.0.0'
# A bare ringgit amount ("RM499.00") — the matriculation letter's "Yuran Pendaftaran" value, and a
# tell that the positional block pairing has shifted if it turns up in a text slot.
_MONEY_RE = re.compile(r'^RM\s*[\d,]+(?:\.\d{2})?$', re.IGNORECASE)
_SPACES = re.compile(r'[^\S\n]')


def _identity_of(identity, glue, text):
    name, nric, source = identity([ln.rstrip() for ln in _split_glued(text, glue).splitlines()])
    return (name if name and _name_ok(re.sub(r'\s+', ' ', name)) else ''), nric, source


def _disagree(a, b) -> bool:
    """Two identity reads of one letter that name another person: a different IC, or a different name."""
    (n1, i1), (n2, i2) = a, b
    return bool((i1 and i2 and _decimal_digits(i1) != _decimal_digits(i2))
                or (n1 and n2 and _name_letters(n1) != _name_letters(n2)))


def _name_letters(name: str) -> str:
    return re.sub(r'[^A-Z]', '', (name or '').upper())


def house_date(raw: str) -> str:
    """The reporting date in the house shape the AI path stores ("8 Jun 2031", English month abbreviations;
    `vision._normalise_reporting_date`) — review M4: `pathway_engine.parse_reporting_date` needs a month
    NAME, so a numeric "08/06/2031" stored as printed read as no date at all."""
    if not raw:
        return ''
    from .vision import _normalise_reporting_date
    return _normalise_reporting_date(raw)


def parse_govt_offer(text: str, page1_text: str = None):
    """STPM/Matrikulasi/Polytechnic offer OCR text → the offer field dict, or None to defer to
    Gemini. Conservative: None unless the issuer and the offer title are recognised AND every
    required field is read. ``page1_text`` (a digital PDF's page-1 text layer) is where the
    identity is read (owner rule 2026-11-01: only the offer page counts); default ``text``."""
    return diagnose(text, page1_text)['locked']


def diagnose(text: str, page1_text: str = None) -> dict:
    """The parser's whole walk, for `parse_govt_offer` and the eval (`offer_replay`): ``{family,
    titled, portal, fields (the read before the exit checks, or None), empty_required, guard, locked}``
    — ``locked`` is the lock (the field dict) or None.

    ``page1_text`` is a digital PDF's page-1 text layer, given ONLY when ``text`` is that PDF's own text
    layer (`offer_exact` decides — review H1). The identity is read from it, AND from ``text``: when the
    two disagree (another IC, another name) the letter does not lock (guard ``identity_disagree``)."""
    text = _SPACES.sub(' ', _ZERO_WIDTH.sub('', text or ''))   # no-break spaces as spaces; no zero-width
    page1_text = _SPACES.sub(' ', _ZERO_WIDTH.sub('', page1_text or ''))
    up = text.upper()
    fam = _detect(up)
    out = {'family': fam, 'titled': False, 'portal': bool(_PORTAL_TELL.search(text)), 'fields': None,
           'empty_required': [], 'guard': None, 'locked': None}
    if not fam:
        return out
    from .offer_parse_families import _FAMILY
    reader, identity, glue = _FAMILY[fam]
    split = _split_glued(text, glue)
    out['titled'] = bool(_TITLE[fam].search(split))
    if not out['titled'] or out['portal']:
        return out
    lines = [ln.rstrip() for ln in split.splitlines()]
    name, nric, source = _identity_of(identity, glue, page1_text if page1_text.strip() else text)
    fields = out['fields'] = {
        'candidate_name': name, 'candidate_nric': nric, 'candidate_nric_source': source if nric else 'none',
        'programme_code': '', 'campus': '', 'stream': '', **reader(lines, up), 'offer_date': _offer_date(lines)}
    fields['reporting_date'] = house_date(fields.get('reporting_date', ''))
    if page1_text.strip() and _disagree((name, nric), _identity_of(identity, glue, text)[:2]):
        out['guard'] = 'identity_disagree'
    required = _REQUIRED + (('stream',) if fam in _REQUIRED_STREAM else ())
    out['empty_required'] = [k for k in required if not (fields.get(k) or '').strip()]
    # A bare numbered-clause header leaked as a field value means the label-anchored layout read
    # went wrong (#47: the STPM section labels '2.4.'/'2.5.' latched as stream/institution). Don't
    # trust a corrupt deterministic read — defer the whole offer to Gemini (which reads the body
    # correctly). A bare N.N. token is NEVER a valid stream / institution / programme.
    from .card_display import looks_like_clause_number, looks_like_date
    slots = ('stream', 'institution', 'programme')
    if out['guard']:
        pass
    elif any(looks_like_clause_number(fields.get(k, '')) for k in slots):
        out['guard'] = 'clause_number'
    # ⚠⚠ THE #125 / #142 FAULT HAPPENED TWICE BECAUSE THE FIRST FIX WAS SCOPED TO ONE PARSER. A DATE
    # or a RINGGIT AMOUNT is never a stream, an institution or a programme; seeing one means the
    # block read went wrong, and a partly-wrong deterministic read is worth less than no
    # deterministic read: defer the whole offer to Gemini. THIS guard is at the single exit point and
    # covers ALL THREE families; do not move it back into a per-family helper (lesson #125 / #142).
    elif any(looks_like_date(fields.get(k, '')) or _MONEY_RE.match((fields.get(k, '') or '').strip())
             for k in slots):
        out['guard'] = 'date_or_money'
    if not out['empty_required'] and not out['guard']:
        out['locked'] = {**fields, '_family': fam, '_offer_parser_version': PARSER_VERSION}
    return out
