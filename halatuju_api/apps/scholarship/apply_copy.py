"""The public apply page's copy, per GIFT.

`/scholarship/apply?p=<code>` renders a heading, an intro paragraph and a bulleted
"Who can apply" list. Until 2026-09-09 those were ONE fixed string each, platform-wide, so a
second gift inherited the first gift's advertisement — BrightPath's B40 criteria would have
appeared on Sabah's own apply link.

⚠⚠ THE NUMBERS BEING LOOSER THAN THE ENGINE IS NOT A BUG, AND MUST NOT BE "FIXED".
Sprint 8 (2026-05-24) ruled that the public page advertises the STRICTER bar (5 A's / PNGK 3.0)
while `shortlisting.evaluate()` runs looser (4 A- / PNGK 2.9) deliberately, to catch near-misses.
The owner reaffirmed it 2026-09-09: *"the public facing text need not be exactly same as the
internal filter."* **Nothing here may derive this copy from a round's thresholds.**

⚠ WHAT THIS MODULE DOES NOT HOLD: the platform default. That lives in the message files
(`scholarship.apply.title` / `.intro` / `.criteria1..4`) and is resolved IN THE BROWSER. Putting
those 7 strings x 3 languages into Python as well is the `_SUBJECT_BM` <-> `subjects.ts` drift
trap, recorded three times in `lessons.md`. The server answers WHICH GIFT; the browser answers
which locale and whether to fall back.
"""

import re

# ── Shape ────────────────────────────────────────────────────────────────────────────────────
LOCALES = ('en', 'ms', 'ta')

MAX_TITLE = 120
MAX_INTRO = 400
MAX_BULLET = 200
MAX_BULLETS = 8


class ApplyCopyError(Exception):
    """A refusal the tab renders beside the offending box.

    Carries `field` so the browser can put the message where the reader is looking, rather than
    a blanket "could not save" — the `parents_occupation` lesson (2026-06-07), where a real
    one-sentence answer overflowed a column and the student saw nothing useful.
    """

    def __init__(self, code, field=''):
        super().__init__(code)
        self.code = code
        self.field = field


# ── The ethnicity warning (owner ruling 2026-09-09, Option A: WARN, DO NOT REFUSE) ───────────
#
# ⚠ `decisions.md` 2026-05-25 removed every mention of Indian descent from the public copy,
# because MyNadi Foundation's **Section 44(6)** tax-exempt status requires the programme not to
# discriminate on the basis of race. That decision was written when the copy was OURS. This tab
# hands it to an organisation, so the constraint needs a voice on the screen.
#
# ⚠ IT WARNS AND SAVES. A platform-wide refusal was rejected: ethnicity-scoped scholarships are
# ordinary and lawful in Malaysia, the constraint is MyNadi's rather than the platform's, and a
# tenant running one legitimately must not be blocked by our funder's terms. The detector ships
# anyway so that tightening later is one branch rather than a new feature, and so the words are
# written down instead of re-derived.
#
# ⚠ A LANGUAGE IS NOT AN ETHNICITY. "Bahasa Melayu" and "Bahasa Tamil" are SUBJECT names a real
# criterion will mention ("a credit in Bahasa Melayu"), so those phrases are removed before the
# scan. Without this the guard would cry wolf on the most ordinary bullet anybody writes.
SENSITIVE_TERMS = (
    # English
    'indian', 'chinese', 'malay', 'bumiputera', 'bumiputra',
    'race', 'racial', 'ethnic', 'ethnicity', 'caste',
    'religion', 'religious', 'muslim', 'hindu', 'christian', 'buddhist',
    # Malay
    'bangsa', 'kaum', 'agama', 'india', 'cina', 'melayu', 'islam',
    # Tamil
    'இந்திய', 'சீன', 'மலாய்', 'இனம்', 'சாதி', 'மதம்',
)

#: Phrases stripped before the scan — a language subject, never an ethnicity claim.
_LANGUAGE_PHRASES = (
    'bahasa melayu', 'bahasa malaysia', 'bahasa tamil', 'bahasa cina', 'bahasa inggeris',
    'malay language', 'tamil language', 'chinese language',
    'மலாய் மொழி', 'தமிழ் மொழி', 'சீன மொழி',
)


