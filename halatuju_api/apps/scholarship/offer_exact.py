"""The Exact offer read — the ONE entry point for the fixed-format reader (offer exact-read S5, 2026-11-03).

`vision._run_field_extraction_impl` (upload, Re-run, sweep, `reextract_documents`, `release-decisions`) calls
`exact_offer_read`; the eval (`offer_replay`, `offer_parse_check`) calls `exact_read` with what production
would derive. Each returns the stored-read dict, or None (→ the AI reader, `offer_reader`). Three steps:

  1. **Parse** (`offer_parse.parse_govt_offer`) the text production holds. The identity comes from PAGE 1
     only (owner rule 2026-11-01), from the SAME source as the body (review H1):
       * the text is a digital PDF's own text layer → page 1's layer; when page 1 has NO usable layer (a
         scanned page 1 in front of digital pages) there is no page-1 identity to read → None (review H2);
         and when page 1's identity and the whole layer's disagree → None;
       * otherwise (a photo, a scan: Vision read page 1 only) → that text itself, never a PDF layer.
  2. **The IC guard** (`offer_ic.guard_nric`, exactly as on the AI path, with the profile IC and the page-1
     text): the parser labels its IC source (`label` for "No. Kad Pengenalan:", "K/P:", the polytechnic
     "NAME (IC)" line; `other` for the first-IC-anywhere fallback, corroborate-only). **A blanked IC means NO
     lock**: a blank IC merged over a prior read would keep the prior AI number under an "Exact" chip, and
     the AI read has its own guard. No text-layer backstop here (the parser either read an IC or did not lock).
     The one exception (OCR-13/14, owner): a lane whose issuer prints no IC (`ISSUER_PRINTS_NO_IC`) locks with
     the IC blank, as its AI read stores it, and refuses if its lock carries one.
  3. **The merge** over the prior read. The parser OWNS the identity and shape keys (`OWNED`) and writes them
     whole, blank included, so a stale AI campus / code / IC source / address / venue cannot survive under an
     "Exact" chip (review L2). On a GOVERNMENT-family lock the reporting date (with its label) and the offer
     date keep merge-preserve (decision 2026-07-10): a blank keeps the prior value — the reporting-date bonus
     depends on it — and so does a parser date `pathway_engine.parse_reporting_date` cannot read when the prior
     one it can (M4). So does a UNIVERSITY rules-lane lock, except for the fields its lane NEVER reads by design
     (`NEVER_READ`, OCR-14 review r2: UNIMAS prints no reporting date; UMK's head date is not proven to be the
     offer date; UiTM prints no offer date): those are written blank, so no earlier AI date survives under a
     deterministic capture. Every other lane and field merges exactly as before (a live lane must not change).
"""
from __future__ import annotations

import logging

from . import offer_parse_uitm, offer_parse_umk, offer_parse_unimas

logger = logging.getLogger(__name__)

#: The keys the parser owns — written whole on a lock, blank or not. The last five are AI-only fields the
#: parser never reads (review L2): blank under an Exact read; every reader takes them with `or ''`.
OWNED = ('candidate_name', 'candidate_nric', 'candidate_nric_source', 'programme', 'programme_code',
         'institution', 'campus', 'stream', 'intake', 'issuer', '_offer_parser_version',
         'candidate_address', 'reporting_venue', 'aliran', 'bidang_pengkhususan', 'elektif')
