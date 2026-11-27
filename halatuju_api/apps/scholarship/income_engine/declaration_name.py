"""Case 1048 (owner 2026-11-27): a HANDWRITTEN income declaration in the salary-slip slot.

A "Surat Akuan Pengesahan Pendapatan" is filled in by hand and uploaded where a payslip goes. Two
things went wrong on it, and this module holds the fix for both.

**1. A near-miss name is 'close', not red.** The AI misreads a handwritten name by a letter or two
(and often reads the "A/L" as a short stray word such as "ALE"), so the earner's own form failed the
tolerant matcher (`vision._tokens_close`: five letters or more, one edit) and the Name chip went red
as if the form named a stranger. The owner ruled:

* a near miss on a declaration SHOWS its own word, ``CLOSE`` (amber: a person must look);
* review round 1 (owner rule): 'close' must NEVER count as clean or ok anywhere. So it is a DISPLAY word
  only. ``soften`` is called by `link_display.income_proof_display` alone, on ``display_name_status``.
  The decision field ``student_income_proof_check()['name_status']`` stays 'mismatch', so every gate,
  resolution, promotion, income-satisfaction, verdict band, route switch, coach and blocker treats the
  form exactly as before (``for_decisions`` is the mapping for any future caller that holds a shown
  word). The stored student verdict is not changed either: it stays 'name_mismatch';
* the matcher is NOT loosened anywhere else. A typed or printed payslip one letter off still says
  'mismatch'. The change is scoped to a salary-slip-slot document the read saw as a declaration
  (``income_declaration.is_declaration``: ``doc_seen == 'declaration'``), which is our only proxy for
  "handwritten" — no stored handwriting flag exists.

The near miss is deliberately narrow. First the patronymic connectors drop out on BOTH sides (A/L,
A/P, S/O, D/O, BIN, BINTI, BT as `vision._canonical_name_seq` already drops them, plus BN). Then:

* **same number of parts** (two or more): every part agrees under the tolerant matcher but at most ONE,
  and that odd pair is at least ``MIN_PART_LETTERS`` long on both sides, shares its first letter and is
  at most ``MAX_EDITS`` apart (no odd pair at all — an exact match once the connectors are gone — is a
  near miss too);
* **one part more on one side**: that extra part is the ONLY inner part (never the first or the last
  word) of at most ``MAX_EXTRA_LETTERS`` letters that is within one edit of a connector (ALE, AIL, NL
  for A/L). It drops, and the rest must agree IN PRINTED ORDER, with at most one odd pair as above.
  Two extra parts, or an extra part that is not connector-like, are never close.

A reversed patronymic (a father and a son) is never close. A different given name is still 'mismatch'.
Review round 1: opposite-sex connectors (A/L or S/O or BIN against A/P or D/O or BINTI/BT) are never
close, even though both drop out of the comparison; a misread connector counts as the one sex it is
within one edit of (ALE, AIL, NL are A/L). Review round 2: the slash-less exact forms (SO, AL, BN male;
DO, AP, BT, BNT female) and a connector glued on both sides ("KUMARANA/PRAJAN") carry their sex too; a
misread word one edit from BOTH sexes (ALP, BO) facing a clear sex is never close; and "AH" (a real
Chinese name part) never drops as a misread connector.

**2. The payslip-only warnings do not show on a declaration.** The read's free-text ``warnings`` (the
AI's notes, stored at read time and shown to the officer) say "no employer" and "no pay period" on
almost every declaration — a declaration has neither, by design. ``shown_warnings`` hides exactly those
two kinds at DISPLAY time (the serializer); the stored read is never edited, and no warning feeds a
verdict, a blocker or the money. Review round 2: the rule is "NOTHING LEFT OVER". The warning splits on
; , . and the words "and" / "dan"; a part is hideable only when, after its employer or pay-period words,
its absence words and its filler words are taken out, nothing is left ("employer not stated", "tiada
majikan", "tempoh gaji tidak dinyatakan"). Every part must be hideable. Anything about tampering, forgery,
a chop, stamp, signature, endorsement, the penghulu, a correction, the applicant, a name or an IC/KP keeps
the whole warning; so does any left-over word ("figure crossed out", "tiada tarikh": a missing DATE is
not payslip-only). When unsure, the warning is kept.

**3. 'close' is not served yet.** ``SHOW_CLOSE`` (below) is False until NRIC chip Sprint 3 gives the web
an amber pill for it; until then ``soften`` changes nothing and the API shows 'mismatch' as before.

It sits in ``income_engine/`` so the verdict-engine fingerprint covers it: BUMP
``verdict_engine.VERDICT_ENGINE_VERSION`` on any change to the rule.
"""
from __future__ import annotations

import re

