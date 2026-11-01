"""The AI offer-letter reader (offer exact-read S4, 2026-11-01) — what Gemini is shown, what it is
asked, and the version stamped on every read.

`vision.extract_document_fields(..., 'offer_letter', ...)` hands every offer read here, so each caller
and every test that patches that seam is unchanged. The deterministic STPM / matriculation /
polytechnic reader (`offer_parse`) still runs first in `vision._run_field_extraction_impl`; this is
the read for every letter it does not lock.

WHAT CHANGED FROM THE UNVERSIONED READER (S3 measured it: 53 of 216 letters fully exact):
  * **Inputs.** Up to `MAX_PAGES` pages, ONE image per page (it was page 1 only), at
    `MEDIA_RESOLUTION` high — S3 found every image sent as 258 tokens, a low-detail view whatever
    its size; a 2026-11-01 probe on a synthetic A4 page measured 258 at the default and at medium,
    3,354 at high (Gemini 2.5 "pan and scan"). A digital PDF's own text layer for those pages goes
    beside the images (it was never shown), so spellings and numbers are read from real characters.
  * **Schema.** `institution` is the institution's NAME only; the new `campus` holds the campus /
    branch ('' when none); a hostel / residential college / reporting venue goes in neither but in
    the new `reporting_venue`; a printed course code leaves `programme` for the new
    `programme_code` (owner rulings 2026-11-01, `docs/decisions.md`; shape agreed with the matcher's
    session). `issuer` is unchanged.
  * **Prompt.** The owner's reading rules: read exactly as printed; PISMP's programme is the degree
    title; the intake keeps its label; dates carry no weekday or time; a reporting date is only a
    report / registration date (never a commencement date); the IC also from the reference line
    when it is printed only there, never invented.
  * **Clean-up.** `clean_offer_fields`: a code left in `programme` moves to `programme_code`, and an
    IC read whose digits cannot be an IC is blanked (a blank is a soft "unread", a wrong number a
    confident wrong-person red).

VERSIONING (memory: feedback_doc_recognition_versioning). `OFFER_READER_VERSION` is semantic and is
stored on every AI offer read as `vision_fields['offer_reader_version']`, with what was shown in
`vision_fields['offer_reader_inputs']`. Bump it on ANY change to the prompt, the schema, the inputs or
the clean-up: MAJOR when a field changes meaning (2.0.0: `institution` no longer carries the campus),
MINOR for a new field or input, PATCH for wording. Reads before S4 carry no stamp (= the 1.x reader).
The genuineness score (`results_doc.MODEL_VERSION`) does not read these fields and is unchanged.
"""
from __future__ import annotations

import re

#: Semantic version of the AI offer reader — see the module docstring.
OFFER_READER_VERSION = '2.0.0'
#: Pages of a PDF shown to Gemini: an e-registration slip can sit in front of the offer and the
#: reporting date can be on page 2 (owner notes, S1); later pages are mostly reply forms.
MAX_PAGES = 3
#: The text layer shown beside the images, at most (3 pages of an offer is ~6-9k characters).
MAX_TEXT_CHARS = 8000
#: `GenerateContentConfig.media_resolution` for an image read (Gemini 2.5 takes it for the whole call,
#: not per image).
MEDIA_RESOLUTION = 'MEDIA_RESOLUTION_HIGH'
#: OCR text shown on the text-only path (no image could be fetched), as before.
MAX_OCR_CHARS = 6000

_STR = {'type': 'string'}
_FIELDS = ('candidate_name', 'candidate_nric', 'programme', 'programme_code', 'institution', 'campus',
           'reporting_venue', 'issuer', 'offer_date', 'intake', 'candidate_address', 'stream',
           'reporting_date', 'reporting_date_label', 'bidang_pengkhususan', 'elektif', 'aliran')
#: The structured-output schema; `vision._FIELD_SCHEMAS['offer_letter']` is this object.
OFFER_SCHEMA = {'type': 'object', 'properties': {
    **{f: _STR for f in _FIELDS}, 'warnings': {'type': 'array', 'items': _STR}}}