#: OCR-13 (owner, 26 Nov: "Lock without IC" for UUM, "Same as UUM" for UPSI; OCR-14, owner 26 Nov: "Same as UUM"
#: for UNIMAS and UTHM; no other): the rules lanes whose issuer prints NO IC on the letter.
#: Only these may lock with a blank IC, and they must: a lock on such a lane that carries an IC refuses. The
#: blank IC is stored as the AI read stores it ('' and source 'none'): `pathway_engine._ic_status` reads it as
#: 'unreadable' (never 'match'), the same for both readers. Every other lane keeps "a blanked IC means NO lock".
ISSUER_PRINTS_NO_IC = frozenset({'ua:UUM', 'ua:UPSI', 'ua:UNIMAS', 'ua:UTHM'})
#: Merge-preserve: the parser's value wins only when it read one (the label travels with its date).
PRESERVED = (('reporting_date', 'reporting_date_label'), ('offer_date',))
#: OCR-14 review r2: per rules lane, the `PRESERVED` fields its reader NEVER reads by design (it always writes them
#: blank). Only these are written blank over the prior AI read; every other lane and field keeps merge-preserve
#: as before review r1 (a live lane's kept AI date must not move a genuineness band).
NEVER_READ = {offer_parse_unimas.LANE: frozenset({'reporting_date', 'reporting_date_label'}),   # UNIMAS prints no reporting date
              offer_parse_umk.LANE: frozenset({'offer_date'}),     # the head TARIKH is a print date, never stored
              offer_parse_uitm.LANE: frozenset({'offer_date'})}    # UiTM prints no offer date (offer_parse_uitm, always '')


def pdf_layers(image, content_type='') -> tuple:
    """(the whole usable text layer, page 1's usable layer) of a digital PDF — what `vision.ocr_document_full`
    reads first — or ('', '') for a photo, a scan or no image."""
    if image is None:
        return '', ''
    from . import vision
    from .pdf_pages import pdf_page_texts, pdf_text_layer, usable_text_layer
    if not vision._is_pdf(content_type, image):
        return '', ''
    pages = pdf_page_texts(image, 1)
    return usable_text_layer(pdf_text_layer(image)), (usable_text_layer(pages[0]) if pages else '')


def page1_text_layer(image, content_type='') -> str:
    """A digital PDF's page-1 text layer ('' for a photo, a scan, or no usable layer)."""
    return pdf_layers(image, content_type)[1]


def _reads(date) -> bool:
    """True when `pathway_engine.parse_reporting_date` reads ``date`` (a stored value that is not a string
    — a damaged record — reads as no date, never an exception up through `vision`)."""
    from .pathway_engine import parse_reporting_date
    return isinstance(date, str) and parse_reporting_date(date) is not None


def merge_over(prior_fields, govt: dict, rules_lane: str = '') -> dict:
    """The lock merged over the prior read: `OWNED` whole, `PRESERVED` only where the parser read it — and a
    reporting date only when it parses, or the prior one does not (review M4). The fields ``rules_lane`` never
    reads (`NEVER_READ`, OCR-14 review r2) are written blank, always: no AI date under a deterministic read."""
    out = dict(prior_fields) if isinstance(prior_fields, dict) else {}
    out.update({k: govt.get(k, '') or '' for k in OWNED})
    never = NEVER_READ.get(rules_lane or '', frozenset())
    out.update({k: '' for group in PRESERVED for k in group if k in never})
    for group in PRESERVED:
        if group[0] in never:
            continue
        mine = (govt.get(group[0]) or '').strip()
        if not mine:
            continue
        if group[0] == 'reporting_date' and not _reads(mine) and _reads(out.get('reporting_date')):
            continue
        out.update({k: govt.get(k, '') or '' for k in group})
    return out


def _lane_module(family: str):
    """The rules-lane reader module for a university family (`offer_parse.family_of`): 'ums', 'uitm', 'uum',
    'um', 'upsi' (OCR-13), 'unimas', 'uthm', 'ukm', 'utem', 'usm', 'umk' or 'unisza' (OCR-14), 'umpsa' (OCR-14b); None for any other family. Each module gives LANE,
    ``ink_targets`` and its reader."""
    if family == 'ums':
        from . import offer_parse_university as mod
        return mod
    if family == 'uitm':
        from . import offer_parse_uitm as mod
        return mod
    if family == 'uum':
        from . import offer_parse_uum as mod
        return mod
    if family == 'um':
        from . import offer_parse_um as mod
        return mod
    if family == 'upsi':
        from . import offer_parse_upsi as mod
        return mod
    if family == 'unimas':
        from . import offer_parse_unimas as mod
        return mod
    if family == 'uthm':
        from . import offer_parse_uthm as mod
        return mod
    if family == 'ukm':
        from . import offer_parse_ukm as mod
        return mod
    if family == 'utem':
        from . import offer_parse_utem as mod
        return mod
    if family == 'usm':
        from . import offer_parse_usm as mod
        return mod
    if family == 'umk':
        from . import offer_parse_umk as mod
        return mod
    if family == 'unisza':
        from . import offer_parse_unisza as mod
        return mod
    if family == 'umpsa':
        from . import offer_parse_umpsa as mod
        return mod
    return None


