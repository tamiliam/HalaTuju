"""The genuineness fingerprint a field-extraction read stores beside its fields
(``vision_fields['authenticity']``), one scorer per document type. Moved out of
``_run_field_extraction_impl`` (audit sprint A3.1); the branches, their order and their calls
are as they were. Each ``_auth_*`` returns the dict to store, or None for no signal."""

from django.conf import settings

from .. import vision as _v   # seams resolve on the package: one patch target reaches every caller


def _ocr_read(doc, ocr):
    """The OCR read a scorer works from: the one handed in, else a fresh ``ocr_document``. ``(read, text)``."""
    rr = ocr if ocr is not None else _v.ocr_document(doc)
    return rr, (rr or {}).get('text', '') or ''


def _signature_auth(sg):
    """The stored shape of a signature-scorer result (results slip, BC, EPF, STPM slot)."""
    return {
        'status': sg['status'], 'reason': sg['reason'], 'doc_seen': sg['type'],
        'probability': sg['probability'], 'present': sg['present'], 'missing': sg['missing'],
        'model_version': sg.get('model_version'),
    }


def _assessed_auth(auth, status):
    """The stored shape of an ``assess`` result (offer, STR): the probability keys only when scored."""
    return {
        'status': status,
        'reason': auth.get('reason', ''),
        'doc_seen': auth.get('type') or auth.get('doc_seen', ''),
        **({'probability': auth['probability'], 'present': auth['present'],
            'missing': auth['missing'], 'model_version': auth.get('model_version')}
           if 'probability' in auth else {}),
    }


def _family_auth(sg):
    """The stored shape of a family-scorer result (income docs, utility bills, school-leaving cert)."""
    return {
        'status': sg['status'], 'reason': sg['reason'], 'doc_seen': sg['family'],
        'probability': sg['probability'], 'model_version': sg.get('model_version'),
        'markers': sg.get('markers'),
    }


def _auth_results_slip(doc, ocr, image):
    # Probabilistic SIGNATURE genuineness (deterministic + auditable) over the OCR text,
    # plus a focused multimodal read for the two VISUAL signatures (QR + crest) on the
    # already-fetched image. A failed/empty OCR read yields NO signal — we never penalise
    # a student for our failure.
    from ..genuineness.results_doc import signature_genuineness, results_visual_markers
    rr, text = _ocr_read(doc, ocr)
    if text.strip() and not (rr or {}).get('error'):
        markers = results_visual_markers(image, doc.content_type) if image is not None else {}
        sg = signature_genuineness(text, has_qr=markers.get('has_qr', False),
                                   has_crest=markers.get('has_crest', False))
        return _signature_auth(sg)
    return None


def _auth_offer_letter(doc, ocr, image):
    # SIGNATURE genuineness over the OCR text (MODEL_VERSION 1.4.0: scored purely by-score via
    # `band_for`, no issuer anchor) → genuine (≥0.70) / suspect (0.35–0.70) / not_offer_letter
    # (<0.35). Text-only — the crest/JPPKK seal are bonus and the text signatures already clear
    # the band. No text + no image → no signal.
    from ..genuineness import assess
    rr, text = _ocr_read(doc, ocr)
    gimg = image if image is not None else _v._fetch_image_bytes(doc.storage_path)
    # The offer is scored TEXT-only (signatures). An empty/failed OCR is OUR failure →
    # no signal, never a 'suspect' penalty (mirrors the slip/BC/EPF branches).
    auth = (assess('offer_letter', image=gimg, content_type=doc.content_type, ocr_text=text)
            if text.strip() and not (rr or {}).get('error') else None)
    if auth and auth.get('status'):
        # The by-score status is stored as-is (the pathway verdict + submission gate treat
        # anything != 'genuine' as not an official offer). A legacy 'unrecognised' (pre-1.4.0,
        # "an issuer we do not know") is still folded to 'suspect'. 1.8.0's NOT CHECKED
        # (`bands.NOT_CHECKED` — a KNOWN public TVET issuer) is NOT folded: it is stored as
        # itself and every reader takes it as no signal (owner ruling A, 2026-10-26).
        st = 'suspect' if auth['status'] == 'unrecognised' else auth['status']
        return _assessed_auth(auth, st)
    return None


