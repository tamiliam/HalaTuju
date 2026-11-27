"""OCR-13/14: the UiTM, UUM, UM, UPSI, UNIMAS, UTHM, UKM, UTeM, USM, UMK and UniSZA branches of `offer_parse.diagnose`, here
rather than in `offer_parse` (its 600-line cap); UMPSA's (OCR-14b) and UniMAP's (OCR-14b-2) live in their own modules (`diagnose_umpsa`, `diagnose_unimap`). No behaviour change in the move (UiTM, UUM). `diagnose` passes each result through
`offer_parse._rules_exit` (Asasi)."""
from __future__ import annotations


def diagnose_uitm(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None) -> dict:
    """The UiTM branch of `diagnose` (OCR-13 phase 2): ONLY a digital letter's page-1 layout can lock, so a scan
    (no layout) refuses with guard ``no_layout``. In this order: the drawn page texts (`page_texts_refusal`);
    `read_uitm`; the owner phrases on page 1's layout (``owner_words_missing``); the whole letter's status and
    withdrawal words (`offer_parse_uitm.letter_refusal`); a letter outside Latin (``foreign_letters``); the name
    standing as its own words in the plain layer (``name_not_plain``); last, the later pages
    (`offer_parse_uitm.later_pages_refusal`). `diagnose` passes the result through `_rules_exit` (Asasi)."""
    from .offer_parse import _SPACES, _ZERO_WIDTH, PARSER_VERSION
    from .offer_owner_words import missing
    from .offer_parse_uitm import LANE, later_pages_refusal, letter_refusal, read_uitm
    from .offer_parse_university import name_in_plain
    from .offer_ums_refusal import foreign_letters, page_texts_refusal
    if out['portal']:
        return out
    if not page1_layout.strip():
        out['guard'] = 'no_layout'
        return out
    if not page1_text.strip():
        out['guard'] = 'no_plain_layer'
        return out
    pages = [_SPACES.sub(' ', _ZERO_WIDTH.sub('', t or '')) for t in (page_texts or ())]
    fields, reason = read_uitm(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    early = page_texts_refusal(pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, page1_layout, text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or letter_refusal(text)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    if not reason and not name_in_plain(fields['candidate_name'], page1_text, page1_layout):
        reason = 'name_not_plain'
    if not reason:
        from .offer_parse_uitm import printed_date
        reason = later_pages_refusal(pages[1:], fields['candidate_nric'], printed_date(page1_layout))
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'uitm', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


def diagnose_uum(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None) -> dict:
    """The UUM branch of `diagnose` (OCR-13 phase 3), in `diagnose_uitm`'s order: a scan refuses (``no_layout``);
    the drawn page texts; `read_uum`; the owner phrases; the whole letter (`offer_parse_uum.uum_letter_refusal`: status
    words, ANY IC-like number, withdrawal words); ``foreign_letters``; ``name_not_plain``; any IC-like number in
    page 1's plain layer (``ic_printed``); last, the later pages. UUM prints no IC: the lock carries a blank one
    (`offer_exact.ISSUER_PRINTS_NO_IC`). `diagnose` passes the result through `_rules_exit` (Asasi)."""
    from .offer_parse import _SPACES, _ZERO_WIDTH, PARSER_VERSION
    from .offer_owner_words import missing
    from .offer_parse_university import name_in_plain
    from .offer_parse_uum import LANE, ic_printed, printed_date, read_uum, uum_later_pages, uum_letter_refusal
    from .offer_ums_refusal import foreign_letters, page_texts_refusal
    if out['portal']:
        return out
    if not page1_layout.strip():
        out['guard'] = 'no_layout'
        return out
    if not page1_text.strip():
        out['guard'] = 'no_plain_layer'
        return out
    pages = [_SPACES.sub(' ', _ZERO_WIDTH.sub('', t or '')) for t in (page_texts or ())]
    fields, reason = read_uum(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    early = page_texts_refusal(pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, page1_layout, text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or uum_letter_refusal(text)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    if not reason and not name_in_plain(fields['candidate_name'], page1_text, page1_layout):
        reason = 'name_not_plain'
    if not reason and (ic_printed(page1_text) or any(ic_printed(p) for p in pages[:1])):
        reason = 'ic_printed'
    if not reason:
        reason = uum_later_pages(pages[1:], fields['programme'], printed_date(page1_layout))
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'uum', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


def diagnose_um(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None) -> dict:
    """The UM branch of `diagnose` (OCR-13 phase 4), in `diagnose_uitm`'s order: a scan refuses (``no_layout``);
    the drawn page texts; `read_um`; the owner phrases; the whole letter (`offer_parse_um.um_letter_refusal`);
    ``foreign_letters``; ``name_not_plain``; last, the later pages (`offer_parse_um.um_later_pages`). UM prints the
    IC, so `offer_exact.exact_read`'s IC guard applies as on every other lane. `diagnose` passes the result through
    `_rules_exit` (Asasi)."""
    from .offer_parse import _SPACES, _ZERO_WIDTH, PARSER_VERSION
    from .offer_owner_words import missing
    from .offer_parse_um import LANE, read_um, um_later_pages, um_letter_refusal, um_printed_date
    from .offer_parse_university import name_in_plain
    from .offer_ums_refusal import foreign_letters, page_texts_refusal
    if out['portal']:
        return out
    if not page1_layout.strip():
        out['guard'] = 'no_layout'
        return out
    if not page1_text.strip():
        out['guard'] = 'no_plain_layer'
        return out
    pages = [_SPACES.sub(' ', _ZERO_WIDTH.sub('', t or '')) for t in (page_texts or ())]
    fields, reason = read_um(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    early = page_texts_refusal(pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, page1_layout, text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or um_letter_refusal(text)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    if not reason and not name_in_plain(fields['candidate_name'], page1_text, page1_layout):
        reason = 'name_not_plain'
    if not reason:
        reason = um_later_pages(pages[1:], fields['candidate_nric'], fields['programme'],
                                um_printed_date(page1_layout))
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'um', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


def diagnose_upsi(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None) -> dict:
    """The UPSI branch of `diagnose` (OCR-13 phase 5), in `diagnose_uum`'s order: a scan refuses (``no_layout``);
    the drawn page texts; `read_upsi`; the owner phrases; the whole letter (`offer_parse_upsi.upsi_letter_refusal`:
    status words, ANY IC-like number, withdrawal words); ``foreign_letters``; ``name_not_plain``; any IC-like number
    in page 1's plain layer (``ic_printed``); last, the later pages. UPSI prints no IC (the matric is not one): the
    lock carries a blank IC (`offer_exact.ISSUER_PRINTS_NO_IC`). `diagnose` passes the result through `_rules_exit`."""
    from .offer_parse import _SPACES, _ZERO_WIDTH, PARSER_VERSION
    from .offer_owner_words import missing
    from .offer_parse_university import name_in_plain
    from .offer_parse_upsi import LANE, read_upsi, upsi_later_pages, upsi_letter_refusal, upsi_printed_date
    from .offer_parse_uum import ic_printed
    from .offer_ums_refusal import foreign_letters, page_texts_refusal
    if out['portal']:
        return out
    if not page1_layout.strip():
        out['guard'] = 'no_layout'
        return out
    if not page1_text.strip():
        out['guard'] = 'no_plain_layer'
        return out
    pages = [_SPACES.sub(' ', _ZERO_WIDTH.sub('', t or '')) for t in (page_texts or ())]
    fields, reason = read_upsi(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    early = page_texts_refusal(pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, page1_layout, text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or upsi_letter_refusal(text)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    if not reason and not name_in_plain(fields['candidate_name'], page1_text, page1_layout):
        reason = 'name_not_plain'
    if not reason and (ic_printed(page1_text) or any(ic_printed(p) for p in pages[:1])):
        reason = 'ic_printed'
    if not reason:
        reason = upsi_later_pages(pages[1:], fields['programme'], fields['programme_code'],
                                  upsi_printed_date(page1_layout))
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'upsi', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


def diagnose_unimas(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None) -> dict:
    """The UNIMAS branch of `diagnose` (OCR-14 phase 2), in `diagnose_upsi`'s order: a scan refuses (``no_layout``);
    the drawn page texts; `read_unimas`; the owner phrases; the whole letter
    (`offer_parse_unimas.unimas_letter_refusal`: status words, ANY IC-like number, withdrawal words);
    ``foreign_letters``; ``name_not_plain``; any IC-like number in page 1's plain layer (``ic_printed``); last, any
    later page (``later_page``: a UNIMAS letter is one page). UNIMAS prints no IC (the matric is not one): the lock
    carries a blank IC (`offer_exact.ISSUER_PRINTS_NO_IC`). `diagnose` passes the result through `_rules_exit`."""
    from .offer_parse import _SPACES, _ZERO_WIDTH, PARSER_VERSION
    from .offer_owner_words import missing
    from .offer_parse_unimas import LANE, read_unimas, unimas_later_pages, unimas_letter_refusal, unimas_portal
    from .offer_parse_university import name_in_plain
    from .offer_parse_uum import ic_printed
    from .offer_ums_refusal import foreign_letters, page_texts_refusal
    out['portal'] = unimas_portal(text)            # the greeting's "Tahniah!" is no portal tell; any other is
    if out['portal']:
        return out
    if not page1_layout.strip():
        out['guard'] = 'no_layout'
        return out
    if not page1_text.strip():
        out['guard'] = 'no_plain_layer'
        return out
    pages = [_SPACES.sub(' ', _ZERO_WIDTH.sub('', t or '')) for t in (page_texts or ())]
    fields, reason = read_unimas(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    early = page_texts_refusal(pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, page1_layout, text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or unimas_letter_refusal(text)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    if not reason and not name_in_plain(fields['candidate_name'], page1_text, page1_layout):
        reason = 'name_not_plain'
    if not reason and (ic_printed(page1_text) or any(ic_printed(p) for p in pages[:1])):
        reason = 'ic_printed'
    if not reason:
        reason = unimas_later_pages(pages[1:])
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'unimas', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


def diagnose_uthm(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None) -> dict:
    """The UTHM branch of `diagnose` (OCR-14 phase 3), in `diagnose_unimas`'s order: a portal page refuses (the
    plain `offer_parse._PORTAL_TELL`, no excuse: the UTHM greeting "Tahniah diucapkan" is not a tell); a scan
    refuses (``no_layout``); the drawn page texts; `read_uthm`; the owner phrases; the whole letter
    (`offer_parse_uthm.uthm_letter_refusal`: status words, ANY IC-like number, withdrawal words); ``foreign_letters``;
    ``name_not_plain``; any IC-like number in page 1's plain layer or any page text (``ic_printed``); last, any later
    page with text (``later_page``). UTHM prints no IC (the matric is not one): the lock carries a blank IC
    (`offer_exact.ISSUER_PRINTS_NO_IC`). `diagnose` passes the result through `_rules_exit`."""
    from .offer_parse import _PORTAL_TELL, _SPACES, _ZERO_WIDTH, PARSER_VERSION
    from .offer_owner_words import missing
    from .offer_parse_university import name_in_plain
    from .offer_parse_uthm import LANE, read_uthm, uthm_later_pages, uthm_letter_refusal
    from .offer_parse_uum import ic_printed
    from .offer_ums_refusal import foreign_letters, page_texts_refusal
    out['portal'] = bool(_PORTAL_TELL.search(text or ''))
    if out['portal']:
        return out
    if not page1_layout.strip():
        out['guard'] = 'no_layout'
        return out
    if not page1_text.strip():
        out['guard'] = 'no_plain_layer'
        return out
    pages = [_SPACES.sub(' ', _ZERO_WIDTH.sub('', t or '')) for t in (page_texts or ())]
    fields, reason = read_uthm(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    early = page_texts_refusal(pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, page1_layout, text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or uthm_letter_refusal(text)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    if not reason and not name_in_plain(fields['candidate_name'], page1_text, page1_layout):
        reason = 'name_not_plain'
    if not reason and (ic_printed(page1_text) or any(ic_printed(p) for p in pages)):
        reason = 'ic_printed'
    if not reason:
        reason = uthm_later_pages(pages[1:])
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'uthm', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


def diagnose_ukm(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None) -> dict:
    """The UKM branch of `diagnose` (OCR-14 phase 4), in `diagnose_uthm`'s order: a portal page refuses
    (`offer_parse_ukm.ukm_portal`: the one "Portal Semakan Kemasukan ke UKM" sentence every letter prints is no
    tell; any other is); a scan refuses (``no_layout``); the drawn page texts; `read_ukm`; the owner phrases; the
    whole letter (`offer_parse_ukm.ukm_letter_refusal`: status words, any IC-like number but the read IC, withdrawal
    words); ``foreign_letters``; ``name_not_plain``; the read IC not printed exactly once in page 1's plain layer
    (``ic_not_plain``); any other IC-like number in page 1's plain layer or any page text (``ic_printed``); last, any
    later page with text (``later_page``). UKM PRINTS the IC: the lock carries it (source ``label``) and the usual IC
    guard applies (`offer_exact.exact_read`). `diagnose` passes the result through `_rules_exit`."""
    from .offer_parse import _SPACES, _ZERO_WIDTH, PARSER_VERSION
    from .offer_owner_words import missing
    from .offer_parse_ukm import LANE, read_ukm, ukm_ic_copies, ukm_ic_elsewhere, ukm_later_pages, ukm_letter_refusal
    from .offer_parse_ukm import ukm_portal
    from .offer_parse_university import name_in_plain
    from .offer_ums_refusal import foreign_letters, page_texts_refusal
    out['portal'] = ukm_portal(text)
    if out['portal']:
        return out
    if not page1_layout.strip():
        out['guard'] = 'no_layout'
        return out
    if not page1_text.strip():
        out['guard'] = 'no_plain_layer'
        return out
    pages = [_SPACES.sub(' ', _ZERO_WIDTH.sub('', t or '')) for t in (page_texts or ())]
    fields, reason = read_ukm(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    nric = (fields or {}).get('candidate_nric', '')
    early = page_texts_refusal(pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, page1_layout, text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or ukm_letter_refusal(text, nric)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    if not reason and not name_in_plain(fields['candidate_name'], page1_text, page1_layout):
        reason = 'name_not_plain'
    if not reason and ukm_ic_copies(page1_text, nric) != 1:
        reason = 'ic_not_plain'
    if not reason and (ukm_ic_elsewhere(page1_text, nric) or any(ukm_ic_elsewhere(p, nric) for p in pages)):
        reason = 'ic_printed'
    if not reason:
        reason = ukm_later_pages(pages[1:])
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'ukm', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


def diagnose_utem(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None) -> dict:
    """The UTeM branch of `diagnose` (OCR-14 phase 5), in `diagnose_ukm`'s order: a portal page refuses (the plain
    `offer_parse._PORTAL_TELL`, no excuse); a scan refuses (``no_layout``); the drawn page texts (no excuse: a page
    that draws no text refuses, ``hidden_page``); `read_utem`; the owner phrases; the whole letter
    (`offer_parse_utem.utem_letter_refusal`: status words, any IC-like number but the read IC, withdrawal words but
    the one genuine note); ``foreign_letters``; ``name_not_plain``; the read IC not printed exactly once in page 1's
    plain layer (``ic_not_plain``); any other IC-like number in page 1's plain layer or any page text
    (``ic_printed``); last, any later page with text (``later_page``). UTeM PRINTS the IC with no label: the lock
    carries it as source ``other``, so `offer_exact.exact_read`'s IC guard keeps it only when it is exactly the
    profile IC. `diagnose` passes the result through `_rules_exit`."""
    from .offer_parse import _PORTAL_TELL, _SPACES, _ZERO_WIDTH, PARSER_VERSION
    from .offer_owner_words import missing
    from .offer_parse_university import name_in_plain
    from .offer_parse_utem import LANE, read_utem, utem_ic_copies, utem_ic_elsewhere, utem_later_pages
    from .offer_parse_utem import utem_letter_refusal
    from .offer_ums_refusal import foreign_letters, page_texts_refusal
    out['portal'] = bool(_PORTAL_TELL.search(text or ''))
    if out['portal']:
        return out
    if not page1_layout.strip():
        out['guard'] = 'no_layout'
        return out
    if not page1_text.strip():
        out['guard'] = 'no_plain_layer'
        return out
    pages = [_SPACES.sub(' ', _ZERO_WIDTH.sub('', t or '')) for t in (page_texts or ())]
    fields, reason = read_utem(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    nric = (fields or {}).get('candidate_nric', '')
    early = page_texts_refusal(pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, page1_layout, text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or utem_letter_refusal(text, nric)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    if not reason and not name_in_plain(fields['candidate_name'], page1_text, page1_layout):
        reason = 'name_not_plain'
    if not reason and utem_ic_copies(page1_text, nric) != 1:
        reason = 'ic_not_plain'
    if not reason and (utem_ic_elsewhere(page1_text, nric) or any(utem_ic_elsewhere(p, nric) for p in pages)):
        reason = 'ic_printed'
    if not reason:
        reason = utem_later_pages(pages[1:])
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'utem', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


def diagnose_usm(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None) -> dict:
    """The USM branch of `diagnose` (OCR-14 phase 6), in `diagnose_utem`'s order: a portal page refuses (the plain
    `offer_parse._PORTAL_TELL`, no excuse); a scan refuses (``no_layout``); the drawn page texts (no excuse: a page
    that draws no text refuses, ``hidden_page``); `read_usm`; the owner phrases; the whole letter
    (`offer_parse_usm.usm_letter_refusal`: status words, any IC-like number but the read IC, withdrawal words but
    the one genuine note); ``foreign_letters``; ``name_not_plain`` (on the plain layer less its one "NAMA :" row,
    `offer_parse_usm.usm_head_plain`); the read IC not printed exactly once in page 1's
    plain layer (``ic_not_plain``); any other IC-like number in page 1's plain layer or any page text
    (``ic_printed``); last, any later page with text (``later_page``). USM PRINTS the IC with no label: the lock
    carries it as source ``other``, so `offer_exact.exact_read`'s IC guard keeps it only when it is exactly the
    profile IC. `diagnose` passes the result through `_rules_exit`."""
    from .offer_parse import _PORTAL_TELL, _SPACES, _ZERO_WIDTH, PARSER_VERSION
    from .offer_owner_words import missing
    from .offer_parse_university import name_in_plain
    from .offer_parse_usm import LANE, read_usm, usm_ic_copies, usm_ic_elsewhere, usm_later_pages
    from .offer_parse_usm import usm_head_plain, usm_letter_refusal
    from .offer_ums_refusal import foreign_letters, page_texts_refusal
    out['portal'] = bool(_PORTAL_TELL.search(text or ''))
    if out['portal']:
        return out
    if not page1_layout.strip():
        out['guard'] = 'no_layout'
        return out
    if not page1_text.strip():
        out['guard'] = 'no_plain_layer'
        return out
    pages = [_SPACES.sub(' ', _ZERO_WIDTH.sub('', t or '')) for t in (page_texts or ())]
    fields, reason = read_usm(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    nric = (fields or {}).get('candidate_nric', '')
    early = page_texts_refusal(pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, page1_layout, text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or usm_letter_refusal(text, nric)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    name = (fields or {}).get('candidate_name', '')
    if not reason and not name_in_plain(name, usm_head_plain(page1_text, name), page1_layout):
        reason = 'name_not_plain'                # USM prints the name twice: the table row is taken out once
    if not reason and usm_ic_copies(page1_text, nric) != 1:
        reason = 'ic_not_plain'
    if not reason and (usm_ic_elsewhere(page1_text, nric) or any(usm_ic_elsewhere(p, nric) for p in pages)):
        reason = 'ic_printed'
    if not reason:
        reason = usm_later_pages(pages[1:])
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'usm', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


def diagnose_umk(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None) -> dict:
    """The UMK branch of `diagnose` (OCR-14 phase 7), in `diagnose_ukm`'s order: a portal page refuses (the plain
    `offer_parse._PORTAL_TELL`, no excuse); a scan refuses (``no_layout``); the drawn page texts (no excuse: a page
    that draws no text refuses, ``hidden_page``); `read_umk`; the owner phrases; the whole letter
    (`offer_parse_umk.umk_letter_refusal`: status words, any IC-like number but the read IC, withdrawal words);
    ``foreign_letters``; ``name_not_plain``; the read IC not printed exactly once in page 1's plain layer
    (``ic_not_plain``); any other IC-like number in page 1's plain layer or any page text (``ic_printed``); last,
    any later page with text (``later_page``, no excuse: owner decision 26 Nov). UMK PRINTS the IC with its label:
    the lock carries it (source ``label``) and the usual IC guard applies (`offer_exact.exact_read`). `diagnose`
    passes the result through `_rules_exit`."""
    from .offer_parse import _PORTAL_TELL, _SPACES, _ZERO_WIDTH, PARSER_VERSION
    from .offer_owner_words import missing
    from .offer_parse_umk import LANE, read_umk, umk_ic_copies, umk_ic_elsewhere, umk_later_pages, umk_letter_refusal
    from .offer_parse_university import name_in_plain
    from .offer_ums_refusal import foreign_letters, page_texts_refusal
    out['portal'] = bool(_PORTAL_TELL.search(text or ''))
    if out['portal']:
        return out
    if not page1_layout.strip():
        out['guard'] = 'no_layout'
        return out
    if not page1_text.strip():
        out['guard'] = 'no_plain_layer'
        return out
    pages = [_SPACES.sub(' ', _ZERO_WIDTH.sub('', t or '')) for t in (page_texts or ())]
    fields, reason = read_umk(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    nric = (fields or {}).get('candidate_nric', '')
    early = page_texts_refusal(pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, page1_layout, text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or umk_letter_refusal(text, nric)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    if not reason and not name_in_plain(fields['candidate_name'], page1_text, page1_layout):
        reason = 'name_not_plain'
    if not reason and umk_ic_copies(page1_text, nric) != 1:
        reason = 'ic_not_plain'
    if not reason and (umk_ic_elsewhere(page1_text, nric) or any(umk_ic_elsewhere(p, nric) for p in pages)):
        reason = 'ic_printed'
    if not reason:
        reason = umk_later_pages(pages[1:])
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'umk', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


def diagnose_unisza(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None) -> dict:
    """The UniSZA branch of `diagnose` (OCR-14 phase 8), in `diagnose_umk`'s order: a portal page refuses (the plain
    `offer_parse._PORTAL_TELL`, no excuse); a scan refuses (``no_layout``); the drawn page texts (no excuse: a page
    that draws no text refuses, ``hidden_page``); `read_unisza`; the owner phrases; the whole letter
    (`offer_parse_unisza.unisza_letter_refusal`: status words, any IC-like number but the read IC, withdrawal words,
    with NO note excused: owner decision 26 Nov); ``foreign_letters``; ``name_not_plain``; the read IC not printed
    exactly once in page 1's plain layer (``ic_not_plain``); any other IC-like number in page 1's plain layer or any
    page text (``ic_printed``); last, any later page with text (``later_page``, no excuse). UniSZA PRINTS the IC with
    no label: the lock carries it as source ``other``, so `offer_exact.exact_read`'s IC guard keeps it only when it
    is exactly the profile IC. `diagnose` passes the result through `_rules_exit`."""
    from .offer_parse import _PORTAL_TELL, _SPACES, _ZERO_WIDTH, PARSER_VERSION
    from .offer_owner_words import missing
    from .offer_parse_unisza import LANE, read_unisza, unisza_ic_copies, unisza_ic_elsewhere, unisza_later_pages
    from .offer_parse_unisza import unisza_letter_refusal
    from .offer_parse_university import name_in_plain
    from .offer_ums_refusal import foreign_letters, page_texts_refusal
    out['portal'] = bool(_PORTAL_TELL.search(text or ''))
    if out['portal']:
        return out
    if not page1_layout.strip():
        out['guard'] = 'no_layout'
        return out
    if not page1_text.strip():
        out['guard'] = 'no_plain_layer'
        return out
    pages = [_SPACES.sub(' ', _ZERO_WIDTH.sub('', t or '')) for t in (page_texts or ())]
    fields, reason = read_unisza(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    nric = (fields or {}).get('candidate_nric', '')
    early = page_texts_refusal(pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, page1_layout, text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or unisza_letter_refusal(text, nric)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    if not reason and not name_in_plain(fields['candidate_name'], page1_text, page1_layout):
        reason = 'name_not_plain'
    if not reason and unisza_ic_copies(page1_text, nric) != 1:
        reason = 'ic_not_plain'
    if not reason and (unisza_ic_elsewhere(page1_text, nric) or any(unisza_ic_elsewhere(p, nric) for p in pages)):
        reason = 'ic_printed'
    if not reason:
        reason = unisza_later_pages(pages[1:])
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'unisza', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


def diagnose_umpsa(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None) -> dict:
    """The UMPSA branch of `diagnose` (OCR-14b-1): `offer_parse_umpsa.diagnose_umpsa` (its own module, this file's
    600-line cap)."""
    from .offer_parse_umpsa import diagnose_umpsa as branch
    return branch(out, text, page1_text, page1_layout, page_texts)


def diagnose_unimap(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None,
                    blank_page2: bool = False) -> dict:
    """The UniMAP branch of `diagnose` (OCR-14b-2): `offer_parse_unimap.diagnose_unimap` (its own module, this
    file's 600-line cap). ``blank_page2``: the bytes proved page 2 fully blank (OCR-14b-3)."""
    from .offer_parse_unimap import diagnose_unimap as branch
    return branch(out, text, page1_text, page1_layout, page_texts, blank_page2)