def _rules_family(text) -> str:
    """The university rules family `offer_parse.diagnose` reads ``text`` as ('ums', 'uitm', 'uum', 'um', 'upsi',
    'unimas', 'uthm', 'ukm', 'utem', 'usm', 'umk', 'unisza', 'umpsa'), else ''."""
    from .offer_parse import family_of
    fam = family_of(text)
    return fam if _lane_module(fam) is not None else ''


def _note_ums_refusal(why, text, reason: str) -> None:
    """Fill ``why`` (the caller's dict, or None) with a rules read's refusal (review round 2): the lane and
    ``read_<reason>`` ('read_no_layout', 'read_not_an_offer', 'read_empty:programme', ...), the same shape as
    `rules_lane_verdict`'s ``rules_fallback``. A letter with the UMS title (as before), or one `family_of` reads
    as UiTM, UUM, UM, UPSI (OCR-13), UNIMAS, UTHM, UKM, UTeM, USM, UMK, UniSZA (OCR-14) or UMPSA (OCR-14b); a letter no rules lane exists for records nothing."""
    from .offer_parse_university import LANE, is_ums
    if not isinstance(why, dict):
        return
    if is_ums((text or '').upper()):
        why.update(lane=LANE, reason=f'read_{reason}')
    elif _rules_family(text) in ('uitm', 'uum', 'um', 'upsi', 'unimas', 'uthm', 'ukm', 'utem', 'usm', 'umk', 'unisza',
                                 'umpsa'):
        why.update(lane=_lane_module(_rules_family(text)).LANE, reason=f'read_{reason}')


def _guard_reason(d: dict) -> str:
    """`offer_parse.diagnose`'s refusal as one word: its guard, ``empty:<fields>``, 'portal' or 'no_title'."""
    if d.get('guard'):
        return d['guard']
    if d.get('empty_required'):
        return 'empty:' + ','.join(d['empty_required'])
    return 'portal' if d.get('portal') else 'no_title'


def exact_read(text, *, from_text_layer=False, page1_layer='', prior=None, profile_nric='',
               page1_layout='', why=None, page_texts=None) -> dict | None:
    """The Exact read from what production derived: ``from_text_layer`` — ``text`` is a digital PDF's own
    text layer — and that PDF's ``page1_layer`` (and its LAYOUT text, ``page1_layout``, which only the UMS
    family reads — OCR-first S1). ``prior`` is the stored ``vision_fields``. A university lock names its
    lane (``rules_lane``, e.g. 'ua:UMS') on the result and in ``offer_reader_inputs``; '' otherwise. When a
    UMS letter does not lock, ``why`` (a dict, if given) gets the lane and the reason (`_note_ums_refusal`),
    and the missing owner phrases' NUMBERS (``owner_words_missing``; never text). ``page_texts``: that PDF's
    drawn text per page (render-mode visible; `pdf_pages.pdf_page_texts`), read by the UMS family only (S1c
    owner words)."""
    from .offer_ic import guard_nric
    from .offer_parse import diagnose
    if from_text_layer and not (page1_layer or '').strip():
        _note_ums_refusal(why, text, 'no_page1_layer')
        return None                              # page 1 is a scan: no page-1 identity to read (H2)
    page1 = page1_layer if from_text_layer else ''
    d = diagnose(text, page1_text=page1 or None, page1_layout=page1_layout if from_text_layer else '',
                 page_texts=page_texts if from_text_layer else None)
    govt = d['locked']
    if govt is None:
        _note_ums_refusal(why, text, _guard_reason(d))
        if isinstance(why, dict) and why.get('reason') == 'read_owner_words_missing':
            why['owner_words_missing'] = list(d.get('owner_words_missing') or ())
        return None
    govt.pop('_family', None)
    lane = govt.pop('rules_lane', '')
    check = guard_nric(govt, profile_nric=profile_nric, page1_text=page1 or text or '')
    no_ic = lane in ISSUER_PRINTS_NO_IC
    if bool((govt.get('candidate_nric') or '').strip()) == no_ic:
        _note_ums_refusal(why, text, 'nric_guard')   # no IC read; or an IC on a lane whose issuer prints none
        return None
    if no_ic:
        govt['candidate_nric'], govt['candidate_nric_source'] = '', 'none'   # as the AI read stores it
    prior_fields = prior.get('fields') if isinstance(prior, dict) else None
    inputs = {'reader': 'deterministic', 'nric_check': check, **({'rules_lane': lane} if lane else {}),
              **({'nric_not_printed': True} if no_ic else {})}
    return {'fields': merge_over(prior_fields, govt, lane), 'warnings': [], 'error': '', 'capture': 'deterministic',
            'rules_lane': lane, 'offer_reader_inputs': inputs}