def _auth_signature_doc(doc, ocr):
    # Probabilistic SIGNATURE genuineness over the OCR text (deterministic + auditable;
    # TD-122). Text-dominant — the visual markers (BC barcode/crest, KWSP logo) are bonus
    # and the text signatures already clear the band; the EPF scorer also doubles as the
    # wrong-type backstop (tax form / withdrawal / STR-as-EPF → not_epf). A failed/empty OCR
    # read yields NO signal. A semester_result (1.9.0) / higher_results (1.11.0, + ruling 1A)
    # is scored only when it is an STPM document (`stpm_doc`); anything else stays unscored.
    from ..genuineness.results_doc import signature_genuineness
    from ..genuineness.stpm_doc import stpm_slot_genuineness
    rr, text = _ocr_read(doc, ocr)
    sg = ({} if not text.strip() or (rr or {}).get('error') else stpm_slot_genuineness(doc, text)
          if doc.doc_type not in ('birth_certificate', 'epf') else signature_genuineness(text, doc_type=doc.doc_type))
    return _signature_auth(sg) if sg else None


def _auth_str(doc, ocr, image_fn):
    # SIGNATURE genuineness over the OCR text for the three STR approval forms (MOF
    # letter / MySTR dashboard / Semakan Status); an LHDN SALINAN copy or a SARA letter
    # is unrecognised → holistic fallback on the image (which still accepts a genuine
    # MySTR screenshot). Approval vs SALINAN stays the extraction `status` field.
    from ..genuineness import assess
    _rr, text = _ocr_read(doc, ocr)
    gimg = image_fn()   # str field-extraction is text-based; bytes for the holistic fallback
    auth = assess('str', image=gimg, content_type=doc.content_type, ocr_text=text)
    if auth and auth.get('status'):
        return _assessed_auth(auth, auth['status'])
    return None


def _auth_income_doc(doc, ocr):
    # POSITIVE signature scorer (salary_doc.py) over the OCR text — statutory payroll grammar,
    # not a letterhead → genuine {private/govt/singapore/gig} / suspect {informal: wage labels,
    # no scaffold} / not_salary {MyKad-in-slot (#47) or no payslip fields}; since 1.2.0 (#374) an
    # income DECLARATION form in EITHER slot reads suspect/'declaration' (a support letter that
    # is no declaration gets no signal). Text-only + deterministic; a failed/empty OCR yields NO
    # signal (never penalise our own read failure). SOFT: feeds the officer chip + the gate's
    # usable-salary-slip check + the declaration rule (`income_declaration`).
    from ..genuineness.declaration_doc import income_doc_genuineness
    rr, text = _ocr_read(doc, ocr)
    if text.strip() and not (rr or {}).get('error') and (sg := income_doc_genuineness(text, doc.doc_type)):
        return _family_auth(sg)
    return None


def _auth_electricity_bill(doc, ocr):
    # POSITIVE signature scorer (electricity_doc.py, MODEL_VERSION 1.0.0) over the OCR text —
    # issuer identity (TNB/SESB/SESCO) + Malay bill-field grammar → genuine {tnb/…} / suspect
    # {thin or cropped-no-issuer} / not_electricity_bill {MyKad or a WATER bill in the slot, or
    # nothing bill-shaped}. An issuer marker guarantees the doc is never rejected (calibrated on
    # 27 live bills, 0 false-rejects). Text-only + deterministic; a failed/empty OCR yields NO
    # signal (never persist 'not_electricity_bill' off our own read failure). SOFT: this feeds
    # the officer cockpit chip + the keep-better ranking (`_doc_genuine_rank` reads
    # authenticity.status) — it does NOT gate submission (utility bills are soft signals).
    from ..genuineness.electricity_doc import electricity_genuineness
    rr, text = _ocr_read(doc, ocr)
    if text.strip() and not (rr or {}).get('error'):
        return _family_auth(electricity_genuineness(text))
    return None


