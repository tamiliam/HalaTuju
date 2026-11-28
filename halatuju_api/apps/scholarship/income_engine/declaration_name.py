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

* **same number of parts** (two or more): part by part IN PRINTED ORDER, every part agrees under the
  tolerant matcher but at most ONE, and that odd pair is at least ``MIN_PART_LETTERS`` long on both
  sides, shares its first letter and is at most ``MAX_EDITS`` apart (no odd pair at all — an exact
  match once the connectors are gone — is a near miss too);
* **one part more on one side**: that extra part is the ONLY inner part (never the first or the last
  word) that is on the allowlist of misread connectors (ALE, AIL, NL for A/L; AIP, NP for A/P; and the
  exact BNT only when the other name prints a connector; SO and DO only when it prints S/O, D/O, A/L or
  A/P of the same sex — review round 4). It drops, and the rest must agree in printed order as above. Two
  extra parts, or any other extra part, are never close.

Review round 3: the order is fixed (own name first, father's after), and a reversal is judged with this
module's own allowance too ("RAJAN A/L KUMARIM" is not "KUMARAN A/L RAJAN"). A connector GLUED onto a
part ("KUMARIAL", "KUMARANAP", "APARUMUGAM") never agrees with the bare part: its sex would go unread.
Only the allowlisted words drop: real short name parts (AH, HO, LO, SOO, SOH, BAN, BUN, BEN, AN, AI, DOO,
SIN, LIN) never do.

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
not payslip-only). When unsure, the warning is kept. Review round 3: a document word is no filler
("Employer declaration missing" stays), a bare "period", "tempoh", "month/year" or "bulan/tahun" is no
pay period (it may be the declaration's own date), and "not visible", "blank", "unclear", "covered",
"cut", "tidak jelas", "kabur", "ditutup", "kosong", "terpotong" and the like keep the warning.

**3. 'close' is not served yet.** ``SHOW_CLOSE`` (below) is False until NRIC chip Sprint 3 gives the web
an amber pill for it; until then ``soften`` changes nothing and the API shows 'mismatch' as before.

**4. Topic codes first (owner 2026-11-28).** The word list kept failing because the AI words each note
differently on every Re-run. The salary-slip read now tags each warning with a topic code
(`vision/warning_topics.py`); ``shown_warnings`` hides the payslip-only TOPICS when every warning carries
a valid code, still never a warning with a keep word. An untagged or older read falls back to the word
filter for the whole list. Review round 1: under a payslip-only code a warning hides only when it also names
an absence; no keep word (widened: signature, alteration, unreadable, mismatch, fake and family words) and
no missing date. When in doubt it SHOWS. Review round 2: a keep list is never complete, so the note hides
only when EVERY part names a payslip-only topic and an absence (``tagged_hides``); else the word filter decides.

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

#: `_canonical_name_seq` keeps BN (it is not in `vision._NAME_NOISE`); it is a connector here.
_ALSO_DROPPED = frozenset({'bn'})

#: The connectors that may be GLUED onto a name part: ``_GLUED_CONNECTORS``, built below from the same
#: sets as the sex signs and the droppable-misread allowlist, so the lists can never drift apart.


def _parts(name: str) -> list:
    from ..vision import _canonical_name_seq
    return [t for t in _canonical_name_seq(name or '') if t not in _ALSO_DROPPED]


def _swallows_glued_connector(x: str, y: str) -> bool:
    """Review round 3 (blocker 2): True when one part ends (or starts) with a connector that the other
    part does not, and taking that connector off brings the two parts no further apart: the agreement
    may then come from swallowing glued connector letters, whose sex is never read ("KUMARIAL" against
    "KUMARI", "KUMARANAP" against "KUMARAN", "APARUMUGAM" against "ARUMUGAM"). Review round 4: "no
    further apart", not only "closer", so "KUMARANP" (KUMARA + a glued NP) against "KUMARAN" counts too.
    Such a pair never agrees, whatever the sex. Checked on every pair before any edit allowance (the
    tolerant matcher's too)."""
    from ..vision import _levenshtein
    for p, q in ((x, y), (y, x)):
        base = _levenshtein(p, q)
        for c in _GLUED_CONNECTORS:
            if len(p) - len(c) >= 2 and p.endswith(c) and not q.endswith(c) \
                    and _levenshtein(p[:-len(c)], q) <= base:
                return True
            if len(p) - len(c) >= 2 and p.startswith(c) and not q.startswith(c) \
                    and _levenshtein(p[len(c):], q) <= base:
                return True
    return False


def _one_part_off(x: str, y: str) -> bool:
    """The near-miss edit allowance for ONE pair of parts (owner C1: 4+ letters, same first letter, at
    most 2 edits), never over glued connector letters."""
    from ..vision import _fold_name_token, _levenshtein
    if _swallows_glued_connector(x, y):
        return False
    x, y = _fold_name_token(x), _fold_name_token(y)
    return min(len(x), len(y)) >= MIN_PART_LETTERS and x[:1] == y[:1] and _levenshtein(x, y) <= MAX_EDITS


def _agree(a: list, b: list, min_parts: int = 2) -> bool:
    """Part by part IN PRINTED ORDER (review round 3, should-fix 3: own name first, father's after; never
    any order): every pair agrees under the tolerant matcher but at most ONE, which is within the
    near-miss allowance. No pair may agree by swallowing a glued connector."""
    from ..vision import _tokens_close
    if len(a) != len(b) or len(a) < min_parts:
        return False
    if any(_swallows_glued_connector(x, y) for x, y in zip(a, b)):
        return False
    odd = [(x, y) for x, y in zip(a, b) if not _tokens_close(x, y)]
    return not odd or (len(odd) == 1 and _one_part_off(*odd[0]))


#: Review round 3 (should-fix 4): an ALLOWLIST of the extra short words that may drop as a misread
#: connector, with the sex each one is. Not "any short word near a connector": that dropped real Chinese
#: name parts (AH, HO, LO, SOO, SOH, BAN, BUN, BEN, AN, AI, DOO, and SIN, LIN, KIN, YIN one edit from
#: BIN). Only these drop, and nothing else ever does:
#:   * the misreads of A/L seen on handwritten forms (ALE, AIL, NL) and their A/P twins (AIP, NP) —
#:     none of them is a name part; they drop even when the other name prints no connector;
#:   * the slash-less exact connectors that ``_parts`` keeps (SO, DO, BNT) — SO and DO are also real
#:     Chinese/Vietnamese name parts, so they drop ONLY when the other name prints a connector itself.
_MISREAD_CONNECTORS = {'ale': 'm', 'ail': 'm', 'nl': 'm', 'aip': 'f', 'np': 'f'}
_EXACT_CONNECTORS = {'so': 'm', 'do': 'f', 'bnt': 'f'}


def _without_misread_connector(longer: list, other_has_connector: bool, other_slash_signs=frozenset()):
    """``(longer without its ONE droppable inner part, that part's sex)``, or ``(None, '')`` when there is
    not exactly one (never the first or the last word). BNT drops beside any printed connector; SO and DO
    only beside a printed slash connector of their own sex (review round 4: never beside BIN or BINTI)."""
    droppable = dict(_MISREAD_CONNECTORS)
    if other_has_connector:
        droppable.update({w: s for w, s in _EXACT_CONNECTORS.items()
                          if w not in ('so', 'do') or s in other_slash_signs})
    hits = [i for i in range(1, len(longer) - 1) if longer[i] in droppable]
    if len(hits) != 1:
        return None, ''
    return longer[:hits[0]] + longer[hits[0] + 1:], droppable[longer[hits[0]]]


#: Review round 1 (should-fix 4): the connectors carry a sex. A son (A/L, S/O, BIN) is never 'close' to a
#: daughter (A/P, D/O, BINTI), even though both connectors drop out of the comparison. Review round 2: the
#: slash-less EXACT forms carry their sex too (SO, AL, BN are male; DO, AP, BT, BNT are female), and they
#: are read BEFORE any misread logic, so an exact SO is never "one edit from DO".
_MALE = frozenset({'a/l', 'al', 's/o', 'so', 'bin', 'bn'})
_FEMALE = frozenset({'a/p', 'ap', 'd/o', 'do', 'binti', 'bt', 'bte', 'bnt'})
#: Review round 3 (blocker 2), round 4 (blocker 1): the slash-less connector forms that may be GLUED onto
#: a name part ("KUMARIAL" = KUMARI + AL, "KUMARANAP", "APARUMUGAM", "DEVINL", "KUMARANNP"): every exact
#: slash-less sex sign above, and every word the allowlist lets drop as a misread connector.
_GLUED_CONNECTORS = tuple(sorted(
    {c for c in _MALE | _FEMALE if '/' not in c} | set(_MISREAD_CONNECTORS) | set(_EXACT_CONNECTORS),
    key=lambda c: (-len(c), c)))
#: SO and DO are real Chinese/Vietnamese name parts too: they drop only beside a printed SLASH connector
#: of the same sex (review round 4, minor 3), never beside BIN, BINTI, BT or BNT.
_SLASH_SIGNS = {'a/l': 'm', 's/o': 'm', 'a/p': 'f', 'd/o': 'f'}
#: A slash connector glued on BOTH sides ("KUMARANA/PRAJAN"), which `vision._split_glued_markers` (one
#: side only) leaves whole. Slash forms only, as there: a '/' never occurs inside a real name.
_GLUED_BOTH_SIDES = re.compile(r'([a-z])(a/[lp]|[ds]/o)([a-z])')


def _name_words(name: str) -> list:
    """The name's words, slash spacing and glue tidied (so "A / L" and "KUMARANA/PRAJAN" read A/L)."""
    from ..vision import _split_glued_markers
    tidy = re.sub(r'\s*/\s*', '/', str(name or '').lower())
    tidy = _split_glued_markers(_GLUED_BOTH_SIDES.sub(r'\1 \2 \3', tidy))
    return re.findall(r'[a-z]+(?:/[a-z]+)?', tidy)


def _slash_signs(name: str) -> set:
    """'m' and/or 'f' for each SLASH connector (A/L, S/O, A/P, D/O) the name prints."""
    return {_SLASH_SIGNS[t] for t in _name_words(name) if t in _SLASH_SIGNS}


def _gender_signs(name: str) -> set:
    """'m' and/or 'f' for each connector the name prints (slash spacing and glue tidied first)."""
    signs = set()
    for tok in _name_words(name):
        if tok in _MALE:
            signs.add('m')
        elif tok in _FEMALE:
            signs.add('f')
    return signs


def _opposite_sex(sa: set, sb: set) -> bool:
    return bool(sa) and bool(sb) and sa.isdisjoint(sb)


def _reversed_within_allowance(extracted, reference) -> bool:
    """Review round 3 (should-fix 3): `name_order.patronymic_reversed` judged with THIS module's own
    allowance on each side of the connector (the same ``_agree`` the close check uses, one part or
    more), so a father and a son with a 2-edit misread ("RAJAN A/L KUMARIM" / "KUMARAN A/L RAJAN") is a
    reversal too."""
    from ..name_order import patronymic_reversed

    def matcher(x, y):
        return 'match' if _agree(_parts(x), _parts(y), min_parts=1) else 'mismatch'
    return patronymic_reversed(extracted, reference, matcher)


def near_miss(extracted, reference) -> bool:
    """True when the two names differ only by a small misread (the rule above)."""
    from .buckets import _near_miss_reversal
    a, b = _parts(extracted), _parts(reference)
    if _near_miss_reversal(extracted, reference) or _reversed_within_allowance(extracted, reference):
        return False
    sa, sb = _gender_signs(extracted), _gender_signs(reference)
    if _opposite_sex(sa, sb):
        return False                                  # A/L against A/P, S/O against D/O, BIN against BINTI
    if len(a) == len(b):
        return _agree(a, b)
    if abs(len(a) - len(b)) != 1:
        return False
    other = reference
    if len(a) < len(b):
        a, b, sa, sb = b, a, sb, sa                   # `a` is the side with the extra word
        other = extracted
    a, sex = _without_misread_connector(a, other_has_connector=bool(sb),
                                        other_slash_signs=_slash_signs(other))
    if a is None:
        return False
    if _opposite_sex({sex}, sb) or _opposite_sex({sex}, sa):
        return False                                  # a misread A/L against a printed A/P
    return _agree(a, b)


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
_EMPLOYER_TOPICS = (
    'name of the employer', 'name of employer', "employer's name", 'employers name', 'employer name',
    'name of the company', 'name of company', "company's name", 'company name', 'nama majikan',
    'nama syarikat', 'employers', 'employer', 'majikan', 'company', 'syarikat',
)
#: The pay period. Review round 3 (minor 5): only words that clearly say PAY. A bare "period", "tempoh",
#: "month/year" or "bulan/tahun" may be the declaration's own date, so it is no topic.
_PERIOD_TOPICS = (
    'pay slip period','payslip period', 'pay period', 'salary period', 'income period', 'period of pay',
    'period of salary', 'period of income', 'month/year of salary', 'month/year of pay',
    'month/year of income', 'pay month', 'salary month', 'income month', 'month of pay',
    'month of salary', 'month of income', 'tempoh gaji', 'tempoh pendapatan', 'bulan gaji',
    'bulan pendapatan',
)
_TOPICS = _EMPLOYER_TOPICS + _PERIOD_TOPICS
#: The ABSENCE words (English and Malay). A bare "not" is NOT one ("employer is not a company" stays).
#: Review round 3 (minor 6): "not visible", "blank" and "kosong" are not absences: the employer may be
#: there but covered over. They are keep words below.
_ABSENCES = (
    'not stated', 'not given', 'not shown', 'not provided', 'not specified', 'not indicated', 'not listed',
    'not mentioned', 'not included', 'not present', 'not recorded', 'not written', 'not filled in',
    'not filled', 'not available', 'not declared', 'missing', 'absent', 'none',
    'no', 'n/a', 'nil', 'omitted', 'unspecified', 'unstated', 'without', 'lack', 'lacks', 'lacking',
    'tiada', 'tidak dinyatakan', 'tidak dicatat', 'tidak dicatatkan', 'tidak tercatat', 'tidak ditulis',
    'tidak diisi', 'tidak ada', 'tidak disertakan', 'tanpa',
)
#: The FILLER words that may stand beside a topic and an absence and say nothing of their own. Review
#: round 3 (blocker 1): no document word (slip, payslip, document, form, declaration): "Employer
#: declaration missing" or "No company payslip" names a missing PAPER, which must stay. A document word
#: is dropped only inside a place phrase ("on the document", "pada borang ini": ``_PLACE``).
#: Case 1048 (2026-11-28): "specific" and "exact" describe the missing pay period or employer ("A specific
#: pay period is not stated"). "clear" is NOT filler: "No clear employer stated" may mean the employer is
#: there but unreadable, the note review round 3 keeps ("unclear", "tidak jelas").
_FILLER = frozenset({
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'has', 'have', 'of', 'this',
    'any', 'stated', 'shown', 'given', 'provided',
    'specified', 'indicated', 'mentioned', 'listed', 'recorded', 'ini', 'yang',
    'telah', 'dinyatakan', 'specific', 'exact',
})
#: Where the note was made: "on the document", "in this form", "pada borang ini", "di dalam dokumen".
_PLACE = re.compile(
    r"\b(?:on|in|within)\s+(?:the\s+|this\s+)?(?:document|form|slip|payslip|pay\s+slip|declaration)\b"
    r"|\b(?:pada|dalam|di\s+dalam|di)\s+(?:dokumen|borang|slip|surat\s+akuan|akuan)(?:\s+ini)?\b")


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
               'mencurigakan', 'inconsistent', 'differ', 'berbeza', 'mismatch', 'relative', 'saudara',
               # review round 3 (minor 6): the employer may be there but covered over or unreadable
               'visib', 'unclear', 'cover', 'blank', 'cut', 'crop', 'legib', 'unread', 'obscur', 'hidden',
               'smudg', 'fade', 'jelas', 'kabur', 'tutup', 'kosong', 'potong', 'dibaca',
               # review round 4 (minor 2): "not found" may mean the employer was covered over
               'not found', 'dijumpai', 'ditemui',
               # topic-codes review round 1 (2026-11-28): a wrong code must never hide these families.
               # Signature and stamp; alteration; unreadable; mismatch; fake or context.
               'tanda tangan', 't/t', 'edit', 'modif', 'amend', 'chang', 'cross', 'white', 'tipp', 'eras',
               'manipul', 'pinda', 'padam', 'conteng', 'tindih', 'semula', 'blur', 'dark', 'gelap', 'quality',
               'faint', 'pudar', 'torn', 'koyak', 'rosak', 'damag', 'partial', 'match', 'sepadan', 'verif',
               'templat', 'sample', 'contoh', 'photocop', 'salinan', 'generat', 'invent', 'famil', 'father',
               'mother', 'bapa', 'duplicat', 'b40', 'high', 'outdat',
               # topic-codes review round 2: genuineness, family, mismatch, income level, duplicate, page
               'genuin', 'authentic', 'fabricat', 'counterfeit', 'bogus', 'ragu', 'tiru', 'husband', 'wife',
               'suami', 'isteri', 'brother', 'sister', 'daughter', 'neighbo', 'jiran', 'agree', 'tally',
               'add up', 'adds up', 'tepat', 'threshold', 'exceed', 'melebihi', 'rendah', 'twice', 'another',
               'serupa', 'dua kali', 'halaman', 'screenshot', 'original', 'typed',
               # topic-codes review round 3: corrected, incomplete, a copy of another form, an uncle
               'correct', 'incomplete', 'lengkap', 'identical', 'uncle', 'pakcik')
