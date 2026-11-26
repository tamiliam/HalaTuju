"""The owner's words: what a genuine offer letter of one issuer ALWAYS shows (owner method change, 2026-11-20).

The same method as SPM, NRIC and EPF: the owner looked at sample letters of one issuer and gave the exact words
every genuine letter prints. A university rules lane may lock a letter only when its DRAWN text (render-mode
visible, S-visible: a digital PDF's checked page-1 layout, or a scan's OCR) shows ALL of them; otherwise the AI
reads it. Colour, size, covering and off-page placement are NOT checked yet (a separate, planned piece of work).
This is an allow-list: it replaces trying to list every way a letter can say "withdrawn" (S1c review rounds 1-3).

Matching (owner's rule, 20 Nov, option 1): the way the genuineness markers match
(`results_doc._norm_fold_upper_alnum`, with letters of any script kept: `_norm`): the phrase AND the text are upper-cased, accents folded, and every run of
characters that are not letters or digits becomes one space. So case, line breaks, spacing and the spaces around
"," "/" "." do not matter ("Tahniah , sukacita", "Saudara / i" match). Kept:

* a phrase is whole words: no letter or digit of ANY script glued on either side ("Programme" is not "Program",
  "Rujukankami" and "RujukanЖ" are not "Rujukan"; `_norm`, review round 1);
* a ONE-word phrase ("Program", "Rujukan") does not count where it sits inside another listed phrase's match
  ("Kod Program", "program pengajian"): the label must be printed on its own;
* no OCR misreading is forgiven.

Per issuer, as DATA (`OWNER_WORDS`), keyed by the rules lane: S2 / S3 add UPSI, UUM and the rest as new rows.
The reverse, for EVERY rules lane (`AI_ONLY_WORDS`, `ai_only`): a letter whose page-1 text says ASASI (glued,
spaced or OCR-misread too) never locks by rules (owner, 20 Nov); `offer_parse._rules_exit` applies it to every
lock, university or government.
Pure; never raises on text input; linear in the text (each phrase is literal words joined by bounded spaces).
"""
from __future__ import annotations

import re

