"""Who issued an offer letter, when no fingerprinted family claims it (corpus-gaps C1, MODEL_VERSION 1.8.0).

The offer scorer (`results_doc.signature_genuineness`) bands every offer by its best-fitting family,
and before 1.8.0 it never said "we do not know this issuer": an offer from a PUBLIC TVET institution
we have not fingerprinted yet (request #47's ILKBS letter) was compared with the nearest university
pattern and read 'suspect', which raised the official-document request and could block submission.
Two owner rulings (2026-10-26, `docs/decisions.md`) settle it:

  A. a CLOSED, NAMED list of known public TVET issuers reads NOT CHECKED (`bands.NOT_CHECKED`): no
     genuineness penalty, never a block, never an official-document request, and the reviewer checks
     the letter by eye. Every other offer keeps exactly today's bands, so a forged letter from an
     UNNAMED issuer scores as it always did;
  B. a TVET offer COUNTS as a supported official public offer — it is not a private (IPTS) option.

Plus an honest reason for a private college/university (IPTS), which used to be labelled with the
nearest public family ("polytechnic") although no public issuer is on the page. The status is
unchanged — only the words.

⚠ THE ISSUER IS READ OFF THE LETTERHEAD ONLY (`_LETTERHEAD_CHARS` of the normalised OCR text, which
runs top-down). Private colleges commonly print "diiktiraf oleh Jabatan Pembangunan Kemahiran (JPK)"
or a MARA sponsorship line in the BODY; read there, the list would excuse a private letter. And the
net never applies when a fingerprinted family's own issuer line is on the page — UiTM ("Universiti
Teknologi MARA") stays a university letter, scored exactly as before. Pure + deterministic.
"""
from .bands import NOT_CHECKED

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

#: The closed list (owner ruling A, 2026-10-26): ministry → (display name, full names, acronyms).
#: Acronyms match as whole words only; full names as phrases. Nothing here is a pattern for a
#: genuineness SCORE — a TVET family is added only once we hold ≥3 genuine letters each (roadmap).
TVET_ISSUERS = {
    'tvet_belia_sukan': ('Kementerian Belia dan Sukan (ILKBS / IKBN / IKTBN)',
                         ('KEMENTERIAN BELIA DAN SUKAN', 'INSTITUT KEMAHIRAN BELIA NEGARA',
                          'INSTITUT KEMAHIRAN TINGGI BELIA NEGARA'),
                         ('ILKBS', 'IKBN', 'IKTBN')),
    'tvet_mara':        ('MARA (TVETMARA / IKM / KKTM)',
                         ('MAJLIS AMANAH RAKYAT', 'INSTITUT KEMAHIRAN MARA',
                          'KOLEJ KEMAHIRAN TINGGI MARA'),
                         ('TVETMARA', 'IKM', 'KKTM')),
    'tvet_jtm':         ('Jabatan Tenaga Manusia (JTM / ADTEC / ILP / JPK)',
                         ('JABATAN TENAGA MANUSIA', 'JABATAN PEMBANGUNAN KEMAHIRAN',
                          'INSTITUT LATIHAN PERINDUSTRIAN', 'PUSAT LATIHAN TEKNOLOGI TINGGI'),
                         ('JTM', 'ADTEC', 'ILP', 'JPK', 'ILJTM')),
}

#: How much of the normalised OCR text counts as the letterhead (see the module note).
_LETTERHEAD_CHARS = 600
#: A private company / an accredited private centre on the letterhead is never a public issuer.
_PRIVATE_HEAD = (' SDN BHD ', ' BHD ', ' BERHAD ', ' PUSAT BERTAULIAH ')
#: Words a public body prints on its letterhead (a ministry, a department, a school); a letterhead
#: naming an institution with NONE of these, and no public issuer, reads as a private one.
_PUBLIC_WORDS = (' KEMENTERIAN ', ' JABATAN ', ' KERAJAAN ', ' MAJLIS ', ' SEKOLAH ', ' TINGKATAN ')
_INSTITUTION_WORDS = (' KOLEJ ', ' COLLEGE ', ' UNIVERSITI ', ' UNIVERSITY ', ' INSTITUT ',
                      ' INSTITUTE ', ' AKADEMI ', ' ACADEMY ')


def _fingerprinted_issuer_on_page(scores) -> bool:
    """True when ANY fingerprinted family's own issuer line was found — that letter belongs to the
    family's bands, never to this net."""
    return any(FAMILY_ISSUER_SIG.get(fam) in (s.get('present') or []) for fam, s in (scores or {}).items())


def tvet_issuer(text_norm: str, scores) -> str:
    """The `TVET_ISSUERS` key named on the letterhead of an offer (already normalised by
    `results_doc._norm_fold_upper_alnum`), or '' — also '' when a fingerprinted family's issuer is
    on the page or the letterhead names a private company."""
    if _fingerprinted_issuer_on_page(scores):
        return ''
    head = f' {(text_norm or "")[:_LETTERHEAD_CHARS]} '
    if any(p in head for p in _PRIVATE_HEAD):
        return ''
    for key, (_display, names, acronyms) in TVET_ISSUERS.items():
        if any(n in head for n in names) or any(f' {a} ' in head for a in acronyms):
            return key
    return ''


def unfingerprinted_offer(text_norm: str, r: dict, status: str, reason: str, model_version: str) -> dict:
    """The scorer's result for an offer BELOW the genuine band (`results_doc.signature_genuineness`
    hands it here with the band it computed): NOT CHECKED for a known public TVET issuer on the
    letterhead; otherwise exactly that band, with the private-college reason where it applies."""
    key = tvet_issuer(text_norm, r.get('scores'))
    if key:
        return not_checked_result(key, r, model_version)
    return {'status': status, 'probability': r['probability'], 'type': r['type'],
            'present': r['present'], 'missing': r['missing'],
            'reason': (private_college_reason(text_norm, r) or reason)[:300],
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


def private_college_reason(text_norm: str, r: dict) -> str:
    """The honest reason for an offer whose LETTERHEAD names an institution but no public body — a
    private college/university (IPTS) — or '' when that is not what the page shows. Read off the
    letterhead for the same reason as `tvet_issuer`: a private letter cites JPK or MARA in its body."""
    head = f' {(text_norm or "")[:_LETTERHEAD_CHARS]} '
    if _fingerprinted_issuer_on_page(r.get('scores')) or any(w in head for w in _PUBLIC_WORDS):
        return ''
    if not any(w in head for w in _INSTITUTION_WORDS):
        return ''
    return (f"private college / university (IPTS) - not a supported public issuer (nearest pattern "
            f"{r['type'].replace('_', ' ')}, p={r['probability']:.2f})")[:300]


def issuer_display(key: str) -> str:
    """The officer-facing name of a `TVET_ISSUERS` key, or '' for any other value."""
    return TVET_ISSUERS[key][0] if key in TVET_ISSUERS else ''


def not_checked_issuer(vision_fields) -> str:
    """The `{issuer}` of the officer's `offer_issuer_not_checked` line (owner ruling A): the stored
    NOT CHECKED offer's issuer, by its `doc_seen` key. The verdict's Pathway card reads it off the offer
    it already holds, so it costs no query; officer-only (not in `resolution.CODE_TO_TICKET`), and TD-114
    holds the card at Probable because the offer carries no genuineness signal."""
    from .bands import stored_authenticity
    return issuer_display(stored_authenticity(vision_fields).get('doc_seen', '')) or 'TVET'