#: ...and these as whole words (too short to match inside other words): IC, I/C, I.C., KP, K/P, K.P., COP;
#: review round 1 of the topic codes: CAP, SAMA, IBU, LAMA ("alamat" is an address); READ and TERANG at a
#: word start only ("already", "keterangan"); OFFICIAL unless it only names the payslip the type note means.
#: Review round 2 of the topic codes: SON, ANAK, LOW whole words ("reason", "below"); ABANG, ADIK, KAKAK,
#: HALF, PAGE at a word start ("behalf"); a page only as a PLACE ("from this page") is no keep word.
_KEEP_WORDS = re.compile(r'\b(?:ic|kp|cop|cap|sama|ibu|lama|son|anak|low|i\s*/\s*c|k\s*/\s*p|i\s*\.\s*c|k\s*\.\s*p)\b'
                         r'|\b(?:read|terang|abang|adik|kakak|half|page)'
                         r'|official(?!\s+(?:pay[\s-]?slip|salary\s+slip))')
_PAGE_PLACE = re.compile(r'\b(?:on|in|from|within)\s+(?:this|the)\s+page\b')
#: "the employer's NAME" is still about the employer, not about who the earner is.
_EMPLOYER_NAME_PHRASES = ("employer's name", 'employer name', 'name of the employer', 'name of employer',
                          "company's name", 'company name', 'name of the company', 'name of company',
                          'nama majikan', 'nama syarikat')
