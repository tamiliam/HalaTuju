"""A saved UP_TVET course page (`awam-kursus/kursus?id_kursus=N`) -> plain structure (Bumi Sprint F1).

`read_page(html)` returns what the parser (`tvet_syarat.py`) needs and nothing about people:

    {'name', 'kod', 'institution', 'address', 'negeri', 'website', 'tahap', 'tempoh', 'description',
     'cards': [{'number': '01', 'title': 'Umur', 'subtitle': 'Berumur 17 hingga 35 tahun',
                'joiner': 'DAN' | 'ATAU' | None,      # the divider printed BEFORE this card
                'options': [{'label': 'Syarat Wajib' | 'Syarat Pilihan 1', 'heading': '...',
                             'joiner': 'ATAU' | 'DAN' | None,   # the divider before this option
                             'body': [('text', 'Umur Minimum : 17'), ('table', {...}), ...]}]}]}

A table is `{'headers': [...], 'rows': [[cell, ...], ...]}`. Body tokens keep document order, one
line per `<br>`-separated or block text, so "1. Tamat Tingkatan 5 / Bil. Subjek : 2 / Gred Minimum : G /
<table>" reads as it is printed. The page's coordinator name, telephone and e-mail are never read.
Pure (lxml, already in requirements.lock); no network.
"""
import re

import lxml.html

_SPACE = re.compile(r'\s+')


def _tidy(text):
    return _SPACE.sub(' ', text or '').strip()


def _line(text):
    """A body line without the stray list commas the page prints between items."""
    return _tidy(text).strip(',').strip()


def _has_class(name):
    return f"contains(concat(' ', normalize-space(@class), ' '), ' {name} ')"


def _table(el):
    headers = [_tidy(th.text_content()) for th in el.xpath('.//thead//th')]
    rows = [[_tidy(td.text_content()) for td in tr.xpath('./td')] for tr in el.xpath('.//tbody/tr')]
    return {'headers': headers, 'rows': [r for r in rows if any(r)]}


def _tokens(el, out):
    """Document-order text lines and tables under `el` (a table is one token, not its text)."""
    if el.tag == 'table':
        out.append(('table', _table(el)))
        return out
    if _line(el.text):
        out.append(('text', _line(el.text)))
    for child in el:
        if isinstance(child.tag, str):
            _tokens(child, out)
        if _line(child.tail):
            out.append(('text', _line(child.tail)))
    return out


def _divider(el):
    if el is None or 'logical-divider' not in (el.get('class') or ''):
        return None
    return _tidy(el.text_content()).upper() or None


def _option(el):
    head = el.xpath(f'./div[1]//div[{_has_class("fw-semibold")}]')
    label = _tidy(head[0].text_content()) if head else ''
    heading = _tidy(head[1].text_content()) if len(head) > 1 else ''
    body_el = el.xpath('./div[2]')
    body = _tokens(body_el[0], []) if body_el else []
    return {'label': label, 'heading': heading, 'body': body,
            'joiner': _divider(el.getprevious())}


def _card(el):
    number = el.xpath(f'.//span[{_has_class("requirement-number")}]')
    title = el.xpath(f'.//div[{_has_class("requirement-header")}]//h5')
    subtitle = el.xpath(f'.//div[{_has_class("requirement-header")}]//h5/following-sibling::div[1]')
    options = el.xpath(f'.//div[{_has_class("requirement-option")}]')
    return {'number': _tidy(number[0].text_content()) if number else '',
            'title': _tidy(title[0].text_content()) if title else '',
            'subtitle': _tidy(subtitle[0].text_content()) if subtitle else '',
            'joiner': _divider(el.getprevious()),
            'options': [_option(o) for o in options]}


def _labelled(doc, label):
    """The value printed beside a 'Nama Institusi' / 'Alamat' / 'Negeri' label in the provider block."""
    for node in doc.xpath('//*[normalize-space(.)=$label][not(*[normalize-space(.)=$label])]', label=label):
        sibling = node.getnext()
        if sibling is None:
            continue
        lines = [_tidy(t) for t in sibling.itertext() if _tidy(t)]
        if label != 'Alamat':   # one value; some pages nest the next section inside it
            return lines[0] if lines else ''
        return ' '.join(lines[:lines.index('Negeri')] if 'Negeri' in lines else lines[:3])
    return ''


def read_page(html):
    """The saved page -> the structure in the module doc. Cards are [] when the page has none."""
    doc = lxml.html.fromstring(html)
    cards = [_card(c) for c in doc.xpath(f'//div[{_has_class("requirement-card")}]')]
    title = doc.xpath(f'//h5[{_has_class("card-title")}]')
    kod = doc.xpath(f'//p[{_has_class("course-code-badge")}]')
    return {
        'name': _tidy(title[0].text_content()) if title else '',
        'kod': _tidy(kod[0].text_content()) if kod else '',
        'institution': _labelled(doc, 'Nama Institusi'),
        'address': _labelled(doc, 'Alamat'),
        'negeri': _labelled(doc, 'Negeri'),
        'website': _labelled(doc, 'Laman Web'),
        'tahap': _labelled(doc, 'Tahap Pengajian'),
        'tempoh': _labelled(doc, 'Tempoh Pengajian'),
        'description': _labelled(doc, 'Pengenalan Kursus'),
        'cards': cards,
    }


def card_text(card):
    """One card as flat text (the reviewer's 'source' beside the parsed fields)."""
    parts = [f"{card['number']} {card['title']}".strip()]
    if card['subtitle']:
        parts.append(f"({card['subtitle']})")
    for option in card['options']:
        if option['joiner']:
            parts.append(option['joiner'])
        parts.append(f"[{option['label']}] {option['heading']}".strip())
        for kind, value in option['body']:
            if kind == 'text':
                parts.append(value)
            else:
                parts.append(' ; '.join(' | '.join(row) for row in value['rows']) or '(empty table)')
    return ' / '.join(parts)
