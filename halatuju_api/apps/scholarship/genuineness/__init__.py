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
from .results_doc import score_signatures, signature_genuineness

__all__ = ['ic_genuineness', 'doc_genuineness', 'score_signatures', 'signature_genuineness',
           'band_for', 'GENUINE_MIN', 'SUSPECT_MAX', 'assess']


def assess(doc_type, *, image=None, content_type='', ocr_text='', has_qr=False, has_crest=False):
    """Single entry point → the soft authenticity dict for ``doc_type`` (or ``{}`` for an
    unsupported type / no signal). Callers supply whatever that type needs (an image for the
    multimodal checks; OCR text + visual flags for the results-slip signature scorer)."""
    if doc_type in ('ic', 'parent_ic'):
        return ic_genuineness(image, content_type)
    if doc_type in ('results_slip', 'certificate'):
        return signature_genuineness(ocr_text, has_qr=has_qr, has_crest=has_crest)
    return doc_genuineness(image, content_type, doc_type)
