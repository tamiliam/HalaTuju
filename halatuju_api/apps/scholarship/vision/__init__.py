"""
Google Cloud Vision OCR for the IC (MyKad) upload — a SOFT signal, never a
hard block. The admin verify-&-accept (S11a) remains the real identity gate;
this module exists to (a) help the student spot typos at upload time, and
(b) give the admin a hint next to the manual checklist.

Pure helpers (``nric_match``, ``name_match``, the canonical normalisers) are
the testable core — they run pure and require no API key. The actual Vision
call (``extract_mykad``) is mocked in tests and degrades gracefully to an
error dict when the API is unavailable or the SDK isn't installed.

⚠ THIS IS A RE-EXPORT SHELL AND NO CODE (audit sprint A3.1, TD-361 part, 2026-11-09).
``vision.py`` was 2,319 lines; its bodies are the modules beside this file, moved and not
changed — except the one long field-extraction read, now a helper per document family
(``field_extraction.py``) and a scorer per type (``authenticity.py``), same calls in the same
order. Import from ``apps.scholarship.vision`` exactly as before: every name the old module
had is re-exported here, and no importing file was changed.

⚠ THE SEAMS STAY ON THIS PACKAGE. Inside the package, a call to a seam (Storage, Cloud Vision,
Gemini, and every function a test or eval command patches) goes through the package —
``from .. import vision as _v`` then ``_v.name(...)`` — so a patch of
``apps.scholarship.vision.<name>`` still reaches every caller, inside and out. A seam called
directly by its module name would make such a patch a silent no-op, and the real (paid)
call would run. Keep that pattern when adding a call.
"""
import logging

from ..gemini import cascade_failure, document_failure
from ..genuineness.bands import keep_stored_authenticity
from ..read_errors import (IC_SECOND_OPINION_ERROR, IC_SECOND_OPINION_UNTIL, OCR_SERVICE_FAILED,
                           UNPARSEABLE_RESPONSE, is_ai_service_error, is_ocr_service_error,
                           model_rejected_document, read_deferred)
from ..pdf_pages import (MIN_TEXT_LAYER_CHARS as _MIN_PDF_TEXT, pdf_first_page_png as _pdf_first_page_png,
                         pdf_text_layer as _pdf_text_layer, usable_text_layer as _usable_text_layer)
from ..income_declaration import read_approval as _read_approval   # #374: the approval is read off the IMAGE
from ..higher_results import HINT as _HIGHER_HINT, SCHEMA as _HIGHER_SCHEMA, extract as _higher_extract
from ..name_order import patronymic_reversed   # TD-408: a reversed patronymic is a different person
from ..offer_reader import OFFER_SCHEMA         # offer exact-read S4: the offer reader's own module
from .names import (
    _GLUED_MARKER_AFTER, _GLUED_MARKER_BEFORE, _MONTHS, _NAME_NOISE, _canonical_name_seq,
    _canonical_nric, _fold_name_token, _glued_equal, _levenshtein, _parse_dob, _split_glued_markers,
    _tokens_close, canonical_name_tokens, name_match, nric_close, nric_dob_agrees, nric_match,
    reference_names, relationship_name_match
)
from .mykad import (
    MY_STATES, _ADDRESS_LABEL_TOKENS, _ADDRESS_PREFIX_NOISE, _GLUED_HEADER_FRAGMENTS,
    _LEADING_PARENTAGE, _MANGLED_MARKERS, _MYKAD_HEADER_TOKENS, _MY_POSTCODE, _NRIC_REGEX,
    _PARENTAGE_MARKER, _TRAILING_PARENTAGE, _continuation_surname, _extract_address, _extract_name,
    _extract_nric, _guard_garbled, _is_card_label_line, _is_likely_state, _is_name_line,
    _name_looks_garbled, _preceding_givenname, _replace_trailing_marker, _trailing_marker_canonical,
    _with_broken_name_parts, _with_trailing_surname
)
from .schemas import (
    GEMINI_EXTRACT_DOC_TYPES, _DOC_HINTS, _FIELD_SCHEMAS, _NAME_FIELD, _STR, _STR_SOURCE, _doc_schema
)
from .match import (
    _ADDR_ABBREV, _ADDR_GENERIC, _ROAD_HEAD, _addr_norm, _house_numbers, _norm_house_no,
    _street_name_tokens, address_match, address_present, name_present, run_vision_match_for_document
)
from .judge import (
    _DOC_NAME_LABEL_RE, _any_field_filled, _bank_verdict, _strip_name_label, doc_student_verdict
)
from .sanitize import (
    _NON_NAME_MARKERS, _RD_MONTHS, _RD_MONTH_NUM, _RD_TIME, _RD_WEEKDAY, _drop_expected_warnings,
    _looks_like_non_name, _normalise_reporting_date, _sanitize_extracted_fields
)
from .gemini_read import (
    _IC_GEMINI_PROMPT, _IC_GEMINI_SCHEMA, _WARNING_VOICE, _as_image_for_gemini, _call_gemini_json,
    _gemini_ic_second_opinion, extract_document_fields
)
from .ocr import (
    _PDF_MAGIC, _doc_usage_ctx, _fetch_image_bytes, _is_pdf, _vision_document_text, _vision_words,
    extract_mykad, extract_text, ocr_document, ocr_document_full, read_text_document
)
from .ic import _lock_nric_if_confirmed, _merge_ic_reads, _should_gemini_ic, run_vision_for_document
from .field_extraction import (
    _EX_KEPT, _extract_slip_deterministic, _offer_context, _run_field_extraction_impl,
    run_field_extraction_for_document
)

logger = logging.getLogger(__name__)   # 'apps.scholarship.vision' — the name every submodule logs under


# ── Genuineness checks live in the genuineness/ package (one home, per the architecture) ──
# Re-exported here so the upload path above and back-compatible imports
# (apps.scholarship.vision.ic_genuineness / .doc_genuineness) keep resolving unchanged.
from ..genuineness.ic import ic_genuineness  # noqa: E402,F401 — re-export for back-compatible imports; placed after the definitions above it
from ..genuineness.supporting_doc import doc_genuineness, _GENUINENESS_DOCS  # noqa: E402,F401 — re-export for back-compatible imports; placed after the definitions above it
