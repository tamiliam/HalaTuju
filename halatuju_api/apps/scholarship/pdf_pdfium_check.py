"""S-visible fix round 5 (2026-11-19): pdfium, the engine that PAINTS the page, judges each page pypdf read.

Four review rounds each found one more place where pypdf (which reads the text layer) and pdfium (which
paints the page image) parse one PDF differently, so pypdf extracted text pdfium never paints. The walk in
``pdf_pages`` mirrors pypdf and stays (defence in depth); this check closes the class by asking pdfium for its
OWN reading of every page whose pypdf text would be used. pdfium's page objects are walked (forms' contents
too, recursively), and the page is hidden (the Vision route) when:

a. any TEXT object has a render mode that does not paint (3, 7, or anything not 0-2 / 4-6);
b. any TEXT object, or a form object holding it, carries a marked-content mark named ``OC`` (pdfium's own
   view of optional content) — unless, exactly as the walk's ``oc_hides``, the mark is a plain /OCG (its
   parameters only Type, a name, and Name) and the document's configuration switches nothing off. One real
   genuine corpus document draws text in such a plain layer that is on, so "any OC mark" would push it off
   its free layer. An /OCMD, a /Usage, an unreadable mark: hidden;
c. pypdf extracted letters or digits from the page but pdfium finds NO text object on it at all;
d. pdfium cannot open the PDF, sees another page count, fails on the page, or the document's pages hold
   more than `MAX_OBJECTS` page objects between them.

Fix round 8: the pdfium part runs in `pdfium_worker` (a child process, killed at its time limit: `pdfium_run.TIMEOUT_S`
and, round 9, the document's `pdfium_run.DOC_BUDGET_S` left).

Per OBJECT, not per character: a text-page character count was tried first and REJECTED — pdfium's text
page drops overlapping duplicate characters (a repeated draw, fake bold), so 6 real genuine documents lost
their free layer. Known limit: pdfium's API does not show a form XObject's own /OC entry; the walk judges it.
"""
from .pdf_layer_guards import PLAIN_OCG_KEYS
from .pdf_pdfium_load import load_check

#: Page objects pdfium lists on the judged pages of ONE document, forms' contents included (each form call
#: is its own object tree). Corpus max (533 PDFs, measured 2026-11-19): 9,101 on one document (doc 1409:
#: 4,099). Past it every page still being judged is hidden.
MAX_OBJECTS = 20_000
#: The parameters of an OC mark for a provably shown /OCG (`pdf_layer_guards.PLAIN_OCG_KEYS`, unslashed).
_PLAIN_OCG_PARAMS = sorted(k[1:] for k in PLAIN_OCG_KEYS)


def hidden_pages(data: bytes, page_count: int, judged: dict, oc_may_be_off: bool, reader=None) -> set:
    """The page indices in ``judged`` ({page index: pypdf's text of it}) that pdfium says do not paint all
    their text (a-d above; e, fix round 6: a page outside `pdf_pdfium_load`'s whitelist). ``reader`` (fix round
    6): pypdf's reader of ``data``; EVERY judged page must first pass `pdf_pdfium_load.load_check` (its resources
    whitelisted and charged) or it is hidden and pdfium never loads it — fix round 8: a page whose pypdf text is
    blank too, since a later reader (the SPM word boxes) may still load it. Only a page with text is then given to
    pdfium (a blank page has nothing to use). ALL of those are hidden when pdfium cannot open the PDF, sees another
    page count, or its child process fails or runs past its time limit, or the document has spent its pdfium budget
    (`pdfium_run`) — never the hidden text.
    ``oc_may_be_off``: the document's optional-content configuration may switch a layer off
    (`pdf_layer_guards._doc_may_switch_off`). pdfium runs in ONE child process for the whole document."""
    from . import pdfium_run
    hidden, state = set(), {}
    for i in list(judged) if reader is not None else ():
        try:
            load_check(reader.pages[i], reader, state)
        except Exception:  # outside the whitelist or past the load budget: hidden, never loaded
            hidden.add(i)
    wanted = {i: any(c.isalnum() for c in t) for i, t in judged.items()
              if t and not t.isspace() and i not in hidden}
    if not wanted:
        return hidden
    answer = pdfium_run.ask(data, [{'op': 'paints', 'pages': [[i, a] for i, a in sorted(wanted.items())],
                                    'count': page_count, 'oc_off': bool(oc_may_be_off), 'max_objects': MAX_OBJECTS,
                                    'plain': _PLAIN_OCG_PARAMS}])
    if answer is None:                      # the child failed or was killed: undecidable is hidden
        return hidden | set(wanted)
    return hidden | (set(answer[0]['hidden']) & set(wanted))