#: The rules lane -> the owner's required phrases, numbered from 1 in this order (the refusal records numbers only).
OWNER_WORDS = {
    # Universiti Malaysia Sabah (owner, 20 Nov). 4: the owner typed "UNIVERSII", the typo of UNIVERSITI. 5 and 6
    # were given as one line; the student's name sits between "bahawa" and "telah", so they are two phrases.
    'ua:UMS': (
        'BAHAGIAN PERKHIDMATAN AKADEMIK',
        'Rujukan',
        'No. Kad Pengenalan',
        'TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA SABAH',
        'Tahniah, sukacita dimaklumkan bahawa',
        'telah ditawarkan tempat',
        'Program',
        'Kod Program',
        'Sekiranya saudara/saudari menerima tawaran ini',
        'Tarikh Lapor Diri',
        'Saudara/i akan mengikuti program pengajian',
    ),
    # OCR-13 (owner, 20 Nov). Read by `offer_parse_upsi` (OCR-13 phase 5; the lane is off by default).
    # Universiti Pendidikan Sultan Idris. 3: the owner typed "UNIVERSII"; letters print UNIVERSITI. An English
    # "official confirmation letter" shows none of these and goes to the AI.
    'ua:UPSI': (
        'BAHAGIAN HAL EHWAL AKADEMIK',
        'Rujukan Kami',
        'TAWARAN KEMASUKAN KE UNIVERSITI PENDIDIKAN SULTAN IDRIS (UPSI)',
        'Sukacita dimaklumkan bahawa anda ditawarkan mengikuti program pengajian di UPSI',
        'Program',
        'Tempoh Pengajian',
        'Tarikh Mendaftar',
        'Sekiranya saudara/i didapati memberi maklumat salah/tidak benar/memanipulasi maklumat',
        'Tawaran ini adalah muktamad',
        'Ketua Timbalan Pendaftar',
        'Surat tawaran ini merupakan surat tawaran rasmi.',
    ),
    # Universiti Utara Malaysia. English "Admission" letters and PENGESAHAN (senate confirmation) letters -> AI.
    'ua:UUM': (
        'JABATAN HAL EHWAL AKADEMIK',
        'Rujukan',
        'TAWARAN KEMASUKAN KE UNIVERSITI UTARA MALAYSIA',
        'Tahniah kerana saudara/i berjaya dipilih',
        'Program Pengajian',
        'Tempoh Pengajian',
        'Tarikh Pendaftaran Fizikal (UUM)',
    ),
    # Universiti Teknologi MARA. 7: the owner typed "Programme dan kampus"; letters print "Program dan kampus".
    # 8: required, though text is sometimes printed over it (owner). UiTM prints DIPLOMA letters on the same
    # layout: these words alone never tell a degree from a diploma (the layout reader must).
    'ua:UiTM': (
        'SURAT TAWARAN',
        'Sukacita dimaklumkan bahawa anda ditawarkan tempat',
        'Program',
        'Tempoh Pengajian',
        'Sila hadir mendaftar',
        'Tarikh',
        'Program dan kampus yang ditawarkan adalah MUKTAMAD',
        'Bahagian Pengambilan Pelajar',
    ),
    # Universiti Malaya. 4 includes "berjaya" (7 of the owner's 8 samples print it); the English letter -> AI.
    'ua:UM': (
        'Nombor K/P',
        'Tarikh',
        'TAWARAN KEMASUKAN KE UNIVERSITI MALAYA',
        'Tahniah saudara/i telah berjaya ditawarkan tempat',
        'PROGRAM PENGAJIAN',
        'TEMPOH PENGAJIAN',
        'Tawaran ini adalah MUKTAMAD',
        'Jabatan Perkhidmatan Akademik',
    ),
    # OCR-14 (owner, 20 Nov; memory halatuju_owner_words). The lanes stay OFF. UNIMAS, UTHM and UKM have layout readers
    # (`offer_parse_unimas` phase 2, `offer_parse_uthm` phase 3, `offer_parse_ukm` phase 4); the rest get theirs later. Universities with no owner words stay AI.
    'ua:UKM': (            # Universiti Kebangsaan Malaysia. 4 as printed (owner yes, 20 Nov).
        'PUSAT PENGURUSAN AKADEMIK', 'Rujukan', 'TAWARAN KEMASUKAN',
        'Dengan sukacitanya saya bagi pihak Universiti Kebangsaan Malaysia', 'NO. KAD PENGENALAN',
        'PROGRAM PENGAJIAN', 'TEMPOH PENGAJIAN', 'TARIKH LAPOR DIRI', 'Tawaran yang diberikan adalah MUKTAMAD',
    ),
    'ua:UMK': (            # Universiti Malaysia Kelantan. 8-10 may fall on PAGE 2 (break before Tarikh/MUSTAHAK).
        'PUSAT PENGURUSAN AKADEMIK', 'No. KAD PENGENALAN', 'TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA KELANTAN',
        'Tahniah, sukacita dimaklumkan anda telah ditawarkan tempat', 'Program', 'Tempoh', 'Tarikh', 'MUSTAHAK',
        'Tawaran ini adalah tertakluk kepada syarat-syarat tawaran kemasukan', 'Tawaran ini adalah MUKTAMAD',
    ),
    'ua:UMPSA': (          # Universiti Malaysia Pahang Al-Sultan Abdullah: the 2026/27 layout ONLY (2024 -> AI).
        'RUJ. KAMI (OUR REF)', '(NO. K/P:',
        'TAWARAN KEMASUKAN KE PROGRAM SARJANA MUDA UNIVERSITI MALAYSIA PAHANG AL-SULTAN ABDULLAH',
        'Dimaklumkan bahawa Universiti Malaysia Pahang Al-Sultan Abdullah (UMPSA) mengucapkan tahniah',
        'PROGRAM PENGAJIAN', 'TEMPOH PENGAJIAN', 'TARIKH PENDAFTARAN KOLEJ KEDIAMAN',
        'Program yang ditawarkan adalah MUKTAMAD', 'Pusat Pemasaran dan Kemasukan',
    ),
    'ua:UniMAP': (         # Universiti Malaysia Perlis (1 degree sample: far below the gate).
        'PUSAT PENGURUSAN AKADEMIK', 'Rujukan Kami', 'TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA PERLIS',
        'Sukacita saya bagi pihak Universiti Malaysia Perlis', 'Program Pengajian', 'Tempoh Pengajian',
        'Tarikh Pendaftaran', 'Tawaran ini adalah muktamad',
    ),
    'ua:UNIMAS': (         # Universiti Malaysia Sarawak: the 2026/27 layout ONLY (2023/24, "PEJABAT PENDAFTAR" -> AI).
        'Pejabat Timbalan Naib Canselor', 'Tawaran kemasukan Ke Universiti Malaysia Sarawak',
        'Tahniah! Saudara/saudari adalah ditawarkan tempat', 'Program', 'Tempoh Pengajian', 'Pendaftar',
    ),
    'ua:UniSZA': (         # Universiti Sultan Zainal Abidin.
        'Rujukan', 'TAWARAN KEMASUKAN KE UNIVERSITI SULTAN ZAINAL ABIDIN',
        'Dengan sukacitanya dimaklumkan bahawa saudara/i ditawarkan mengikuti program', 'Program Pengajian',
        'Tempoh Pengajian', 'Tarikh', 'Tawaran ini adalah MUKTAMAD', 'Pendaftar',
    ),
    'ua:UPM': (            # Universiti Putra Malaysia.
        'PEJABAT TIMBALAN NAIB CANSELOR', 'Rujukan', 'TAWARAN KEMASUKAN KE UNIVERSITI PUTRA MALAYSIA',
        'Sukacita dimaklumkan bahawa anda ditawarkan masuk ke Universiti Putra Malaysia', 'Program', 'Tarikh',
    ),
    'ua:USM': (            # Universiti Sains Malaysia. 1 is in the letterhead PICTURE (`OPTIONAL_ON_TEXT_PDF`).
        'Jabatan Pendaftar', 'No.Rujukan',
        'TAWARAN KEMASUKAN PROGRAM IJAZAH SARJANA MUDA, UNIVERSITI SAINS MALAYSIA',
        'Tahniah, saudara/i telah berjaya ditawarkan tempat untuk mengikuti program Ijazah Sarjana Muda (Penuh Masa)',
        'PROGRAM PENGAJIAN', 'TEMPOH PENGAJIAN', 'TARIKH LAPOR DIRI/MASA',
        'Program pengajian yang ditawarkan kepada saudara/i ini adalah muktamad', 'Pendaftar',
    ),
    'ua:UTeM': (           # Universiti Teknikal Malaysia Melaka. NO Asasi excuse (measured: `_EXCUSED_LINE`).
        'PEJABAT PENDAFTAR', 'Rujukan Kami (Our Ref)', 'TAWARAN KEMASUKAN KE UNIVERSITI TEKNIKAL MALAYSIA MELAKA',
        'Tahniah, sukacita dimaklumkan bahawa', 'Program Pengajian', 'Tarikh', 'Bahagian Pengurusan Akademik',
    ),
    'ua:UTHM': (           # Universiti Tun Hussein Onn Malaysia.
        'PEJABAT PENGURUSAN AKADEMIK', 'Rujukan Kami(Our Ref.)',
        'TAWARAN KEMASUKAN KE UNIVERSITI TUN HUSSEIN ONN MALAYSIA',
        'Tahniah diucapkan kepada saudara/i kerana ditawarkan tempat', 'Program & Kod Program',
        'Tempoh Program (Tahun)', 'Tarikh', 'Tawaran ini adalah MUKTAMAD',
    ),
}

