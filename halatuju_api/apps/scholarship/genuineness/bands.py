"""Shared probability → soft-status bands for document genuineness.

Calibrated on the 48-doc labelled results-slip corpus (2026-06-15): 46 genuine 0.56–0.80,
1 typed fake 0.04; crediting the visual QR/crest lifts genuine photos to ~0.80. The three
statuses map onto the vocabulary the verdict cap already reads ('likely_genuine' = no cap,
'low_confidence'/'suspect' = soft cap + caveat). Used by the signature scorer; the IC and
supporting-doc checks map their model verdict words to the same statuses directly.
"""
GENUINE_MIN = 0.70      # >= → genuine (no cap)
SUSPECT_MAX = 0.35      # <  → not_<type> (so few signatures it isn't recognisably that document)
# in between (0.35–0.70) → suspect (cropped / partial / not confidently genuine; reviewer confirms).

# The CANONICAL genuineness outcome — shared by EVERY document type, however it's derived
# (probability bands for the signature docs; a holistic model verdict for the IC / STR / EPF):
#   'genuine'    — a real official document of the expected type (no cap)
#   'suspect'    — the right kind of document but not confidently genuine (incomplete/cropped/fabricated)
#   'not_<type>' — not recognisably that document at all ('not_ic', 'not_birth_certificate', …)
# 'suspect' and 'not_<type>' get the SAME soft treatment (cap + officer flag); only the message differs.
_GENUINE = {'genuine', 'likely_genuine'}            # incl. the legacy 'likely_genuine'
_NOT_LEGACY = {'wrong_type', 'not_an_ic'}           # legacy "wrong document" values
#: MODEL_VERSION 1.8.0 (owner ruling A, 2026-10-26): an offer from a KNOWN public TVET issuer we have
#: not fingerprinted yet (`offer_issuers`). Stored as itself, read everywhere as NO SIGNAL — like an
#: unscored document: no genuineness step, no block, no official-document request; the reviewer
#: checks it by eye. ⚠ Deliberately not `not_checked`: a `not_` prefix reads as a wrong-type FAKE.
NOT_CHECKED = 'unchecked'


def band_for(probability: float) -> str:
    """Probability → canonical band: 'genuine' / 'suspect' / 'not_type' (the caller substitutes
    the doc type for 'not_type', e.g. 'not_birth_certificate')."""
    if probability >= GENUINE_MIN:
        return 'genuine'
    if probability < SUSPECT_MAX:
        return 'not_type'
    return 'suspect'


def stored_authenticity(vision_fields) -> dict:
    """TD-293 (2026-10-03): a document's stored ``authenticity`` block — ALWAYS a dict, ``{}`` when
    ``vision_fields`` or the block is anything else. The one reader for the old
    ``(vf.get('authenticity') or {})`` idiom, which guarded ``vision_fields`` and then assumed the
    block was a dict: a stored string there raised ``AttributeError`` and 500'd the officer's view."""
    a = vision_fields.get('authenticity') if isinstance(vision_fields, dict) else None
    return a if isinstance(a, dict) else {}


def stored_status(vision_fields) -> str:
    """TD-293: the stored genuineness status — ALWAYS a string, ``''`` when unscored OR malformed.

    ⚠ A MALFORMED VALUE READS AS NO SIGNAL — the same as a document never scored, which since
    TD-114 holds its fact at Probable and leaves the officer to look. It is never read as genuine
    and never as fake: we cannot read what the scorer said, so we claim neither. No document holds
    such a value (the lead's count, 2026-09-21: 0 of 1,356), and every writer stores a string."""
    s = stored_authenticity(vision_fields).get('status')
    return s if isinstance(s, str) else ''


#: Owner ruling B (2026-10-29, Matric/Diploma M4b): a higher-results page that is NOT the final result
#: (a semester result slip, the polytechnic portal page, a transcript with no completion status) is
#: stored NOT_CHECKED with one of these `doc_seen` codes — no genuineness signal, never a step — and
#: read as "the final results are not on file yet" (`higher_results.final_owed`).
NOT_FINAL_SEEN = frozenset({'matric_result_slip', 'poly_result_slip', 'poly_portal_page',
                            'matric_transcript_not_final', 'poly_transcript_not_final'})
#: What the student's and the reviewer's document serializer shows for such a page (not a `not_`
#: prefix: that reads as a wrong-type fake).
FINAL_OWED = 'final_owed'


def shown_status(raw, doc_type=None, doc_seen='') -> str:
    """`canonical_status`, except a NOT_CHECKED page that is not the final result reads `FINAL_OWED`
    (owner ruling B) so the Documents card can ask for the final academic transcript."""
    if (raw if isinstance(raw, str) else '').strip().lower() == NOT_CHECKED and doc_seen in NOT_FINAL_SEEN:
        return FINAL_OWED
    return canonical_status(raw, doc_type)


def canonical_status(raw, doc_type=None) -> str:
    """Fold any genuineness status — current OR legacy (likely_genuine / low_confidence / wrong_type
    / not_an_ic) — to the canonical enum: 'genuine' / 'suspect' / 'not_<type>' / '' (no signal). So
    existing stored authenticity (from live IC/supporting runs) keeps working without a backfill.
    TD-293: a non-string ``raw`` (a stored ``12345``) is no signal, never an ``AttributeError``."""
    s = (raw if isinstance(raw, str) else '').strip().lower()
    if not s or s == NOT_CHECKED:
        return ''          # no signal: unscored, or a known public issuer not checked (1.8.0)
    if s in _GENUINE:
        return 'genuine'
    if s.startswith('not_') or s in _NOT_LEGACY:
        return f'not_{doc_type}' if doc_type else (s if s.startswith('not_') else 'not_document')
    return 'suspect'   # low_confidence / suspect / review / anything else non-empty


def keep_stored_authenticity(doc, prior, new) -> None:
    """TD-407 — never overwrite a genuineness score with silence. A re-read rebuilds a document's
    ``vision_fields``; when it produced no FRESH ``authenticity`` — ``DOC_GENUINENESS_CHECK_ENABLED`` is
    off (a Cloud Run job carries only core env: corpus C4 wiped 16 scores this way, and the 2026-10-24
    re-reads 16 more), or the scorer gave no signal this time (an empty OCR, an AI outage) — the score
    stored on ``prior`` is carried into ``new`` and a WARNING says so. A fresh score always replaces it;
    a first read (nothing stored, the upload path) is untouched. Mutates ``new``; returns nothing."""
    stored = prior.get('authenticity') if isinstance(prior, dict) else None
    fresh = new.get('authenticity')
    if not isinstance(stored, dict) or (isinstance(fresh, dict) and fresh is not stored):
        return
    import logging
    from django.conf import settings
    new['authenticity'] = stored
    why = ('the re-read gave no genuineness signal' if getattr(settings, 'DOC_GENUINENESS_CHECK_ENABLED', False)
           else 'DOC_GENUINENESS_CHECK_ENABLED is off')
    logging.getLogger('apps.scholarship.vision').warning(
        'TD-407: kept the stored genuineness score of document %s (%s)', getattr(doc, 'id', None), why)


def needs_attention(raw, doc_type=None) -> bool:
    """Does this genuineness status warrant the soft cap + officer flag? — anything non-empty
    that isn't 'genuine'."""
    return canonical_status(raw, doc_type) not in ('', 'genuine')
