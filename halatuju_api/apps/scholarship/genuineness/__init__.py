"""Document genuineness — one home for every "is this a genuine document?" check.

Per document type:
  * ic / parent_ic      → ic.ic_genuineness          (multimodal MyKad markers)
  * results_slip / cert → results_doc.signature_genuineness (probabilistic OCR signatures)
  * str / birth_cert /  → supporting_doc.doc_genuineness     (multimodal, doc-type rule)
    epf

All return a soft authenticity dict consumed by the verdict cap, the anomaly engine, and the
serializer. SOFT throughout — the reviewer is the authority. ``assess()`` is the single dispatch.
"""
from .bands import GENUINE_MIN, SUSPECT_MAX, band_for
from .ic import ic_genuineness
from .supporting_doc import doc_genuineness
from .results_doc import score_signatures, signature_genuineness, misfiled_as
from .salary_doc import salary_genuineness
from .electricity_doc import electricity_genuineness
from .water_doc import water_genuineness

__all__ = ['ic_genuineness', 'doc_genuineness', 'score_signatures', 'signature_genuineness',
           'misfiled_as', 'salary_genuineness', 'electricity_genuineness', 'water_genuineness',
           'band_for', 'GENUINE_MIN', 'SUSPECT_MAX', 'assess']


def assess(doc_type, *, image=None, content_type='', ocr_text='', has_qr=False, has_crest=False):
    """Single entry point → the soft authenticity dict for ``doc_type`` (or ``{}`` for an
    unsupported type / no signal). Callers supply whatever that type needs (an image for the
    multimodal checks; OCR text + visual flags for the results-slip signature scorer)."""
    if doc_type in ('ic', 'parent_ic'):
        return ic_genuineness(image, content_type)
    if doc_type in ('results_slip', 'certificate'):
        return signature_genuineness(ocr_text, has_qr=has_qr, has_crest=has_crest)
    if doc_type == 'offer_letter':
        # MODEL_VERSION 1.4.0: the offer is signature-scored purely by-score (no issuer anchor) →
        # genuine / suspect / not_offer_letter. Owner policy: only a genuine OFFICIAL public offer
        # qualifies — a cropped/thin (suspect) or non-official (not_offer_letter) read stays
        # not-genuine so the submission gate + pathway verdict act on it. No holistic image rescue.
        return signature_genuineness(ocr_text, doc_type='offer_letter')
    if doc_type == 'salary_slip':
        # Signature-scored off the OCR text (statutory payroll grammar, not a letterhead) →
        # genuine {private/govt/singapore/gig} / suspect {informal} / not_salary {MyKad/empty}.
        # See salary_doc.py + docs/scholarship/salary-signature-model.md.
        return salary_genuineness(ocr_text)
    if doc_type == 'electricity_bill':
        # Signature-scored off the OCR text (issuer identity + Malay bill grammar) → genuine {tnb/…} /
        # suspect {thin/cropped} / not_electricity_bill {MyKad / water bill / junk in the slot}.
        # See electricity_doc.py + docs/scholarship/electricity-bill-catalogue.md.
        return electricity_genuineness(ocr_text)
    if doc_type == 'water_bill':
        # Signature-scored off the OCR text (GRAMMAR-first, operator-as-bonus — water has no single
        # national operator, unlike TNB) → genuine {air_selangor/saj_johor/…/unrecognised} / suspect
        # {thin/cropped} / not_water_bill {MyKad / an ELECTRICITY bill in the water slot / junk}.
        # See water_doc.py + docs/scholarship/water-bill-catalogue.md.
        return water_genuineness(ocr_text)
    if doc_type == 'str':
        # Three genuine STR approval forms (MOF letter / dashboard / semakan) are signature-
        # scored off the OCR text; an LHDN SALINAN copy or a SARA letter matches no form marker
        # → unrecognised → holistic fallback (which still accepts a genuine MySTR screenshot).
        sig = signature_genuineness(ocr_text, doc_type='str')
        if sig.get('status') != 'unrecognised':
            return sig
        return doc_genuineness(image, content_type, doc_type)
    return doc_genuineness(image, content_type, doc_type)
