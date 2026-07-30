"""
Utility functions for the courses app.

Extracted from one-time management commands for reuse in tests and recurring tools.
"""
import re


# ── Parentage-marker tidy (person names) ─────────────────────────

# A MyKad parentage marker is printed with NO space inside it: "A/P", "A/L", "S/O", "D/O".
# Students routinely type one anyway ("A/ P", "A / P", "A /P") and the form stores the
# signature verbatim, so the stray space reaches `StudentProfile.name` — the canonical name
# the payments CSV, emails, sponsor profiles and partner exports all read.
#
# ⚠ THIS IS A MARKER FIX, NOT A NAME FIX. It only ever removes whitespace INSIDE the marker;
# it cannot touch a single letter of anyone's name, reorder tokens, or alter spacing between
# name words. A '/' never legitimately occurs inside a Malaysian personal name, which is what
# makes the rewrite safe — the same property `vision._split_glued_markers` relies on.
#
# Why it belongs at the WRITE boundary: `apps.scholarship.vision` already tolerates the spaced
# forms when COMPARING names (`_NAME_NOISE`), a tolerance added for application #20 precisely
# so a typed "A/ P" would stop reading as a false Name mismatch against the student's own IC.
# That was right, and it is why nothing ever flagged the typo — but tolerating a variant on read
# is not the same as storing one form. This is the missing half. (2026-07-30)
_SPACED_PARENTAGE_MARKER = re.compile(r'\b([ASD])\s*/\s*([PLO])\b', flags=re.IGNORECASE)


def tidy_parentage_marker(name: str) -> str:
    """Collapse whitespace inside a slash parentage marker: 'A/ P' → 'A/P'. Idempotent.

    Preserves the marker's own letter case, so it composes with any case normalisation
    applied around it. Returns the input unchanged when there is no slash marker.
    """
    if not name or '/' not in name:
        return name
    return _SPACED_PARENTAGE_MARKER.sub(r'\1/\2', name)


# ── MOHE URL builder ──────────────────────────────────────────────

MOHE_BASE = 'https://online.mohe.gov.my/epanduan/carianNamaProgram'


def build_mohe_url(course_id: str, stream: str) -> str:
    """Generate MOHE ePanduan URL from course_id and stream."""
    prefix = course_id[:2]
    # Science gets S, arts gets A, both defaults to S
    cat = 'A' if stream == 'arts' else 'S'
    return f'{MOHE_BASE}/{prefix}/{course_id}/{cat}/stpm'


# ── Proper case name ─────────────────────────────────────────────

_LOWERCASE_WORDS = {
    # Malay connectors
    'dan', 'dengan', 'atau', 'di', 'ke', 'untuk', 'dalam', 'bagi', 'oleh', 'yang',
    # English connectors
    'and', 'of', 'with', 'in', 'for', 'at', 'the', 'or', 'by',
}


def _case_token(token: str, is_first: bool) -> str:
    """Title-case a single word token, lowercasing connectors (unless first).

    Also handles hyphenated words (e.g. LAIN-LAIN -> Lain-Lain).
    """
    if not token:
        return token
    lower = token.lower()
    if not is_first and lower in _LOWERCASE_WORDS:
        return lower
    # Capitalise each hyphen-separated segment
    return '-'.join(part.capitalize() for part in lower.split('-'))


def proper_case_name(name: str) -> str:
    """Convert an all-caps programme name to proper title case.

    Rules:
    - Every word is title-cased by default.
    - Malay/English connector words are lowercased (except the first word).
    - Parenthesised campus suffixes are cased with the same rules.
    - The trailing '#' marker is preserved as-is.
    """
    if not name:
        return name

    # Strip and split trailing '#' marker
    suffix = ''
    stripped = name.strip()
    if stripped.endswith('#'):
        suffix = ' #'
        stripped = stripped[:-1].rstrip()

    # Split into: plain text segments and parenthesised segments
    segment_re = re.compile(r'(\([^)]*\))')
    segments = segment_re.split(stripped)

    result_parts = []
    first_word_seen = False

    for seg in segments:
        if seg.startswith('(') and seg.endswith(')'):
            # Bracketed segment — case the inside independently
            inner = seg[1:-1]
            inner_tokens = re.split(r'(\s+)', inner)
            cased_inner = []
            inner_first = True
            for it in inner_tokens:
                if not it.strip():
                    cased_inner.append(it)
                else:
                    cased_inner.append(_case_token(it, inner_first))
                    inner_first = False
            result_parts.append('(' + ''.join(cased_inner) + ')')
            first_word_seen = True
        else:
            # Plain text segment — tokenise on whitespace
            tokens = re.split(r'(\s+)', seg)
            for tok in tokens:
                if not tok.strip():
                    result_parts.append(tok)
                else:
                    result_parts.append(_case_token(tok, not first_word_seen))
                    first_word_seen = True

    return ''.join(result_parts) + suffix