_SPLIT = re.compile(r"[;,.]|\b(?:and|dan)\b")
#: Case 1048 (2026-11-28): the TYPE NOTE. A part that says only that the document is a declaration and
#: not a payslip ("The document is an income declaration letter rather than a standard payslip", "Dokumen
#: ini ialah surat akuan pendapatan, bukan slip gaji") tells the officer nothing new: this filter runs only
#: on a document already seen as a declaration. The WHOLE part must match: any other word keeps it, and
#: the keep words above are checked first over the whole warning. "handwritten" is no part of it: "The
#: document is handwritten" is a note review round 1 keeps.
_EN_TAIL = (r"(?:rather\s+than|instead\s+of|not)\s+(?:an?\s+)?(?:(?:standard|formal|regular|official|typical)\s+)?"
            r"(?:pay[\s-]?slip|salary\s+slip)")
_MS_TAIL = r"bukan(?:nya)?\s+(?:sebuah\s+|satu\s+)?(?:slip\s+gaji|penyata\s+gaji)"
_TYPE_NOTE = re.compile(
    r"(?:(?:(?:the|this)\s+)?(?:uploaded\s+)?(?:document|form)|this|it)\s+(?:is|appears\s+to\s+be)\s+(?:an?\s+)?"
    rf"(?:(?:income|salary)\s+)?declaration(?:\s+(?:letter|form))?\s+{_EN_TAIL}"
    r"|(?:(?:dokumen|borang)(?:\s+ini)?|ini)\s+(?:ialah|adalah|merupakan)\s+(?:sebuah\s+|satu\s+)?(?:surat\s+)?"
    rf"(?:akuan|pengakuan)(?:\s+(?:pendapatan|gaji))?\s+{_MS_TAIL}")
