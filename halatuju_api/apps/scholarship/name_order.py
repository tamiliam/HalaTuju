"""TD-408 — word order in a patronymic name.

Every name comparison (`vision.name_match`, `vision.relationship_name_match`) compares token SETS
after the connectors are stripped, so "ALI BIN ABU" (Ali, son of Abu) and "ABU BIN ALI" (Abu, son of
Ali) — a father and a son built from the same two words — used to match. A patronymic name has two
parts with different meanings: the person's own given name BEFORE the connector, the parent's name
AFTER it. When BOTH names carry a connector, this module splits each at its first connector and asks
whether the pair is a TRUE REVERSAL under the caller's own matcher (exact for identity, tolerant for a
relationship): A's given name matches B's parent's name, A's parent's name matches B's given name, and
the two given names do NOT match each other. Only that is vetoed.

Narrowed after the live dry-run (2026-10-28): a first version vetoed whenever EITHER part pair
mismatched, and a Chinese name whose syllable reads BIN ("LO BIN BIN ...") then split at a "connector"
that is not one, and a genuine birth-certificate mother went partial -> mismatch. A reversal needs both
cross pairs to agree, which a mis-split Chinese name practically never does.

A pure VETO: it can only turn a 'match' / 'partial' into a 'mismatch', never the reverse; anything that is
not a reversal keeps today's set comparison exactly, and a name without a connector (a Chinese name, a
mononym, a name typed without its A/L) is not split. The connectors are the ones `vision._NAME_NOISE`
already treats as one (BIN, BINTI, BT, BTE, ANAK, AK, A/L, A/P, S/O, D/O), so a BIN on one side and a BINTI
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


def patronymic_reversed(a: str, b: str, matcher) -> bool:
    """True only for a TRUE REVERSAL: both names split, A's given part matches B's parent part, A's
    parent part matches B's given part (``matcher`` answering 'match' or 'partial'), and the two given
    parts do not match each other ("ALI BIN ABU" / "ABU BIN ALI"). False in every other case, so the
    caller's set comparison stands unchanged."""
    sa, sb = split_patronymic(a), split_patronymic(b)
    if sa is None or sb is None:
        return False
    (ga, pa), (gb, pb) = sa, sb
    return (matcher(ga, pb) != 'mismatch' and matcher(pa, gb) != 'mismatch'
            and matcher(ga, gb) == 'mismatch')