#: Per issuer (rules lane): the phrase numbers NOT required on a PDF read from its TEXT LAYER, because that
#: issuer prints them as part of its letterhead picture (owner, 20 Nov: UMS phrase 1). A scan (OCR of the page
#: image) still needs every phrase. OCR-14: USM phrase 1 (owner, 20 Nov).
OPTIONAL_ON_TEXT_PDF = {'ua:UMS': (1,), 'ua:USM': (1,)}

#: Words that keep a letter off EVERY rules lane (university or government family): the AI reads it instead (owner,
#: 20 Nov: "For now, let AI handle Asasi. When there a larger sample, we can consider switching."). Asasi is a
#: foundation programme, not a degree, and some UMS Asasi letters look like the degree template. word -> guard.
AI_ONLY_WORDS = {'ASASI': 'asasi_ai_read'}
#: The spaced-out form, whole words ("A S A S I", "A.S.A.S.I", "ASAS I"), in the `_norm` fold.
_AI_ONLY = tuple((re.compile(r'(?<!\w)' + ' ?'.join(w) + r'(?!\w)'), g) for w, g in AI_ONLY_WORDS.items())
#: Asasi fix round (20 Nov, review MEDIUM): the unspaced form ANYWHERE, no word edges ("PROGRAMASASI", "178Asasi",
#: a scan's "ASASIpin"), the last I also read as OCR's 1, L or | ("ASAS1", "ASASl", "ASAS|"); looked for in the
#: look-alike fold (`offer_ums_refusal.fold_lookalikes`: a Cyrillic / Greek "АSASI" is ASASI), upper-cased, with
#: every other character kept. Refusing more is the safe side: "ASASIAH" or "ASASINYA" refuse too (one AI call).
_AI_ONLY_GLUED = ((re.compile(r'ASAS[I1L|]'), AI_ONLY_WORDS['ASASI']),)
#: OCR-13 (roadmap Asasi note, 20 Nov): the ONE letterhead phrase a lane may print without it meaning an Asasi
#: offer, per issuer. 17 of 18 UiTM letters print an "Asasi & Diploma" office line; measured on the owner's
#: UiTM samples (OCR-13, shapes and counts only), the drawn page-1 layout shows it as a contact label in a
#: telephone block: "Asasi & Diploma : (NNN) NNNN NNNN / NNNN ...", starting a layout column (below the title in 13 of 14
#: layouts, so its place on the page is not used). Excused only in exactly that form (plain ASCII letters, any
#: case; up to 3 spaces around '&' and ':'), starting a line or a layout column (3+ spaces before it), with
#: NOTHING but telephone numbers after the colon up to the column's end (digits, spaces, '(', ')', '/', '-'), and
#: only ONCE: ASASI anywhere else on the page (programme, offer sentence, another line, the label with no number
#: or with words after it, words before it in its column, the phrase split over two lines, a second copy,
#: look-alike letters) still refuses. Only the label words are blanked: the numbers stay. A UiTM letter's PARSED
#: programme is checked on its own (`programme_ai_only`), so a label-shaped programme value still refuses.
#: The one sample that prints the label another way ("... (Asasi & Diploma)") refuses: refusing more is safe.
#: No other lane has an excuse. OCR-14 phase 1 measured UTeM the same way (shapes and counts only): none of the
#: owner's 10 UTeM degree letters, nor the corpus's degree letter, prints ASASI on page 1. The UTeM letters that do
#: are DIPLOMA letters, whose faculty field names "Sekolah Asasi Teknikal dan Pengajian Diploma", and two of them
#: show all 7 UTeM owner phrases: for those the Asasi exit is the owner-words barrier, so UTeM gets NO excuse.
_PHONE = r'\(?\+?\d{2,4}\)?[^\S\n]?-?[^\S\n]?\d{3,4}'     # "(603) 5544 ...", "03-5544 ..."
_EXCUSED_LINE = {'ua:UiTM': re.compile(r'(?aim)(?:^|(?<=[^\S\n]{3}))[^\S\n]*ASASI[^\S\n]{1,3}&[^\S\n]{1,3}DIPLOMA'
                                       r'[^\S\n]{0,3}:(?=[^\S\n]{0,3}' + _PHONE +
                                       r'(?:[^\S\n]{0,2}[\d()/\-])*[^\S\n]*(?:[^\S\n]{3}|$))')}