#: "a declaration, not a payslip" / "akuan, bukan slip gaji": the comma (or and/dan) before the tail would
#: split the type note in two, so it is joined first. A joined part can only hide as a whole type note:
#: the tail's own words (not, rather than, bukan, payslip) are neither topic, absence nor filler.
_TYPE_JOIN = re.compile(rf"(?:\s*,\s*(?:(?:and|dan)\s+)?|\s+(?:and|dan)\s+)(?=(?:{_EN_TAIL}|{_MS_TAIL})\b)")


def _type_note(part: str) -> bool:
    """One part that says only "this is a declaration, not a payslip" (the whole part, nothing else)."""
    return bool(_TYPE_NOTE.fullmatch(' '.join(re.sub(r"[^a-z0-9/' ]", ' ', part).split())))


def _hideable_part(part: str) -> bool:
    """One part: a topic, an absence, and NOTHING left over once they and the filler words are gone."""
    s = ' '.join(re.sub(r"[^a-z0-9/' ]", ' ', part).split())
    s = ' '.join(_PLACE.sub(' ', s).split())
    if not (_TOPIC_RE.search(s) and _ABSENT_RE.search(s)):
        return False
    rest = _ABSENT_RE.sub(' ', _TOPIC_RE.sub(' ', s)).split()
    return all(t in _FILLER for t in rest)