#: The SHOWN status word (``display_name_status`` only). Never a decision value.
CLOSE = 'close'

#: Review round 2 (owner rule): the API must not SERVE 'close' until the web can draw it. Today the web
#: turns an unknown word into 'unknown' and the officer drawer then shows a green "verified", so while this
#: is False ``soften`` returns every status unchanged and ``display_name_status`` is exactly what it was
#: before case 1048 ('mismatch'). NRIC chip Sprint 3 (the web amber pill and label for 'close') is the
#: change that turns it on — in code, here, never from an env var. ``shown_warnings`` does not read it.
SHOW_CLOSE = False


def for_decisions(status: str) -> str:
    """The decision value of a name status: 'close' is 'mismatch' for every gate and decision (owner
    rule, review round 1). Every other status is returned unchanged."""
    return 'mismatch' if status == CLOSE else status

MIN_PART_LETTERS = 4
MAX_EDITS = 2

#: The connector forms an extra short part may be one edit from (A/L and A/P lose their slash).
CONNECTORS = ('al', 'ap', 'so', 'do', 'bin', 'binti', 'bt', 'bn')
#: `_canonical_name_seq` keeps BN (it is not in `vision._NAME_NOISE`); it is a connector here.
_ALSO_DROPPED = frozenset({'bn'})
MAX_EXTRA_LETTERS = 3


def _parts(name: str) -> list:
    from ..vision import _canonical_name_seq
    return [t for t in _canonical_name_seq(name or '') if t not in _ALSO_DROPPED]


def _one_part_off(x: str, y: str) -> bool:
    from ..vision import _fold_name_token, _levenshtein
    x, y = _fold_name_token(x), _fold_name_token(y)
    return min(len(x), len(y)) >= MIN_PART_LETTERS and x[:1] == y[:1] and _levenshtein(x, y) <= MAX_EDITS


def _same_count(a: list, b: list) -> bool:
    """The rule for two names of the same number of parts (matched in any order, as before)."""
    from ..vision import _tokens_close
    if len(a) < 2:
        return False
    rest, odd = list(b), []
    for x in a:
        hit = next((i for i, y in enumerate(rest) if _tokens_close(x, y)), None)
        if hit is None:
            odd.append(x)
        else:
            rest.pop(hit)
    if not odd:
        return True                                   # exact once the connectors are gone
    return len(odd) == 1 and len(rest) == 1 and _one_part_off(odd[0], rest[0])


#: Review round 2: short REAL name parts that are one edit from a connector but are never a misread one.
#: AH is a Chinese name part ("TAN AH SENG" is not "TAN SENG"), so it never drops.
_NEVER_DROPPED = frozenset({'ah'})


def _connector_like(tok: str) -> bool:
    from ..vision import _levenshtein
    return (tok not in _NEVER_DROPPED and len(tok) <= MAX_EXTRA_LETTERS
            and any(_levenshtein(tok, c) <= 1 for c in CONNECTORS))


def _without_misread_connector(longer: list):
    """``(longer without its ONE connector-like inner part, that part)``, or ``(None, '')`` when there is
    not exactly one."""
    hits = [i for i in range(1, len(longer) - 1) if _connector_like(longer[i])]
    if len(hits) != 1:
        return None, ''
    return longer[:hits[0]] + longer[hits[0] + 1:], longer[hits[0]]


#: Review round 1 (should-fix 4): the connectors carry a sex. A son (A/L, S/O, BIN) is never 'close' to a
#: daughter (A/P, D/O, BINTI), even though both connectors drop out of the comparison. Review round 2: the
#: slash-less EXACT forms carry their sex too (SO, AL, BN are male; DO, AP, BT, BNT are female), and they
#: are read BEFORE any misread logic, so an exact SO is never "one edit from DO".
_MALE = frozenset({'a/l', 'al', 's/o', 'so', 'bin', 'bn'})
_FEMALE = frozenset({'a/p', 'ap', 'd/o', 'do', 'binti', 'bt', 'bte', 'bnt'})
#: A slash connector glued on BOTH sides ("KUMARANA/PRAJAN"), which `vision._split_glued_markers` (one
#: side only) leaves whole. Slash forms only, as there: a '/' never occurs inside a real name.
_GLUED_BOTH_SIDES = re.compile(r'([a-z])(a/[lp]|[ds]/o)([a-z])')


def _gender_signs(name: str) -> set:
    """'m' and/or 'f' for each connector the name prints (slash spacing and glue tidied first)."""
    from ..vision import _split_glued_markers
    tidy = re.sub(r'\s*/\s*', '/', str(name or '').lower())
    tidy = _split_glued_markers(_GLUED_BOTH_SIDES.sub(r'\1 \2 \3', tidy))
    signs = set()
    for tok in re.findall(r'[a-z]+(?:/[a-z]+)?', tidy):
        if tok in _MALE:
            signs.add('m')
        elif tok in _FEMALE:
            signs.add('f')
    return signs


