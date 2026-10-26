"""Who issued an offer letter, when no fingerprinted family claims it (corpus-gaps C1, MODEL_VERSION 1.8.0).

The offer scorer (`results_doc.signature_genuineness`) bands every offer by its best-fitting family,
and before 1.8.0 it never said "we do not know this issuer": an offer from a PUBLIC TVET institution
we have not fingerprinted yet (request #47's ILKBS letter) was compared with the nearest university
pattern and read 'suspect', which raised the official-document request and could block submission.
Owner rulings (2026-10-26, `docs/decisions.md`) settle it:

  A. a GENUINE-LOOKING letter from a CLOSED, NAMED list of known public TVET issuers reads NOT CHECKED
     (`bands.NOT_CHECKED`): no genuineness penalty, never a block, never an official-document request,
     and the reviewer checks it by eye. Every other offer keeps exactly today's bands;
  B. a TVET offer COUNTS as a supported official public offer — it is not a private (IPTS) option;
  C. Kolej Profesional MARA and the Kolej MARA colleges are public (on the list); KPTM (Kolej Poly-Tech
     MARA) and UniKL (Universiti Kuala Lumpur) are MARA-OWNED BUT PRIVATE — never NOT CHECKED, always
     the private-college reason, although their names contain "MARA".

Plus an honest reason for a private college/university (IPTS), which used to be labelled with the
nearest public family ("polytechnic") although no public issuer is on the page. Its status is
unchanged — only the words.

⚠ THE NET IS NARROW ON PURPOSE (C1 review, 2026-10-26: a typed fake, a skills certificate, a MARA loan
letter, a page reading only "JTM" and a MARA-sponsored private college all read NOT CHECKED in the
first cut, which would have closed the officer's official-offer request on each). So ALL of these hold:
  1. the letter already reads SUSPECT (0.35–0.70) — the shape of a real but unfingerprinted offer. A
     `not_offer_letter` (< 0.35) stays exactly as today, whatever it names;
  2. the page carries offer-shaped wording (`_OFFER_WORDS`) — a certificate or a loan letter does not;
  3. the issuer is named on the LETTERHEAD (`_LETTERHEAD_CHARS`, top-down), because private colleges
     cite "Jabatan Pembangunan Kemahiran (JPK)" accreditation or MARA sponsorship in the body;
  4. a SPONSOR line ("Tajaan" / "ditaja" / "Penaja" / "sponsored by") never names the issuer;
  5. a bare 3-letter acronym (IKM, ILP, JTM, JPK) never counts alone — it needs offer wording on the
     letterhead too; the full names and the longer acronyms are distinctive enough on their own;
  6. never over a fingerprinted family's own issuer line (a UA name — UiTM stays a university letter),
     a private company, or a private MARA-owned institution (ruling C). Pure + deterministic.
"""
import re

from .bands import NOT_CHECKED, GENUINE_MIN, SUSPECT_MAX

#: The fingerprinted families' own issuer lines — the weight-3 identity signature of each family in
#: `results_doc` (label as stored in `authenticity.present`). ONE home: `pathway_engine` reads it for
#: the reporting-date bonus's public-issuer gate.
FAMILY_ISSUER_SIG = {
    'stpm':          'Sektor Operasi Sekolah',
    'matriculation': 'Bahagian Matrikulasi',
    'polytechnic':   'Jabatan Pend. Politeknik & KK',
    'pismp':         'Institut Pendidikan Guru',
    'ua_offer':      'public university (UA) name',
}

#: The closed list (owner rulings A + C, 2026-10-26): ministry → (display name, full names, acronyms).
#: Full names match as phrases; acronyms as whole words, a bare 3-letter one only beside offer wording.
#: Nothing here is a pattern for a genuineness SCORE — a TVET family is added only once we hold ≥3
#: genuine letters each (roadmap "Later").
TVET_ISSUERS = {
    'tvet_belia_sukan': ('Kementerian Belia dan Sukan (ILKBS / IKBN / IKTBN)',
                         ('KEMENTERIAN BELIA DAN SUKAN', 'INSTITUT KEMAHIRAN BELIA NEGARA',
                          'INSTITUT KEMAHIRAN TINGGI BELIA NEGARA'),
                         ('ILKBS', 'IKBN', 'IKTBN')),
    'tvet_mara':        ('MARA (TVETMARA / IKM / KKTM / Kolej MARA)',
                         ('MAJLIS AMANAH RAKYAT', 'INSTITUT KEMAHIRAN MARA',
                          'KOLEJ KEMAHIRAN TINGGI MARA', 'KOLEJ PROFESIONAL MARA', 'KOLEJ MARA'),
                         ('TVETMARA', 'IKM', 'KKTM')),
    'tvet_jtm':         ('Jabatan Tenaga Manusia (JTM / ADTEC / ILP / JPK)',
                         ('JABATAN TENAGA MANUSIA', 'JABATAN PEMBANGUNAN KEMAHIRAN',
                          'INSTITUT LATIHAN PERINDUSTRIAN', 'PUSAT LATIHAN TEKNOLOGI TINGGI'),
                         ('JTM', 'ADTEC', 'ILP', 'JPK', 'ILJTM')),
}
#: Owner ruling C: MARA-OWNED but PRIVATE. Anywhere on the page, it rules the net out and the
#: private-college reason in — the "MARA" in their names never makes them a public issuer.
_PRIVATE_MARA = (' KOLEJ POLY TECH MARA ', ' KPTM ', ' UNIVERSITI KUALA LUMPUR ', ' UNIKL ')