OFFER_HINT = (
    ' This is a Malaysian post-SPM offer letter — Form Six ("Tingkatan Enam"), matriculation '
    '("Program Matrikulasi"), polytechnic ("Politeknik"), community college, PISMP (teacher training, '
    '"Ijazah Sarjana Muda Perguruan"), a skills institute, or a university degree / diploma / '
    'foundation offer. The file may hold more than the offer: an e-registration slip in front of it, '
    'further pages, or a reply / acceptance form, a checklist or a medical form after it. Read the '
    'OFFER pages; a value may sit on any of them. Labels and values are often a two-column list — '
    'read the layout VISUALLY and pair each value with its own label. READ EXACTLY AS PRINTED: copy '
    'the letter\'s own spelling, capitals and wording; never correct, translate, expand or shorten '
    'anything (keep "UiTM" as "UiTM"). '
    '"candidate_name" = the offered student\'s full name. "candidate_nric" = the student\'s IC number '
    '(12 digits), printed as "No. Kad Pengenalan" / "No. K/P" / "No. Pengenalan Diri" / "MyKad"; when '
    'the offer prints it ONLY inside its reference line ("Rujukan Kami", "No. Rujukan", "Our '
    'Reference", e.g. "<12 digits>/UP..." or ".../<12 digits>"), take those 12 digits. Never a matric, '
    'student, application or reference number, never a number written on a reply or acceptance form, '
    'and leave it EMPTY when the offer pages print no IC — never guess one. '
    '"institution" = the institution\'s NAME only, as printed in the line that says where the programme '
    'is offered ("Kampus", "Tempat Pengajian", "Institusi", "ditawarkan ... di ...") — e.g. "UiTM", '
    '"UNIVERSITI MALAYSIA SABAH", "INSTITUT PENDIDIKAN GURU", "POLITEKNIK KOTA KINABALU", "KOLEJ '
    'MATRIKULASI SELANGOR". A town or state that is part of a polytechnic\'s, community college\'s, '
    'matriculation college\'s, Form-Six centre\'s or skills institute\'s own name stays in the name. '
    '"campus" = the campus / branch of that institution as printed (e.g. "KAMPUS KOTA KINABALU", '
    '"KAMPUS PAGOH", "Antarabangsa Labuan"), without a campus code ("S -", "B8 -"); when a line prints '
    'both a state branch and a campus ("CAWANGAN SABAH, KAMPUS KOTA KINABALU") the campus is the most '
    'specific part ("KAMPUS KOTA KINABALU"); empty when the letter names no campus. NEVER put a hostel '
    'or residential college ("Kolej Kediaman", "KOLEJ DAHLIA", "Desasiswa"), a faculty, a hall or any '
    'reporting / registration venue in "institution" or "campus": that place, if printed, goes in '
    '"reporting_venue", as printed. "issuer" = the body that issued the letter, from its letterhead '
    '(Sektor Operasi Sekolah / Bahagian Matrikulasi / Jabatan Pendidikan Politeknik dan Kolej Komuniti '
    '/ Institut Pendidikan Guru Malaysia / a university or its admissions office). '
    '"programme" = the programme / course title as printed, WITHOUT a course code; a printed code '
    '("UH6481001", "BA272") goes in "programme_code" (several joined with ", "; empty when none). '
    'PISMP: "programme" = the degree title as printed (e.g. "IJAZAH SARJANA MUDA PERGURUAN"), the '
    'specialisation goes in "bidang_pengkhususan" (e.g. "Bahasa Tamil Pendidikan Rendah"), "elektif" = '
    'the elective subject, "aliran" = the school stream ("SK" / "SJKC" / "SJKT"). "stream" = the '
    'Form-Six "Bidang" (Sains / Sains Sosial) or the matriculation "Jurusan". '
    '"intake" = the session / intake exactly as printed WITH its label and any semester words (e.g. '
    '"SESI 1-2026/2027", "SEMESTER 1 TAHUN 2026", "SESI AKADEMIK 2026/2027", "AMBILAN 2026"). Write a '
    'date without its weekday or time. "offer_date" = the date the letter was ISSUED ("Tarikh" in the '
    'reference block), NOT "Tarikh Cetakan" (the print date). "reporting_date" = ONLY the date the '
    'student must REPORT / REGISTER, labelled e.g. "Tarikh Lapor Diri", "Tarikh Pendaftaran", "Tarikh '
    'Mendaftar", "Tarikh dan Masa Daftar", "Tarikh Kemasukan ke Kolej", or a bare "Tarikh" inside a '
    '"diminta untuk mendaftar pada tarikh, tempat dan masa" clause; for a range, its first day. NEVER '
    'a commencement or lecture-start date ("Tarikh Mula Kuliah", "Tarikh Permulaan Pengajian", "kuliah '
    'bermula") and never the issue date: leave it EMPTY when the letter prints no report / '
    'registration date. "reporting_date_label" = the VERBATIM label the reporting date sits under; '
    'empty when there is no reporting date. "candidate_address" = the student\'s mailing address if '
    'shown. Leave any field empty if the letter does not print it — fill only the fields this kind of '
    'letter actually has.')

_TEXT_LAYER_HEAD = ('\n\nTEXT LAYER of the same pages (the PDF\'s own characters, page by page): use it '
                    'to read spellings and numbers exactly; the images decide which label each value '
                    'belongs to.\n')


def _ask(source: str) -> str:
    from .vision import _WARNING_VOICE
    return (f'{source} Extract the listed fields exactly as printed. If a field is missing or unclear, '
            'leave it empty and add a short note to "warnings". Do NOT invent values.'
            f'{_WARNING_VOICE}{OFFER_HINT}')


def image_prompt(n_images: int, text_layer: str = '') -> str:
    """The prompt sent after ``n_images`` page images (images first, then this — the seam's order)."""
    pages = ('an image of a Malaysian offer letter' if n_images == 1 else
             f'images of the first {n_images} pages of a Malaysian offer letter file, in order')
    prompt = _ask(f'These are {pages}. Read every image carefully.')
    return prompt + (_TEXT_LAYER_HEAD + text_layer if text_layer else '')