def ocr_first_lanes() -> tuple:
    """The rules lanes switched ON (OCR-first S1, 2026-11-19): the env var ``OCR_FIRST_LANES``, a comma
    list ("ua:UMS"); a test sets ``settings.OCR_FIRST_LANES``. Empty by default: every lane starts OFF and
    is switched on only after it passes Gate 1 on held-out letters (docs/plans/ocr-first-roadmap.md).
    Read here, not in settings/base.py, which is at its size allowance (`test_code_standards`)."""
    import os
    from django.conf import settings
    got = getattr(settings, 'OCR_FIRST_LANES', None)
    if got is None:
        got = os.environ.get('OCR_FIRST_LANES', '').split(',')
    return tuple(v.strip() for v in got if v and v.strip())


def rules_lane_verdict(ex) -> str:
    """Gate 2's last checks for a UNIVERSITY rules read (OCR-first S1): '' when its lane is switched on
    (`ocr_first_lanes`, default none) AND the catalogue pins exactly ONE course, at the letter's own level
    and at one campus (`offer_course_match.pinned_match`; the UPU code is extra evidence only). Else WHY
    the AI reads the letter instead: 'lane_off', 'match_<pinned_match reason>', or 'match_error' when the
    match raised (logged; review round 1). A government-family read (no ``rules_lane``) is unaffected."""
    lane = (ex or {}).get('rules_lane') or ''
    if not lane:
        return ''
    if lane not in ocr_first_lanes():
        return 'lane_off'
    try:
        from .offer_course_match import letter_institution, pinned_match, programme_line
        f = ex.get('fields') or {}
        reason, _match = pinned_match(programme_line(f.get('programme'), f.get('programme_code')),
                                      letter_institution(f.get('institution'), f.get('campus')), f.get('issuer') or '')
    except Exception:  # any fault in the match: the AI reads the letter, as it always could
        logger.exception('rules lane %s: the catalogue match failed; the AI reads the letter', lane)
        return 'match_error'
    return f'match_{reason}' if reason else ''


def _ums_family(text) -> bool:
    """True when `offer_parse.diagnose` reads ``text`` as a UMS letter (the SAME helper,
    `offer_parse.family_of`: no government family, and the UMS title). `exact_offer_read` uses it twice:
    with the lane off such a letter goes to the AI before the page-1 layout child or `read_ums` runs
    (recording 'lane_off', the reason `rules_lane_verdict` gave before review round 3); with the lane on,
    only such a letter gets the layout child (a government letter that also prints the UMS title does not)."""
    from .offer_parse import family_of
    return family_of(text) == 'ums'


def rules_lane_open(ex) -> bool:
    """True when a rules read may stand (`rules_lane_verdict` is ''); False sends the letter to the AI."""
    return rules_lane_verdict(ex) == ''