#: OCR-13: an English-language letter's Asasi ("Foundation in Science"): looked for in the PROGRAMME field only —
#: sponsor and fund names elsewhere on a page print "Foundation".
_FOUNDATION_IN = re.compile(r'(?<!\w)FOUNDATION IN(?!\w)')


#: Owner words review round 1 (LOW 5): the most text the phrases are looked for in, counted AFTER the unicode
#: unpacking (one U+FDFA unpacks to 18 characters: 200,000 of them took about 5 s). Longer shows no phrase.
MAX_NORM_CHARS = 200_000
#: NFKD runs on pieces this long (splitting between characters changes only the ORDER of combining marks, and
#: those are dropped): one call on the whole of 200,000 x U+FDFA took 4.7 s, pieces take milliseconds.
_CHUNK = 256
#: A run of characters that are not a letter or a digit (any script; '_' is not a letter).
_NOT_WORD = re.compile(r'[\W_]+')


def _norm(text: str) -> str:
    """The genuineness markers' rule (`results_doc._norm_fold_upper_alnum`: NFKD, accents dropped, upper case,
    each run of other characters one space), applied to phrase and text alike, with ONE change (owner words
    review round 1, LOW 6): a letter or digit of ANY script is kept as a word character, never turned into a
    space, so "RujukanЖ" and "ProgramΑ" are not "Rujukan" / "Program". The phrases are plain A-Z, so for them
    the two rules agree. '' when the unpacked text is longer than `MAX_NORM_CHARS`."""
    import unicodedata
    text, parts, size = text or '', [], 0
    for i in range(0, len(text), _CHUNK):        # chunked: one long NFKD call is slow on its own (U+FDFA)
        part = unicodedata.normalize('NFKD', text[i:i + _CHUNK])
        size += len(part)
        if size > MAX_NORM_CHARS:
            return ''
        parts.append(part)
    s = ''.join(c for c in ''.join(parts) if not unicodedata.combining(c))
    return _NOT_WORD.sub(' ', s.upper()).strip()