def _misread_sign(tok: str) -> set:
    """The sex of the dropped short word: an exact slash-less form first (SO is male, DO female); else
    every sex whose connectors it is within one edit of — {'m'} for ALE, AIL, NL; {'m', 'f'} for a word
    near BOTH (ALP, APL, BO); empty when near neither."""
    from ..vision import _levenshtein
    plain = (('m', {f.replace('/', '') for f in _MALE}), ('f', {f.replace('/', '') for f in _FEMALE}))
    exact = {sex for sex, forms in plain if tok in forms}
    if exact:
        return exact
    return {sex for sex, forms in plain if any(_levenshtein(tok, f) <= 1 for f in forms)}


def _opposite_sex(sa: set, sb: set) -> bool:
    return bool(sa) and bool(sb) and sa.isdisjoint(sb)


def _in_order(a: list, b: list) -> bool:
    """Part by part in printed order: all agree, or exactly one odd pair within the near-miss limits."""
    from ..vision import _tokens_close
    if len(a) != len(b) or len(a) < 2:
        return False
    odd = [(x, y) for x, y in zip(a, b) if not _tokens_close(x, y)]
    return not odd or (len(odd) == 1 and _one_part_off(*odd[0]))


def near_miss(extracted, reference) -> bool:
    """True when the two names differ only by a small misread (the rule above)."""
    from .buckets import _near_miss_reversal
    a, b = _parts(extracted), _parts(reference)
    if _near_miss_reversal(extracted, reference):
        return False
    sa, sb = _gender_signs(extracted), _gender_signs(reference)
    if _opposite_sex(sa, sb):
        return False                                  # A/L against A/P, S/O against D/O, BIN against BINTI
    if len(a) == len(b):
        return _same_count(a, b)
    if abs(len(a) - len(b)) != 1:
        return False
    if len(a) < len(b):
        a, b, sa, sb = b, a, sb, sa                   # `a` is the side with the extra word
    a, dropped = _without_misread_connector(a)
    if a is None:
        return False
    sex = _misread_sign(dropped)
    if len(sex) > 1 and sb:
        return False                                  # ALP / BO (near both sexes) against a clear A/L or A/P
    if _opposite_sex(sa | sex, sb):
        return False                                  # a misread A/L against a printed A/P
    return _in_order(a, b)


def soften(doc, status: str, extracted: str, reference: str) -> str:
    """The SHOWN name status: ``CLOSE`` in place of 'mismatch' for a near-miss name on a declaration in
    the salary-slip slot; every other status, document type or name is returned unchanged. DISPLAY
    ONLY (`link_display.income_proof_display`): never call it on a decision field. While ``SHOW_CLOSE`` is
    False it returns ``status`` unchanged for every document."""
    if not SHOW_CLOSE or status != 'mismatch' or getattr(doc, 'doc_type', '') != 'salary_slip':
        return status
    if not near_miss(extracted, reference):
        return status
    from ..income_declaration import is_declaration
    return CLOSE if is_declaration(doc) else status


# ── 2. The payslip-only warnings ─────────────────────────────────────────────────────────────────
#: Review round 2: the rule is "NOTHING LEFT OVER". A warning splits into parts on ; , . and the whole words
#: "and" / "dan". A part is hideable only when it names the employer or the pay period (a TOPIC), says it is
#: ABSENT, and nothing else is left once the topic, the absence and the FILLER words are taken out. The
#: whole warning hides only when every part is hideable. When unsure, the warning is kept.
#:
#: The topics. A DATE is not one: a declaration should carry a date, so "date missing" is never hidden.
_TOPICS = (
    # the employer
    'name of the employer', 'name of employer', "employer's name", 'employers name', 'employer name',
    'name of the company', 'name of company', "company's name", 'company name', 'nama majikan',
    'nama syarikat', 'employers', 'employer', 'majikan', 'company', 'syarikat',
    # the pay period
    'pay slip period', 'payslip period', 'pay period', 'salary period', 'income period', 'period of pay',
    'period of salary', 'period of income', 'period', 'month/year of salary', 'month/year of pay',
    'month/year of income', 'month/year', 'pay month', 'salary month', 'income month', 'month of pay',
    'month of salary', 'month of income', 'tempoh gaji', 'tempoh pendapatan', 'tempoh', 'bulan gaji',
    'bulan pendapatan', 'bulan/tahun',
)
#: The ABSENCE words (English and Malay). A bare "not" is NOT one ("employer is not a company" stays).
_ABSENCES = (
    'not stated', 'not given', 'not shown', 'not provided', 'not specified', 'not indicated', 'not listed',
    'not mentioned', 'not included', 'not present', 'not recorded', 'not written', 'not filled in',
    'not filled', 'not found', 'not visible', 'not available', 'not declared', 'missing', 'absent', 'none',
    'no', 'n/a', 'nil', 'blank', 'omitted', 'unspecified', 'unstated', 'without', 'lack', 'lacks', 'lacking',
    'tiada', 'tidak dinyatakan', 'tidak dicatat', 'tidak dicatatkan', 'tidak tercatat', 'tidak ditulis',
    'tidak diisi', 'tidak ada', 'tidak disertakan', 'kosong', 'tanpa',
)
#: The FILLER words that may stand beside a topic and an absence and say nothing of their own.
_FILLER = frozenset({
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'has', 'have', 'on', 'in', 'of', 'this',
    'any', 'slip', 'payslip', 'document', 'form', 'declaration', 'stated', 'shown', 'given', 'provided',
    'specified', 'indicated', 'mentioned', 'listed', 'recorded', 'pada', 'di', 'dalam', 'ini', 'yang',
    'telah', 'dinyatakan',
})