def _normalised(warning) -> str:
    """The warning lower-cased, spaces tidied, "the employer's name" read as "employer"."""
    s = ' '.join(str(warning or '').lower().replace('’', "'").split())
    for phrase in _EMPLOYER_NAME_PHRASES:
        s = s.replace(phrase, 'employer')
    return s


def _keeps(s: str) -> bool:
    return any(k in s for k in _KEEP_STEMS) or bool(_KEEP_WORDS.search(_PAGE_PLACE.sub(' ', s)))


#: Date phrases that say WHEN a paper was signed: "signing" holds the keep stem "sign", so a "the date is the
#: signing date rather than a pay period" note would always show; the tagged path drops these before the keep
#: check, but NEVER beside an absence ("signing date missing", "date signed: missing", "tiada"): a missing
#: date shows. Review round 1: "signed on" is no date phrase ("not signed on behalf of the employer").
_SIGNING_DATE_PHRASES = re.compile(r"\b(?:signing\s+date|date\s+of\s+signing|date\s+signed|signed\s+date)\b")
_AFTER_GAP = re.compile(r"\s*[:\-]?\s*(?:(?:is|are|was|were|has|have|been|being|also)\s+){0,2}")
_BEFORE_GAP = r"\s*[:\-]?\s*(?:(?:the|a|an|its)\s+)?$"
#: Topic-codes review round 2: the tagged path judges PART BY PART. Every part must name a payslip-only TOPIC
#: (the word filter's, plus the take-home, gross and payslip words the codes cover) and an ABSENCE.
_PAPER_TOPICS = ('payslip', 'pay slip', 'salary slip', 'slip gaji', 'penyata gaji')
_TAGGED_TOPIC_RE = _phrases(_TOPICS + _PAPER_TOPICS + (
    'take home', 'net pay', 'net income', 'net salary', 'gross', 'gaji bersih', 'gaji kasar',
    'pendapatan bersih', 'pendapatan kasar'))