def _pattern(phrase: str):
    """The normalised phrase as whole words in the normalised text (single spaces, so a literal match); a
    letter or digit of any script on either side means it is part of a longer word."""
    return re.compile(r'(?<!\w)' + re.escape(_norm(phrase)) + r'(?!\w)')


_PATTERNS = {lane: tuple(_pattern(p) for p in phrases) for lane, phrases in OWNER_WORDS.items()}


def _shown(lane: str, text: str) -> set:
    """The 0-based indices of ``lane``'s phrases that ``text`` shows (the one-word rule in the module docstring)."""
    pats = _PATTERNS.get(lane, ())
    text = _norm(text) if pats else ''
    spans = [[m.span() for m in p.finditer(text)] for p in pats]
    multi = _merged(sorted(s for k, p in enumerate(OWNER_WORDS.get(lane, ())) if len(p.split()) > 1 for s in spans[k]))
    shown = set()
    for k, phrase in enumerate(OWNER_WORDS.get(lane, ())):
        own = spans[k]
        if len(phrase.split()) == 1:
            own = [s for s in own if not _inside(s, multi)]
        if own:
            shown.add(k)
    return shown


def owner_ink_targets(lane: str, page1_layout: str, labels: dict, optional, printed: dict) -> tuple:
    """(phrases, values) for the ink check (`pdf_ink.ink_missing`): the owner phrases ``page1_layout`` shows
    (``p<n>``), and each ``labels`` field's value as ``printed``; an ``optional`` one only when read. A required value
    left blank stays in, so the ink check refuses it. OCR-13: the one home for this rule (UUM uses it)."""
    shown = _shown(lane, page1_layout or '')
    phrases = [(f'p{k + 1}', p) for k, p in enumerate(OWNER_WORDS[lane]) if k in shown]
    values = [(label, printed[k]) for k, label in labels.items() if k not in optional or str(printed[k]).strip()]
    return phrases, values


