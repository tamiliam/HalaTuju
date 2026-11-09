"""The deterministic student-facing verdict on an extracted document (moved verbatim from
``vision.py``, audit sprint A3.1)."""

import re

from .names import name_match
from .schemas import _NAME_FIELD
from .match import address_match


def _any_field_filled(fields: dict) -> bool:
    for v in fields.values():
        if isinstance(v, str):
            if v.strip():
                return True
        elif v:
            return True
    return False


_DOC_NAME_LABEL_RE = re.compile(r'^\s*(?:NAMA(?:\s+CALON)?|NAME|CALON)\s*[:.\-]?\s+', re.IGNORECASE)


def _strip_name_label(s: str) -> str:
    """Drop a leaked field label ('NAMA :', 'NAME -', 'CALON ') that Gemini sometimes prepends
    to an extracted candidate name, so it doesn't pollute the token-set name match (it turned a
    genuine slip — 'NAMA : SANJANA A/P KALIANA KUMAR' vs the typed 'SANJANA A/P KALIANAKUMAR' —
    into a false name_mismatch). Requires a trailing separator+space, so a real name is untouched."""
    return _DOC_NAME_LABEL_RE.sub('', s or '').strip()


def _bank_verdict(fields, student_name) -> str:
    """Deterministic verdict for a bank statement (never hallucinated):
    'ok' | 'name_mismatch' (holder isn't the student) | 'incomplete' (a required field
    couldn't be read) | 'wrong_doc' (nothing bank-shaped). The holder MUST be the STUDENT
    — a hard rule — so the name is matched ONLY against the student, never a guardian."""
    bank = _strip_name_label(fields.get('bank_name') or '').strip()
    acct = (fields.get('account_number') or '').strip()
    holder = _strip_name_label(fields.get('account_holder') or '').strip()
    if not (bank or acct or holder):
        return 'wrong_doc'
    if not (bank and acct and holder):
        return 'incomplete'   # a bank statement, but a required field couldn't be read
    if name_match(holder, student_name or '') == 'mismatch':
        return 'name_mismatch'   # the account is in someone else's name
    return 'ok'


def doc_student_verdict(doc_type, fields, *, names, postcode='', city='', street='', check_address=False) -> str:
    """Deterministic verdict from the Gemini-extracted fields (never hallucinated):
    'ok' | 'name_mismatch' | 'address_mismatch' | 'incomplete' | 'wrong_doc'."""
    if doc_type == 'bank_statement':
        # The holder must be the STUDENT only — names[0] is the applicant (guardians follow).
        return _bank_verdict(fields, names[0] if names else '')
    if doc_type == 'income_support_doc':
        # V1: a supporting income doc NAMES THE EARNER (a working household member), not the
        # student — so we do NOT name-match it against the applicant (that would false-red a
        # genuine employer letter for the father). It must simply READ as a real support
        # document: some field (name / amount / issuer / kind) present. A blank/wrong image
        # reads nothing → 'wrong_doc', which does NOT clear the declared-income gap. Whether
        # the named person is the right earner is an officer/interview judgement, not a red.
        return 'ok' if _any_field_filled(fields) else 'wrong_doc'
    if not _any_field_filled(fields):
        return 'wrong_doc'   # nothing of the expected shape was found
    # Two doc kinds are held in a PARENT's name and must NEVER be name-checked against the student
    # here (the reference `names` are student + guardians only, so a genuine parent-name doc reads a
    # false 'name_mismatch' that loops the student with no useful coaching):
    #   • UTILITY BILL — an ADDRESS anchor in the account-holder parent's name (owner 2026-07-09,
    #     #130: a father's-name bill looped ~34× as 'name_mismatch'). Matches help_engine (bills
    #     un-name-checked) + doc_match_verdict (bills accept); a stranger's bill is still caught
    #     softly by utility_holder_unknown, which knows the declared parents.
    #   • STR — the recipient is a PARENT/earner; the proper HOUSEHOLD match (against every
    #     parent/guardian IC, on name OR nric) is done by income_engine.student_str_check, which is
    #     what the income VERDICT BAND and doc_match_verdict read — NOT this stored display verdict
    #     (owner 2026-07-09, #126: a Lulus Semakan in the declared mother's name read 'name_mismatch'
    #     though VIMALA matches the mother's IC + roster, panicking the student into junk re-uploads).
    #     A genuine recipient mismatch is still surfaced by student_str_check → str_recipient_mismatch.
    if doc_type not in ('water_bill', 'electricity_bill', 'str'):
        extracted_name = _strip_name_label(fields.get(_NAME_FIELD.get(doc_type, 'name')) or '')
        if extracted_name:
            matched = any(name_match(extracted_name, n) in ('match', 'partial') for n in names if n)
            if not matched:
                return 'name_mismatch'
    if check_address:
        addr = (fields.get('address') or '').strip()
        # Only a genuinely DIFFERENT home is flagged to the student; a soft 'unconfirmed'
        # (abbreviation / bilingual town / partial OCR) stays quiet — the officer sees amber.
        if addr and address_match(addr, postcode=postcode, city=city, street=street) == 'mismatch':
            return 'address_mismatch'
    return 'ok'