#: The narrow absences, only beside a pay period or a payslip: "... a signing date RATHER THAN a (specific)
#: pay period", "the document SHOWS ONLY ...", "ONLY a declaration DATE". Never beside the employer ("the
#: employer is a person rather than a company" is no absence), and never with no such topic at all.
_NARROW_TOPIC = '(?:' + '|'.join(re.escape(t) for t in sorted(_PERIOD_TOPICS + _PAPER_TOPICS, key=len,
                                                               reverse=True)) + ')'
_RATHER_THAN = re.compile(rf"(?<![a-z0-9/'])rather\s+than\s+an?\s+(?:[a-z]+\s+){{0,3}}{_NARROW_TOPIC}"
                          r"(?![a-z0-9/'])")
_SHOWS_ONLY = re.compile(r"(?<![a-z0-9/'])(?:shows?\s+only|only\s+an?\s+(?:[a-z]+\s+){0,3}date)(?![a-z0-9/'])")
_NARROW_TOPIC_RE = re.compile(rf"(?<![a-z0-9/']){_NARROW_TOPIC}(?![a-z0-9/'])")
#: A part that says a DATE (or a month) is absent always shows: a declaration should carry one. The topic
#: phrases ("pay month", "bulan gaji") are taken out first; they name the pay period, not a date.
_DATE_WORDS = re.compile(r"\b(?:dated?|dates|undated|(?:ber)?tarikh|months?|bulan)\b")
#: The parts: the word filter's ; , . and/dan, plus : and the turn words (a "but ..." part is a new claim).
_TAGGED_SPLIT = re.compile(r"[;,.:]|\b(?:and|dan|but|however|although|though|whereas|while|tetapi|tapi|namun|"
                           r"walaupun|manakala)\b")