def exact_offer_read(text, *, prior=None, image=None, content_type='', profile_nric='',
                     page1_ocr='', why=None) -> dict | None:
    """Production's Exact read → ``{fields, warnings, error, capture, offer_reader_inputs}``, or None (→ AI).
    ``text`` came from the PDF's text layer exactly when it IS that layer (`vision.ocr_document_full`'s
    rule); ``page1_ocr`` is accepted for `vision._offer_context`'s shape and not read. ``why``: see
    `exact_read` (a UMS letter's refusal, for ``offer_reader_inputs['rules_fallback']``)."""
    if image is None and 'pdf' in (content_type or '').lower():
        _note_ums_refusal(why, text, 'no_pdf_bytes')
        return None                              # a PDF whose bytes are not here: no page 1 to read (H2)
    layer, page1 = pdf_layers(image, content_type)
    from_layer = bool(layer.strip()) and layer.strip() == (text or '').strip()
    mod = _lane_module(_rules_family(text))     # OCR-13: each university lane switched on by its own name
    lane_on = mod is not None and mod.LANE in ocr_first_lanes()
    if mod is not None and not lane_on:          # review round 3 (option A): no layout child, no reader
        if isinstance(why, dict):
            why.update(lane=mod.LANE, reason='lane_off')
        return None
    layout, page_texts = '', None
    if lane_on and from_layer and page1.strip():
        from .pdf_pages import MAX_LAYER_PAGES
        from .pdf_rules_pages import pdf_page1_layout, pdf_rules_page_texts
        layout, page_texts = pdf_page1_layout(image), pdf_rules_page_texts(image, MAX_LAYER_PAGES)
    ex = exact_read(text, from_text_layer=from_layer, page1_layer=page1, prior=prior, profile_nric=profile_nric,
                    page1_layout=layout, why=why, page_texts=page_texts)
    lane = (ex or {}).get('rules_lane') or ''
    if lane and lane in ocr_first_lanes() and from_layer:
        missing = _not_inked(ex, image, layout, lane)
        if missing:                              # S-visible 2: the visible page judges; the AI reads it
            if isinstance(why, dict):
                why.update(lane=lane, reason='not_inked', ink_missing=missing)
            return None
    return ex


def _not_inked(ex, image, layout, lane) -> list:
    """S-visible 2 (owner rule, 20 Nov: "the visible page always judges"): the labels (`pdf_ink.ink_missing`)
    of the owner phrases and values a rules lock on a TEXT-LAYER PDF relied on that leave no real ink on the
    rendered page 1; [] when every one does. A lane with no `ink_targets` reader, or any fault, refuses."""
    try:                                         # each lane's own `ink_targets` (OCR-13)
        from .pdf_ink import ink_missing, page1_ink
        families = ('ums', 'uitm', 'uum', 'um', 'upsi', 'unimas', 'uthm', 'ukm', 'utem', 'usm', 'umk', 'unisza', 'umpsa')
        mod = next((m for m in map(_lane_module, families) if m.LANE == lane), None)
        if mod is None:
            return ['no_targets']
        targets = (getattr(mod, 'ink_targets', None) or getattr(mod, 'uum_ink_targets', None)
                   or getattr(mod, 'um_ink_targets', None) or getattr(mod, 'upsi_ink_targets', None)
                   or getattr(mod, 'unimas_ink_targets', None) or getattr(mod, 'uthm_ink_targets', None)
                   or getattr(mod, 'ukm_ink_targets', None) or getattr(mod, 'utem_ink_targets', None)
                   or getattr(mod, 'usm_ink_targets', None) or getattr(mod, 'umk_ink_targets', None)
                   or getattr(mod, 'unisza_ink_targets', None)
                   or mod.umpsa_ink_targets)    # own names (one-home rule)
        phrases, values = targets(ex.get('fields'), layout)
        return ink_missing(page1_ink(image), phrases, values, lane=lane)   # a Type3 font: `TYPE3_LANES`
    except Exception:  # fail closed: the AI reads the letter, as it always could
        logger.exception('rules lane %s: the ink check failed; the AI reads the letter', lane)
        return ['ink_error']