#: How much of the normalised OCR text counts as the letterhead (see the module note).
_LETTERHEAD_CHARS = 600
#: Offer-shaped wording (rule 2). "TAWARAN PINJAMAN" (a loan offer) is not an admission offer.
_OFFER_WORDS = (' TAWARAN ', ' DITAWARKAN ', ' OFFER OF ADMISSION ', ' SURAT TAWARAN ')
_NOT_OFFER = (' TAWARAN PINJAMAN ',)
#: A sponsor line names who pays, never who issues (rule 4). Matched on the RAW line, before folding.
_SPONSOR = re.compile(r'\b(TAJAAN|DITAJA|PENAJA|SPONSORED\s+BY|SPONSOR)\b', re.IGNORECASE)
#: A private company / an accredited private centre on the letterhead is never a public issuer.
_PRIVATE_HEAD = (' SDN BHD ', ' BHD ', ' BERHAD ', ' PUSAT BERTAULIAH ')
#: Words a public body prints on its letterhead (a ministry, a department, a school); a letterhead
#: naming an institution with NONE of these, and no public issuer, reads as a private one. The public
#: universities' common short names count too (C1 review: a UiTM PDF's text layer carries no
#: letterhead and says only "UiTM").
_PUBLIC_WORDS = (' KEMENTERIAN ', ' JABATAN ', ' KERAJAAN ', ' MAJLIS ', ' SEKOLAH ', ' TINGKATAN ')
_UA_SHORT = ('UM', 'USM', 'UKM', 'UPM', 'UTM', 'UITM', 'UIAM', 'IIUM', 'UUM', 'UNIMAS', 'UMS', 'UPSI',
             'USIM', 'UTEM', 'UMP', 'UNIMAP', 'UTHM', 'UMT', 'UMK', 'UPNM', 'UNISZA')
_INSTITUTION_WORDS = (' KOLEJ ', ' COLLEGE ', ' UNIVERSITI ', ' UNIVERSITY ', ' INSTITUT ',
                      ' INSTITUTE ', ' AKADEMI ', ' ACADEMY ')


def _fold(s):
    from .results_doc import _norm_fold_upper_alnum
    return f' {_norm_fold_upper_alnum(s)} '


def _letterhead(ocr_text: str) -> str:
    """The folded letterhead: the opening lines up to `_LETTERHEAD_CHARS`, sponsor lines dropped."""
    from .results_doc import _norm_fold_upper_alnum
    parts, size = [], 0
    for line in (ocr_text or '').splitlines():
        if size >= _LETTERHEAD_CHARS:
            break
        folded = '' if _SPONSOR.search(line) else _norm_fold_upper_alnum(line)
        if folded:
            parts.append(folded)
            size += len(folded) + 1
    return f" {' '.join(parts)[:_LETTERHEAD_CHARS]} "


def _has_offer_words(folded: str) -> bool:
    for w in _NOT_OFFER:
        folded = folded.replace(w, ' ')
    return any(w in folded for w in _OFFER_WORDS)


def _names_a_listed_issuer(head: str) -> bool:
    """True when the folded letterhead names a `TVET_ISSUERS` body — by full name or by an acronym
    longer than three letters (the short ones are too common to say "public" on their own)."""
    return any(any(f' {n} ' in head for n in names) or any(f' {a} ' in head for a in acr if len(a) > 3)
               for _display, names, acr in TVET_ISSUERS.values())


def _fingerprinted_issuer_on_page(scores) -> bool:
    """True when ANY fingerprinted family's own issuer line was found — that letter belongs to the
    family's bands, never to this net."""
    return any(FAMILY_ISSUER_SIG.get(fam) in (s.get('present') or []) for fam, s in (scores or {}).items())