#: Topic-codes review round 3: "nothing left over". Once the topic and absence words are gone, every word
#: left in a hiding part must be one of these (no word that can carry a claim of its own). "date" is safe
#: here: a part that says a date is absent never reaches this test.
_TAGGED_FILLER = _FILLER | frozenset((
    'pay amount separate separately details information info figure document form declaration letter slip '
    'payslip on in from for it there only shows show rather than does not page appear appears income salary '
    'or nor either neither available filled date maklumat butiran pada dalam di borang dokumen surat akuan '
    'amaun atau').split())


def _beside_absence(s: str, m: re.Match) -> bool:
    """True when an absence word sits right after or right before the match (a gap of is/was/:/the only)."""
    after = s[m.end():]
    if _ABSENT_RE.match(after, _AFTER_GAP.match(after).end()):
        return True
    return bool(re.search(_ABSENT_RE.pattern + _BEFORE_GAP, s[:m.start()]))


def _tagged_part_hides(part: str) -> bool:
    """One part: a payslip-only topic AND an absence (``_ABSENT_RE``, or a narrow one beside a pay period
    or a payslip), no date said to be absent, and nothing left over but ``_TAGGED_FILLER`` words."""
    p = ' '.join(re.sub(r"[^a-z0-9/' ]", ' ', part).split())
    if not _TAGGED_TOPIC_RE.search(p):
        return False
    if _ABSENT_RE.search(p):
        if _DATE_WORDS.search(_TAGGED_TOPIC_RE.sub(' ', p)):
            return False
    elif not (_RATHER_THAN.search(p) or (_SHOWS_ONLY.search(p) and _NARROW_TOPIC_RE.search(p))):
        return False
    return all(t in _TAGGED_FILLER for t in _ABSENT_RE.sub(' ', _TAGGED_TOPIC_RE.sub(' ', p)).split())