def _phrases(words) -> re.Pattern:
    alts = '|'.join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<![a-z0-9/'])(?:{alts})(?![a-z0-9/'])")


_TOPIC_RE = _phrases(_TOPICS)
_ABSENT_RE = _phrases(_ABSENCES)
#: Any of these anywhere in the warning keeps it whole, whatever else it says (substring: the safe
#: direction, so "signed", "menandatangani", "forged", "diubah", "unendorsed" all count).
_KEEP_STEMS = ('tamper', 'alter', 'forg', 'fake', 'palsu', 'ubah', 'chop', 'stamp', 'sign', 'tandatangan',
               'endorse', 'penghulu', 'overwrit', 'written over', 'correction', 'fluid', 'applicant',
               'pemohon', 'themselves', 'himself', 'herself', 'sendiri', 'name', 'nama', 'nric', 'mykad',
               'identity', 'pengenalan', 'approv', 'lulus', 'sah', 'cert', 'witness', 'saksi', 'suspicious',
               'mencurigakan', 'inconsistent', 'differ', 'berbeza', 'mismatch', 'relative', 'saudara')
#: ...and these as whole words (too short to match inside other words): IC, I/C, I.C., KP, K/P, K.P., COP.
_KEEP_WORDS = re.compile(r'\b(?:ic|kp|cop|i\s*/\s*c|k\s*/\s*p|i\s*\.\s*c|k\s*\.\s*p)\b')
#: "the employer's NAME" is still about the employer, not about who the earner is.
_EMPLOYER_NAME_PHRASES = ("employer's name", 'employer name', 'name of the employer', 'name of employer',
                          "company's name", 'company name', 'name of the company', 'name of company',
                          'nama majikan', 'nama syarikat')
_SPLIT = re.compile(r"[;,.]|\b(?:and|dan)\b")


def _hideable_part(part: str) -> bool:
    """One part: a topic, an absence, and NOTHING left over once they and the filler words are gone."""
    s = ' '.join(re.sub(r"[^a-z0-9/' ]", ' ', part).split())
    if not (_TOPIC_RE.search(s) and _ABSENT_RE.search(s)):
        return False
    rest = _ABSENT_RE.sub(' ', _TOPIC_RE.sub(' ', s)).split()
    return all(t in _FILLER for t in rest)


def payslip_only_warning(warning) -> bool:
    """True only when EVERY part of the warning is a pure absence of the employer or the pay period
    (the "nothing left over" rule above). Anything else, or anything mixed, is kept."""
    s = ' '.join(str(warning or '').lower().replace('’', "'").split())
    if not s:
        return False
    for phrase in _EMPLOYER_NAME_PHRASES:
        s = s.replace(phrase, 'employer')
    if any(k in s for k in _KEEP_STEMS) or _KEEP_WORDS.search(s):
        return False
    s = re.sub(r'\bmonth\s*(?:and|&)\s*year\b', 'month/year', s)
    s = re.sub(r'\bbulan\s*(?:dan|&)\s*tahun\b', 'bulan/tahun', s)
    parts = [p for p in _SPLIT.split(s) if p.strip()]
    return bool(parts) and all(_hideable_part(p) for p in parts)


def shown_warnings(doc, warnings):
    """The warnings to SHOW for ``doc``: a declaration in the salary-slip slot loses its payslip-only
    ones; any other document gets ``warnings`` back unchanged (the same object). Display only."""
    if getattr(doc, 'doc_type', '') != 'salary_slip' or not isinstance(warnings, list) or not warnings:
        return warnings
    from ..income_declaration import is_declaration
    if not is_declaration(doc):
        return warnings
    return [w for w in warnings if not payslip_only_warning(w)]