def tvet_issuer(ocr_text: str, scores) -> str:
    """The `TVET_ISSUERS` key named on the letterhead of an offer, or '' (see the module note,
    rules 2–6; rule 1, the suspect band, is the caller's)."""
    page, head = _fold(ocr_text), _letterhead(ocr_text)
    if (_fingerprinted_issuer_on_page(scores) or not _has_offer_words(page)
            or any(p in page for p in _PRIVATE_MARA) or any(p in head for p in _PRIVATE_HEAD)):
        return ''
    offer_in_head = _has_offer_words(head)
    for key, (_display, names, acronyms) in TVET_ISSUERS.items():
        if any(f' {n} ' in head for n in names):
            return key
        if any(f' {a} ' in head and (len(a) > 3 or offer_in_head) for a in acronyms):
            return key
    return ''


def unfingerprinted_offer(ocr_text: str, r: dict, status: str, reason: str, model_version: str) -> dict:
    """The scorer's result for an offer BELOW the genuine band (`results_doc.signature_genuineness`
    hands it here with the band it computed): NOT CHECKED for a known public TVET issuer on a letter
    that reads SUSPECT (rule 1); otherwise exactly that band, with the private-college reason where
    it applies."""
    key = tvet_issuer(ocr_text, r.get('scores')) if SUSPECT_MAX <= r['probability'] < GENUINE_MIN else ''
    if key:
        return not_checked_result(key, r, model_version)
    return {'status': status, 'probability': r['probability'], 'type': r['type'],
            'present': r['present'], 'missing': r['missing'],
            'reason': (private_college_reason(ocr_text, r) or reason)[:300],
            'model_version': model_version}


def not_checked_result(key: str, r: dict, model_version: str) -> dict:
    """The NOT CHECKED outcome for a known public TVET issuer — the scorer's result shape, with the
    issuer's key as `type` (stored as `doc_seen`) and a reason the officer can read plainly."""
    return {'status': NOT_CHECKED, 'probability': r['probability'], 'type': key,
            'present': r['present'], 'missing': r['missing'],
            'reason': (f'{TVET_ISSUERS[key][0]}: a known public TVET issuer we have not fingerprinted '
                       f'yet - NOT CHECKED, check the letter by eye (nearest pattern '
                       f"{r['type'].replace('_', ' ')}, p={r['probability']:.2f})")[:300],
            'model_version': model_version}


def private_college_reason(ocr_text: str, r: dict) -> str:
    """The honest reason for an offer whose LETTERHEAD names an institution but no public body — a
    private college/university (IPTS) — or '' when that is not what the page shows. A private
    MARA-owned institution (ruling C) always gets it. Read off the letterhead for the same reason
    as `tvet_issuer`; any public-university name or short name anywhere on the page rules it out."""
    page, head = _fold(ocr_text), _letterhead(ocr_text)
    text = (f"private college / university (IPTS) - not a supported public issuer (nearest pattern "
            f"{r['type'].replace('_', ' ')}, p={r['probability']:.2f})")[:300]
    if any(p in page for p in _PRIVATE_MARA):
        return text
    from .results_doc import _UA_NAMES
    if (_fingerprinted_issuer_on_page(r.get('scores')) or any(w in head for w in _PUBLIC_WORDS)
            or any(f' {n} ' in page for n in _UA_NAMES) or any(f' {a} ' in page for a in _UA_SHORT)
            or _names_a_listed_issuer(head)):
        return ''           # a public body — even one the TVET net did not excuse — is never "private"
    return text if any(w in head for w in _INSTITUTION_WORDS) else ''


def issuer_display(key: str) -> str:
    """The officer-facing name of a `TVET_ISSUERS` key, or '' for any other value."""
    return TVET_ISSUERS[key][0] if key in TVET_ISSUERS else ''


def officer_must_close(doc, item) -> bool:
    """C1 review (corpus-gaps C2): True when an upload must NOT close `item` because the uploaded
    offer is NOT CHECKED and `item` is an OFFICER's own offer-letter request. The officer asked for
    the official offer and nobody has checked this one — so it waits for the officer, who closes it
    by hand. System and Check-2 requests are untouched, and it never blocks the student."""
    from .bands import NOT_CHECKED, stored_status
    return (getattr(doc, 'doc_type', '') == 'offer_letter' and getattr(item, 'source', '') == 'officer'
            and getattr(item, 'doc_type', '') == 'offer_letter'
            and stored_status(getattr(doc, 'vision_fields', None)) == NOT_CHECKED)


def not_checked_issuer(vision_fields) -> str:
    """The `{issuer}` of the officer's `offer_issuer_not_checked` line (owner ruling A): the stored
    NOT CHECKED offer's issuer, by its `doc_seen` key. The verdict's Pathway card reads it off the offer
    it already holds, so it costs no query; officer-only (not in `resolution.CODE_TO_TICKET`), and TD-114
    holds the card at Probable because the offer carries no genuineness signal."""
    from .bands import stored_authenticity
    return issuer_display(stored_authenticity(vision_fields).get('doc_seen', '')) or 'TVET'
