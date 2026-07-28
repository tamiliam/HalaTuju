"""The block-splitting template engine shared by every editable-email family.

Extracted from `partner_comms` on 2026-07-28, when sponsor comms became the second family to
need it. It knows three things and deliberately nothing else:

  * a stored body splits on BLANK LINES into paragraphs;
  * a block that is *exactly* a structural token becomes the table/list that token names;
  * values are HTML-escaped on the way in, so a stray `<` in a name cannot break an email.

It knows nothing about partners, sponsors, organisations or students. Each family supplies its
own ``scalars`` (plain `{token}` → value) and ``blocks`` (`{token}` → the pre-rendered
`(html, text)` pair), and gets back the three parts a sender needs. That split is the point: the
FAMILIES own their vocabulary, this module owns the mechanics, and there is one implementation
of the mechanics rather than one per family drifting apart.

Import direction: this module imports nothing from the project. `partner_comms` and
`sponsor_comms` import it, never the reverse.
"""
import re
from html import escape as html_escape

# A placeholder token: lowercase + underscores only, so prose containing a brace cannot be
# mistaken for one.
TOKEN_RE = re.compile(r'\{([a-z_]+)\}')

# How far a structural token is allowed to expand when it appears in a SUBJECT line.
SUBJECT_TOKEN_CHARS = 120


def esc(value):
    """HTML-escape an interpolated value. Names come from the database, so this is what stops a
    stray `<` in someone's name from breaking the markup of an email."""
    return html_escape('' if value is None else str(value), quote=True)


def unknown_placeholders(allowed, *parts):
    """Tokens in `parts` that `allowed` does not supply — sorted, so an error message is stable.

    An empty tuple means the template is safe to save. This is the guard that stops a template
    reaching an inbox with a literal `{whatever}` in it, and for the sponsor family it is also a
    privacy control: a token nobody supplies cannot resolve to a student's identity.
    """
    found = set()
    for part in parts:
        found.update(TOKEN_RE.findall(part or ''))
    return tuple(sorted(found - set(allowed or ())))


def banned_phrases(banned, *parts):
    """Phrases from `banned` present in `parts`, sorted and case-insensitively matched.

    A copy rule that lives only in a reviewer's head gets edited away later; this makes the rule
    refuse the save. Each family owns its own list — what counts as the wrong voice for a partner
    organisation is not what counts as the wrong voice for a donor.
    """
    haystack = ' '.join(p or '' for p in parts).lower()
    return tuple(sorted({p for p in (banned or ()) if p in haystack}))


def list_blocks(items):
    """A plain bulleted list as `(html, text)` — the one structural block every family wants."""
    lis = ''.join('<li style="margin-bottom:3px;">' + esc(i) + '</li>' for i in items)
    return ('<ul style="margin:0 0 12px;padding-left:22px;">' + lis + '</ul>',
            '\n'.join('- ' + str(i) for i in items))


def fill(text, scalars, escape):
    """Substitute the scalar tokens.

    The template text is escaped by `render` BEFORE this runs (a `{token}` survives escaping), so
    `escape` here decides whether the VALUES are escaped — True for the HTML part, False for the
    plain-text part.
    """
    out = text
    for token, value in scalars.items():
        out = out.replace('{' + token + '}', esc(value) if escape else str(value))
    return out


def render(subject, body, scalars, blocks):
    """A stored template + one recipient's resolved values → `(subject, text_body, html_body)`.

    `html_body` is the INNER html; the caller wraps it in the shared email shell, which is why
    this module imports no email code.

    A structural token appearing in the SUBJECT is flattened to a one-line summary rather than
    rendered or left raw — nobody should receive a subject line reading `{student_cards}`.
    """
    out_subject = fill(subject or '', scalars, escape=False)
    for token, (_html, text_form) in blocks.items():
        out_subject = out_subject.replace(
            '{' + token + '}', ' '.join(text_form.split())[:SUBJECT_TOKEN_CHARS])

    html_parts, text_parts = [], []
    for raw in re.split(r'\n\s*\n', body or ''):
        block = raw.strip()
        if not block:
            continue
        token = block[1:-1] if block.startswith('{') and block.endswith('}') else ''
        if token in blocks:
            html_form, text_form = blocks[token]
            html_parts.append(html_form)
            text_parts.append(text_form)
            continue
        filled = fill(block, scalars, escape=False)
        # A block that fills to nothing is DROPPED, not rendered as an empty paragraph. This is
        # what lets a template carry an optional token on its own line — the invite's personal
        # note, say, which most inviters leave blank — without a stray gap in the layout for
        # everyone who omits it.
        if not filled.strip():
            continue
        text_parts.append(filled)
        safe = fill(html_escape(block, quote=False), scalars, escape=True)
        html_parts.append('<p style="margin:0 0 14px;">' + safe.replace('\n', '<br>') + '</p>')

    return out_subject, '\n\n'.join(text_parts), ''.join(html_parts)
