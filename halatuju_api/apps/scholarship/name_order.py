"""TD-408 — word order in a patronymic name.

Every name comparison (`vision.name_match`, `vision.relationship_name_match`) compares token SETS
after the connectors are stripped, so "ALI BIN ABU" (Ali, son of Abu) and "ABU BIN ALI" (Abu, son of
Ali) — a father and a son built from the same two words — used to match. A patronymic name has two
parts with different meanings: the person's own given name BEFORE the connector, the parent's name
AFTER it. When BOTH names carry a connector, this module splits each at its first connector and the
caller compares the parts pairwise with its own matcher (exact for identity, tolerant for a
relationship), so a reversed patronymic is a mismatch while a romanisation variant or a near miss
inside one part still behaves as it always has.

A pure VETO: it can only turn a 'match' / 'partial' into a 'mismatch', never the reverse; a name
without a connector (a Chinese name, a mononym, a name typed without its A/L) is not split, so it
keeps today's set comparison exactly. The connectors are the ones `vision._NAME_NOISE` already
treats as one (BIN, BINTI, BT, BTE, ANAK, AK, A/L, A/P, S/O, D/O), so a BIN on one side and a BINTI
on the other still split alike and agree as they did. The slash-less OCR forms AL / AP are NOT split
on (an Arabic "AL" is a name part): a side that carries only those is simply not split.
"""
from __future__ import annotations

import re

#: The first patronymic connector in a name. Word-bounded, so "BTARA" or "KAMAL" never splits; the
#: optional LELAKI / PEREMPUAN follows a long-form ANAK ("ANAK LELAKI", the birth-certificate form).
CONNECTOR_RE = re.compile(
    r'\b(?:anak(?:\s+(?:lelaki|perempuan))?|ak|bin|binti|bte|bt|a\s*/\s*[lp]|s\s*/\s*o|d\s*/\s*o)\b',
    re.IGNORECASE,
)


def split_patronymic(name: str):
    """``(given, parent)`` — the text before and after the name's FIRST connector — or None when the
    name carries no connector, or when either side holds no name token once the noise is stripped
    (a bare "BIN ALI", an honorific alone before the connector). Glued slash markers are detached
    first (`vision._split_glued_markers`, #48), as every matcher does."""
    from .vision import _split_glued_markers, canonical_name_tokens
    s = _split_glued_markers(name or '')
    m = CONNECTOR_RE.search(s)
    if not m:
        return None
    given, parent = s[:m.start()], s[m.end():]
    if not canonical_name_tokens(given) or not canonical_name_tokens(parent):
        return None
    return given, parent


def aligned_parts(a: str, b: str):
    """``[(given_a, given_b), (parent_a, parent_b)]`` when BOTH names split, else None."""
    sa, sb = split_patronymic(a), split_patronymic(b)
    if sa is None or sb is None:
        return None
    return [(sa[0], sb[0]), (sa[1], sb[1])]


def patronymic_reversed(a: str, b: str, matcher) -> bool:
    """True when both names carry a connector and their given names, or their parents' names, do not
    match under ``matcher`` (the caller's own name matcher, recursed on each part — a part that holds
    a second connector, "ALI BIN ABU" after "AHMAD BIN", is split again). False whenever either name
    has no connector: the set comparison then stands unchanged."""
    pairs = aligned_parts(a, b)
    return pairs is not None and any(matcher(x, y) == 'mismatch' for x, y in pairs)