def tagged_hides(warning) -> bool:
    """The tagged path, for a warning under a payslip-only code. A keep word anywhere (once the signing-date
    phrases, none beside an absence, are gone) SHOWS it. Then it hides only when EVERY part
    (``_TAGGED_SPLIT``) names a payslip-only topic and an absence, no part saying a date is absent; else the
    word filter decides (``payslip_only_warning``, which never hides more than before). Topic-codes review
    round 2: a keep list can never be complete, so a part about anything else shows the note."""
    s = _normalised(warning)
    if not s:
        return False
    stripped = _SIGNING_DATE_PHRASES.sub(lambda m: m.group(0) if _beside_absence(s, m) else ' ', s)
    if _keeps(stripped):
        return False
    stripped = re.sub(r'\bmonth\s*(?:and|&)\s*year\b', 'month/year', stripped)
    stripped = re.sub(r'\bbulan\s*(?:dan|&)\s*tahun\b', 'bulan/tahun', stripped)
    parts = [p for p in _TAGGED_SPLIT.split(stripped) if p.strip()]
    if parts and all(_tagged_part_hides(p) for p in parts):
        return True
    return payslip_only_warning(warning)


def has_keep_word(warning) -> bool:
    """True when the warning names anything that always keeps it (``_KEEP_STEMS``, ``_KEEP_WORDS``):
    tampering, a chop or signature, the applicant, a name or an IC, an unreadable or covered part, ..."""
    return _keeps(_normalised(warning))


def payslip_only_warning(warning) -> bool:
    """True only when EVERY part of the warning is a pure absence of the employer or the pay period
    (the "nothing left over" rule above) or the declaration type note. Anything else, or anything mixed,
    is kept."""
    s = _normalised(warning)
    if not s or _keeps(s):
        return False
    s = re.sub(r'\bmonth\s*(?:and|&)\s*year\b', 'month/year', s)
    s = re.sub(r'\bbulan\s*(?:dan|&)\s*tahun\b', 'bulan/tahun', s)
    s = _TYPE_JOIN.sub(' ', s)
    parts = [p for p in _SPLIT.split(s) if p.strip()]
    return bool(parts) and all(_type_note(p) or _hideable_part(p) for p in parts)


def shown_warnings(doc, warnings):
    """The warnings to SHOW for ``doc``: a declaration in the salary-slip slot loses its payslip-only
    ones; any other document gets ``warnings`` back unchanged (the same object). Display only.

    Topic-coded (owner 2026-11-28): when the read tagged its warnings (``vision_fields['warning_topics']``,
    `vision.warning_topics.valid_topics`), warning i hides only when its topic is payslip-only AND
    `tagged_hides` (no keep word; every part a payslip-only absence). When in doubt it SHOWS: a wrong
    code must never hide a note the reviewer needs. Topics missing, of the wrong length or with an unknown
    code: the word filter above, for the WHOLE list. The two are never mixed."""
    if getattr(doc, 'doc_type', '') != 'salary_slip' or not isinstance(warnings, list) or not warnings:
        return warnings
    from ..income_declaration import is_declaration
    if not is_declaration(doc):
        return warnings
    from ..vision.warning_topics import KEY, PAYSLIP_ONLY_TOPICS, valid_topics
    stored = getattr(doc, 'vision_fields', None)
    topics = stored.get(KEY) if isinstance(stored, dict) else None
    if valid_topics(warnings, topics):
        return [w for w, t in zip(warnings, topics) if t not in PAYSLIP_ONLY_TOPICS or not tagged_hides(w)]
    return [w for w in warnings if not payslip_only_warning(w)]