def text_prompt(ocr_text: str) -> str:
    """The prompt for the text-only read (no image could be fetched)."""
    return (_ask('Here is the OCR text from a Malaysian offer letter.')
            + f'\n\nOCR TEXT:\n{(ocr_text or "")[:MAX_OCR_CHARS]}')


def offer_inputs(data: bytes, content_type: str) -> dict:
    """What Gemini is shown for a file: ``{images: [(bytes, mime)], text_layer, kind}``. A PDF → its
    first `MAX_PAGES` pages, one PNG each, plus its usable text layer for those pages (TD-411's
    test, so a scanner app's stamp is no layer); a photo → itself. ``images`` is [] when nothing
    can be shown."""
    from . import vision
    from .pdf_pages import pdf_page_pngs, pdf_page_text, usable_text_layer
    if not data:
        return {'images': [], 'text_layer': '', 'kind': 'none'}
    if vision._is_pdf(content_type, data):
        pngs = pdf_page_pngs(data, MAX_PAGES)
        text = usable_text_layer(pdf_page_text(data, MAX_PAGES))[:MAX_TEXT_CHARS]
        return {'images': [(p, 'image/png') for p in pngs], 'text_layer': text, 'kind': 'pdf'}
    img, mime = vision._as_image_for_gemini(data, content_type)
    return {'images': [(img, mime)] if img else [], 'text_layer': '', 'kind': 'image'}


def _stamp(inputs=None, *, text_only=False) -> dict:
    shown = {'pages': 0, 'text_layer_chars': 0, 'media_resolution': '', 'ocr_text': text_only}
    if inputs:
        shown.update(pages=len(inputs['images']), text_layer_chars=len(inputs['text_layer']),
                     media_resolution=MEDIA_RESOLUTION if inputs['images'] else '')
    return {'offer_reader_version': OFFER_READER_VERSION, 'offer_reader_inputs': shown}


def read_offer(ocr_text: str, *, image=None, content_type: str = '') -> dict:
    """The AI offer read → ``{fields, warnings, error, offer_reader_version, offer_reader_inputs}``.
    ``image`` is the uploaded FILE's bytes (a PDF or a photo); without it ``ocr_text`` is read.
    Never raises; persists nothing (the only write on its path is the seam's usage meter)."""
    from . import vision
    if image is not None:
        inputs = offer_inputs(image, content_type)
        if not inputs['images']:
            return {'fields': {}, 'warnings': [], 'error': 'no image for extraction', **_stamp(inputs)}
        data = vision._call_gemini_json(image_prompt(len(inputs['images']), inputs['text_layer']),
                                        OFFER_SCHEMA, images=inputs['images'],
                                        media_resolution=MEDIA_RESOLUTION)
        stamp = _stamp(inputs)
    else:
        if not (ocr_text or '').strip():
            return {'fields': {}, 'warnings': [], 'error': 'no text', **_stamp(text_only=True)}
        data = vision._call_gemini_json(text_prompt(ocr_text), OFFER_SCHEMA)
        stamp = _stamp(text_only=True)
    if '_error' in data:
        return {'fields': {}, 'warnings': [], 'error': data['_error'], **stamp}
    warnings = vision._drop_expected_warnings('offer_letter', data.pop('warnings', []) or [])
    data = clean_offer_fields(vision._sanitize_extracted_fields('offer_letter', data))
    return {'fields': data, 'warnings': warnings, 'error': '', **stamp}


#: An IC is 12 digits; one dropped or added digit is still an IC the name·IC check can call "close".
_NRIC_DIGITS = (11, 13)


def clean_offer_fields(data: dict) -> dict:
    """Deterministic guards after the read. Pure; never raises.
      * A course code left in ``programme`` (our UPU code "UW6526001", UiTM's leading "BA272") moves to
        ``programme_code`` — the matcher's code tier reads it there once it reads the field.
      * ``candidate_nric`` is blanked unless its digits number 11-13: a reference or matric number is
        not an IC, and a blank reads "unread" (soft) where a wrong number reads a wrong person."""
    if not isinstance(data, dict):
        return data
    prog = str(data.get('programme') or '')
    if prog:
        from .offer_course_match import COURSE_CODE_RE, _LOCAL_CODE_RE
        codes = [c.upper() for c in COURSE_CODE_RE.findall(prog)]
        local = _LOCAL_CODE_RE.match(prog)
        if local:
            codes.insert(0, local.group(0).strip())
            prog = prog[local.end():]
        if codes:
            prog = COURSE_CODE_RE.sub(' ', prog)
            prog = re.sub(r'\(\s*\)', ' ', prog)
            data['programme'] = re.sub(r'^[\s\-–—:,]+|[\s\-–—:,]+$', '', ' '.join(prog.split()))
            have = [c.strip() for c in str(data.get('programme_code') or '').split(',') if c.strip()]
            data['programme_code'] = ', '.join(dict.fromkeys(have + codes))
    nric = str(data.get('candidate_nric') or '')
    digits = len(re.sub(r'\D', '', nric))
    if nric and not (_NRIC_DIGITS[0] <= digits <= _NRIC_DIGITS[1]):
        data['candidate_nric'] = ''
    return data
