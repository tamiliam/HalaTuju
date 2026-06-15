"""Back-compat shim — the results-document signature scorer moved into the genuineness/
package (genuineness/results_doc.py + genuineness/bands.py). Kept so existing imports
(``apps.scholarship.doc_signatures.*``) keep resolving. New code should import from
``apps.scholarship.genuineness``.
"""
from .genuineness.bands import GENUINE_MIN, SUSPECT_MAX, band_for  # noqa: F401
from .genuineness.results_doc import (  # noqa: F401
    SLIP_SIGNATURES, CERT_SIGNATURES, score_signatures, signature_genuineness,
)
