"""TD-718 part 2 (owner 2026-11-24): a MySTR "application details" page is NOT an STR proof.

"Anyone can apply; so received application is a failed STR route. The student must submit salary
route." The MySTR portal's application details screen ("Maklumat Pemohon": No. MyKad, Nama, Umur,
Jantina, Status Perkahwinan, No. Telefon Bimbit, Alamat, Poskod, Bandar, Negeri) shows who APPLIED,
never whether STR was approved. It carries no status line, so it used to fall to the STR parser's
catch-all ``semakan_status`` and read amber 'unreadable', which ``str_not_breached`` lets pass. This
signature turns it into ``source_type='unknown'`` → ``wrong_type`` → red, and the salary route.

THE SIGNATURE — all must hold:
  * at least 3 of the application-only labels below, each as a LABEL: a whole line that is the label
    (spaces and case free), optionally followed by ":" and a value on the same line;
  * no "Status Permohonan Semasa" / "Status Permohonan STR" (the Semakan and dashboard status lines);
  * no approved or rejected token anywhere (``doc_parse._STR_DECIDED_RE``: Lulus, diluluskan, Ditolak…;
    a bare "berjaya" — "berjaya dihantar", sent — does not count, TD-718 R2);
  * none of the approval LETTER's markers ("Nama Penerima", "Layak STR"): a letter prints an address.

The not-yet-approved words of part 1 ("Permohonan Diterima", "Dalam Proses") do NOT keep a page out:
either way the STR fails and the salary route applies, so the page reads red as not an STR proof.

Guarded on every door: ``doc_parse._str_surface`` (the deterministic read) and
``vision.field_extraction._read_labelled_doc`` (after the Gemini read too, on the same OCR text), which
upload, the cockpit Re-run, the bulk ``reextract_documents``, the hourly sweep and the blockers re-read
all pass through. Pure; never raises.
"""
from __future__ import annotations

import re

_LABELS = (r'umur', r'jantina', r'status\s+perkahwinan', r'no\.?\s*telefon\s+bimbit',
           r'alamat', r'poskod', r'bandar', r'negeri')
# TD-718 R4: any horizontal space around the label and before the colon — a no-break space
# ("Umur\xa0:") or another Unicode space as OCR prints them. Never a line break: one label per line.
_HSPACE = r'[^\S\r\n]*'
_LABEL_RES = tuple(re.compile(r'^' + _HSPACE + lab + _HSPACE + r'(?::.*)?$', re.IGNORECASE | re.MULTILINE)
                   for lab in _LABELS)
_NOT_APPLICATION = re.compile(r'status\s+permohonan\s+(?:semasa|str)\b|nama\s+penerima|layak\s+str',
                              re.IGNORECASE)

#: The fewest application-only labels that make the signature.
MIN_LABELS = 3


def is_application_details(text: str) -> bool:
    """True when ``text`` (OCR) is a MySTR application details page — see the module docstring."""
    try:
        text = text or ''
        if _NOT_APPLICATION.search(text):
            return False
        # lazy: doc_parse imports this module. TD-718 R2: a bare "berjaya" ("berjaya dihantar") does
        # not keep a page out; Lulus / diluluskan / Kekal Kelulusan Asal / a rejected word still does.
        from .doc_parse import _STR_DECIDED_RE
        if _STR_DECIDED_RE.search(text):
            return False
        return sum(1 for rx in _LABEL_RES if rx.search(text)) >= MIN_LABELS
    except Exception:
        return False


def guard_str_source(doc_type: str, ex: dict, text: str) -> dict:
    """The read ``ex`` with its STR ``source_type`` set to 'unknown' when the OCR ``text`` is an
    application details page, whatever the reader (rules or Gemini) said. Any other read: unchanged."""
    fields = ex.get('fields') if isinstance(ex, dict) else None
    if doc_type != 'str' or ex.get('error') or not isinstance(fields, dict):
        return ex
    if fields.get('source_type') != 'unknown' and is_application_details(text):
        fields['source_type'] = 'unknown'
    return ex