def sensitive_terms(*parts):
    """Terms in `parts` that touch race, ethnicity or religion. Sorted, case-insensitive.

    Advisory ONLY — no caller refuses on this. See the block above for why.
    """
    haystack = ' '.join(p or '' for p in parts).lower()
    for phrase in _LANGUAGE_PHRASES:
        haystack = haystack.replace(phrase, ' ')
    return tuple(sorted({t for t in SENSITIVE_TERMS if t in haystack}))


# ── Validation + normalisation ───────────────────────────────────────────────────────────────
#
# ⚠ ANGLE BRACKETS ARE REFUSED. This text renders on a public page and is not markup. The apply
# page prints it as text, so a `<script>` would be inert there today — but "inert in the one
# renderer we happen to have" is not a property worth relying on across a redesign.
_MARKUP = re.compile(r'[<>]')


def _clean(value, limit, field):
    text = (value or '').strip()
    if _MARKUP.search(text):
        raise ApplyCopyError('markup', field)
    if len(text) > limit:
        raise ApplyCopyError('too_long', field)
    return text


def normalise(raw):
    """A client payload -> the stored map. Raises `ApplyCopyError` on a refusal.

    Returns `{}` for "this gift uses the platform default" — the ONLY way to say that. A blank
    is a real answer, never a copied default: a copied default rots the day the platform's own
    wording moves (the `OrganisationConfiguration` rule).
    """
    if raw in (None, '', {}):
        return {}
    if not isinstance(raw, dict):
        raise ApplyCopyError('bad_shape')

    out = {}
    for loc in LOCALES:
        block = raw.get(loc) or {}
        if not isinstance(block, dict):
            raise ApplyCopyError('bad_shape', loc)

        title = _clean(block.get('title'), MAX_TITLE, '%s.title' % loc)
        intro = _clean(block.get('intro'), MAX_INTRO, '%s.intro' % loc)

        bullets_raw = block.get('criteria') or []
        if not isinstance(bullets_raw, list):
            raise ApplyCopyError('bad_shape', '%s.criteria' % loc)
        bullets = []
        for i, b in enumerate(bullets_raw):
            text = _clean(b if isinstance(b, str) else '', MAX_BULLET, '%s.criteria' % loc)
            if text:                       # a blank row is the reader tidying up, not an error
                bullets.append(text)
        if len(bullets) > MAX_BULLETS:
            raise ApplyCopyError('too_many', '%s.criteria' % loc)

        # ⚠⚠ ALL-OR-NOTHING PER LANGUAGE, AND THIS IS THE LOAD-BEARING RULE.
        # Per-FIELD fallback would render "Apply for B40 Education Assistance" — the platform's
        # heading — above Sabah's own bullets: one gift's title over another gift's criteria,
        # with nothing failing anywhere. A gift either writes its whole card or uses ours.
        filled = [bool(title), bool(intro), bool(bullets)]
        if any(filled) and not all(filled):
            raise ApplyCopyError('incomplete', loc)

        if all(filled):
            out[loc] = {'title': title, 'intro': intro, 'criteria': bullets}

    # ⚠ ENGLISH IS THE FLOOR. ms/ta fall back to the gift's own ENGLISH (see `for_wire`), so a
    # gift with Malay copy and no English would have nothing to fall back TO for a Tamil reader.
    if out and 'en' not in out:
        raise ApplyCopyError('english_required', 'en')
    return out


def for_wire(programme):
    """The per-locale map the public intake endpoint serves. `{}` = use the platform default.

    ⚠ ms/ta FALL BACK TO THE GIFT'S OWN ENGLISH, NEVER TO THE PLATFORM'S MALAY OR TAMIL — and
    this deliberately DIFFERS from `branding.resolveLang`, which falls back per locale to the
    platform. The difference is the whole point: falling back to the platform's *name* is
    harmless, but falling back to the platform's *criteria* would tell a Malay-reading Sabah
    applicant they must be B40 with five A's. **A wrong-language truth beats a right-language
    falsehood.** Do not "make it consistent" with branding.
    """
    stored = getattr(programme, 'apply_copy', None) or {}
    en = stored.get('en')
    if not en:
        return {}
    return {loc: (stored.get(loc) or en) for loc in LOCALES}


def is_configured(programme):
    """Has this gift written its own card? Drives the tab's empty state, nothing else."""
    return bool((getattr(programme, 'apply_copy', None) or {}).get('en'))
