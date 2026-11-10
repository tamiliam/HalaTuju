"""Contract module: the {{token}} merge variables and the Word bracket placeholders.

Moved unchanged out of ``contracts.py`` when audit A3.8 (2026-11-10) made it a package.
"""
import re


# ─────────────────────────────────────────────────────────────────────────────
# Merge variables (2026-07-21): {{token}} placeholders an author writes into a clause
# / heading / preamble, resolved to the case's real values at RENDER time (never stored
# resolved — the template keeps the generic token, the signed snapshot gets the value).
# The registry is the single source of truth the editor's "Insert variable" menu reads.
# ─────────────────────────────────────────────────────────────────────────────
CONTRACT_VARS = (
    ('student_name', "The student's full name"),
    ('student_nric', "The student's NRIC"),
    ('guarantor_name', "The guarantor / parent-guardian's name"),
    ('guarantor_relationship', 'The guarantor relationship (e.g. father)'),
    ('donor_name', 'The donor / sponsor name (from the template config)'),
    ('donor_nric', "The donor / counterparty's NRIC (from config)"),
    ('donor_address', "The donor / counterparty's address (from config)"),
    ('amount', 'The bursary amount (e.g. RM3,000)'),
    ('institution', 'The institution name'),
    ('course', 'The course / programme name'),
    ('commencement_date', 'The course commencement date'),
    ('progress_standard', 'The academic progress standard'),
)
_VAR_RE = re.compile(r'\{\{\s*(\w+)\s*\}\}')


def substitute_vars(text, context):
    """Replace ``{{token}}`` placeholders with values from ``context``. A KNOWN token with
    no value renders empty; an UNKNOWN token is left VERBATIM — a stray ``{{typo}}`` stays
    visible in the document (obviously fixable) rather than becoming a silent blank."""
    if not text:
        return text

    def _repl(m):
        key = m.group(1)
        if key in context:
            val = context[key]
            return '' if val is None else str(val)
        return m.group(0)

    return _VAR_RE.sub(_repl, text)


# Bracket placeholders authors hand-type in Word (e.g. "[Student Full Name & NRIC]") →
# our tokens, applied on import. Only mappings with reliable backing data are listed;
# an unrecognised bracket (e.g. "[Date]", "[Student Address]") is left untouched for the
# author to resolve, never converted into a dangling token.
_BRACKET_VARS = {
    'student full name & nric': '{{student_name}} ({{student_nric}})',
    'student full name and nric': '{{student_name}} ({{student_nric}})',
    'student name & nric': '{{student_name}} ({{student_nric}})',
    'student full name': '{{student_name}}',
    'student name': '{{student_name}}',
    'student nric': '{{student_nric}}',
    'institution': '{{institution}}',
    'course': '{{course}}',
}
_BRACKET_RE = re.compile(r'\[([^\[\]]+)\]')


def _brackets_to_vars(text):
    """Convert an author's hand-typed ``[Bracket Placeholder]`` to the matching ``{{token}}``
    (import-time sugar). Unrecognised brackets are preserved verbatim."""
    if not text:
        return text
    return _BRACKET_RE.sub(
        lambda m: _BRACKET_VARS.get(m.group(1).strip().lower(), m.group(0)), text)


# The counterparty (Donor) recital, shaped like:
#   "… between {Name}, NRIC {nric}, of {address} ("Donor") …"
# Best-effort — a preamble that doesn't match leaves the fields for the author to fill.
_COUNTERPARTY_RE = re.compile(
    r'between\s+(?P<name>.+?)\s*,\s*NRIC\s+(?P<nric>[\w/-]+)\s*,\s*of\s+(?P<address>.+?)'
    r'\s*[(\[]\W{0,2}(?:the\s+)?Donor',
    re.IGNORECASE)


def _extract_counterparty(preamble):
    """Pull the counterparty (Donor) name / NRIC / address from a parties recital.
    Returns ``{'name', 'nric', 'address'}`` with '' for anything not found. The counterparty
    is the party signing opposite the student — the same person the agreement renders as the
    Foundation signatory + ``{{donor_name}}`` — so this pre-fills the Config party fields on
    import (fill-if-blank; the author reviews before deploy)."""
    out = {'name': '', 'nric': '', 'address': ''}
    if not preamble:
        return out
    m = _COUNTERPARTY_RE.search(preamble)
    if m:
        out['name'] = m.group('name').strip()
        out['nric'] = m.group('nric').strip()
        out['address'] = m.group('address').strip().rstrip(',').strip()
    return out