def _merged(spans) -> list:
    """Sorted spans merged into disjoint ones (two overlapping phrases cover their union: refusing more is safe)."""
    out = []
    for a, b in spans:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _inside(span, merged) -> bool:
    """True when ``span`` lies within one of the disjoint, sorted ``merged`` spans (one bisect: linear overall)."""
    import bisect
    i = bisect.bisect_right(merged, (span[0], float('inf'))) - 1
    return i >= 0 and merged[i][0] <= span[0] and span[1] <= merged[i][1]


def missing(lane: str, text: str, text_pdf: bool = False) -> list:
    """The 1-based numbers of ``lane``'s owner phrases that ``text`` does NOT show ([] = all shown). A lane with
    no owner list misses nothing here; the caller decides whether such a lane may lock at all. ``text_pdf`` (the
    drawn page-1 text of a PDF read from its text layer) excuses the lane's `OPTIONAL_ON_TEXT_PDF` phrases only."""
    shown = _shown(lane, text)
    excused = set(OPTIONAL_ON_TEXT_PDF.get(lane, ())) if text_pdf else set()
    return [k + 1 for k in range(len(OWNER_WORDS.get(lane, ()))) if k not in shown and k + 1 not in excused]


def ai_only(text: str) -> str:
    """The guard (`AI_ONLY_WORDS`, e.g. 'asasi_ai_read') when ``text`` — a letter's page-1 text as its rules lane
    reads it (`offer_parse._rules_exit`), or a parsed programme / stream — says ASASI; '' otherwise. Two forms:
    whole words folded as the phrases are (`_norm`: any case, accents, line breaks, punctuation around it), its
    letters spaced out too ("A S A S I", "A.S.A.S.I"); and the unspaced form anywhere, glued to other letters or
    digits, the last I also OCR's 1 / L / |, Cyrillic or Greek look-alikes folded first (`_AI_ONLY_GLUED`).
    Fails closed: text with letters or digits that `_norm` will not fold (longer than `MAX_NORM_CHARS`) gives the
    first guard."""
    from .offer_ums_refusal import fold_lookalikes
    text = text or ''
    folded = _norm(text)
    if not folded:
        return next(iter(AI_ONLY_WORDS.values())) if any(c.isalnum() for c in text) else ''
    looks = fold_lookalikes(text)
    spaced = (folded, _norm(looks))
    return (next((guard for pat, guard in _AI_ONLY if any(pat.search(s) for s in spaced)), '')
            or next((guard for pat, guard in _AI_ONLY_GLUED if pat.search(looks.upper())), ''))


def ai_only_on_lane(lane: str, text: str) -> str:
    """`ai_only` for a rules lane's page-1 text, with that lane's ONE excused letterhead label (`_EXCUSED_LINE`,
    UiTM only) blanked first; any other lane: exactly `ai_only`. Two or more such labels: nothing is excused."""
    pat = _EXCUSED_LINE.get(lane)
    text = text or ''
    if pat is not None and len(text) <= MAX_NORM_CHARS and len(pat.findall(text)) == 1:
        text = pat.sub(' ', text, count=1)
    return ai_only(text)


def programme_ai_only(programme: str) -> str:
    """The Asasi guard for a university lane's parsed PROGRAMME field: `ai_only`, or an English "Foundation in"
    programme (`_FOUNDATION_IN`, folded as the phrases are); '' otherwise. Never applied to a whole page."""
    guard = ai_only(programme)
    if guard:
        return guard
    return AI_ONLY_WORDS['ASASI'] if _FOUNDATION_IN.search(_norm(programme or '')) else ''


def page_of_each(lane: str, pages) -> dict:
    """{phrase number: the 1-based page that first shows it, or 0 when no ONE page does} — for the eval (counts)."""
    out = {}
    for k in range(len(OWNER_WORDS.get(lane, ()))):
        out[k + 1] = next((n + 1 for n, page in enumerate(pages or ()) if k in _shown(lane, page)), 0)
    return out