def _auth_water_bill(doc, ocr):
    # POSITIVE signature scorer (water_doc.py, MODEL_VERSION 1.0.0) over the OCR text —
    # GRAMMAR-first, operator-as-bonus (water is state-run: ~13 operators, none dominant, so
    # the shared 'Bil Air'/m³/'No. Akaun' grammar decides, not a single issuer) → genuine
    # {air_selangor/saj_johor/…/unrecognised} / suspect {thin/cropped} / not_water_bill {MyKad,
    # or an ELECTRICITY bill misfiled into the water slot (family 'electricity_bill' — the
    # reverse of the #83 swap, caught symmetrically), or nothing bill-shaped}. Any water signal
    # (a water term / an m³ unit / a recognised operator) guarantees the doc is never rejected
    # (calibrated on 28 live bills, 0 false-rejects). Text-only + deterministic; a failed/empty
    # OCR yields NO signal (never persist 'not_water_bill' off our own read failure). SOFT:
    # this feeds the officer cockpit chip + the keep-better ranking (`_doc_genuine_rank` reads
    # authenticity.status) — it does NOT gate submission (utility bills are soft signals).
    from ..genuineness.water_doc import water_genuineness
    rr, text = _ocr_read(doc, ocr)
    if text.strip() and not (rr or {}).get('error'):
        return _family_auth(water_genuineness(text))
    return None


def _auth_school_leaving_cert(doc, ocr):
    # POSITIVE signature scorer (school_leaving_doc.py, MODEL_VERSION 1.0.0) over the OCR text
    # — leaver-anchor-first (Berhenti Sekolah / a leaving-cert title) + the standard numbered
    # form's field labels → genuine {sijil_berhenti} / suspect {thin-cropped} / unrecognised
    # {a free-form testimonial we can't structurally confirm — DEFER, never fake} /
    # not_school_leaving_cert {a MyKad or another known doc misfiled in the slot}. A leaver
    # signal guarantees the doc is never rejected. Text-only + deterministic; a failed/empty
    # OCR yields NO signal (never persist a reject off our own read failure). SOFT: feeds the
    # officer chip + the keep-better ranking (`_doc_genuine_rank`) only — a school-leaving cert
    # is a soft academic-completeness doc, it does NOT gate submission. `markers` (incl.
    # `label_names`) is the calibration readout the re-extraction pass reads back to tune.
    from ..genuineness.school_leaving_doc import school_leaving_genuineness
    rr, text = _ocr_read(doc, ocr)
    if text.strip() and not (rr or {}).get('error'):
        return _family_auth(school_leaving_genuineness(text))
    return None


def _auth_holistic(doc, image_fn):
    # birth_certificate/epf holistic fallback (+ any other)
    gimg = image_fn()
    if gimg is not None:
        auth = _v.doc_genuineness(gimg, doc.content_type, doc.doc_type)
        if auth:
            return auth
    return None


def add_read_authenticity(doc, result, *, ocr, image, image_fn):
    """Genuineness fingerprint (flag-gated, soft): a multimodal "does this look like a real
    official document?" read → ``result['authenticity']``. One extra Gemini call per
    supporting doc; never blocks. (The IC has its own in run_vision_for_document.) The
    results-slip and the offer already fetched their ``image`` in the read; the others fetch
    here through ``image_fn``. Leaves ``result`` untouched when there is no signal."""
    if not getattr(settings, 'DOC_GENUINENESS_CHECK_ENABLED', False):
        return
    t = doc.doc_type
    if t == 'results_slip':
        auth = _auth_results_slip(doc, ocr, image)
    elif t == 'offer_letter':
        auth = _auth_offer_letter(doc, ocr, image)
    elif t in ('birth_certificate', 'epf', 'semester_result', 'higher_results'):
        auth = _auth_signature_doc(doc, ocr)
    elif t == 'str':
        auth = _auth_str(doc, ocr, image_fn)
    elif t in ('salary_slip', 'income_support_doc'):
        auth = _auth_income_doc(doc, ocr)
    elif t == 'electricity_bill':
        auth = _auth_electricity_bill(doc, ocr)
    elif t == 'water_bill':
        auth = _auth_water_bill(doc, ocr)
    elif t == 'school_leaving_cert':
        auth = _auth_school_leaving_cert(doc, ocr)
    elif t in _v._GENUINENESS_DOCS:
        auth = _auth_holistic(doc, image_fn)
    else:
        auth = None
    if auth is not None:
        result['authenticity'] = auth
