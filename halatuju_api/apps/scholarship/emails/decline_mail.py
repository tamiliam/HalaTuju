"""The decline mail and its HTML dressing. Its copy lives in `student_decisions`.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from .sending import _html_email_shell, _send_html
from .shared import _DEFAULT_NAME, _P
from .student_decisions import FAIL_BODIES, FAIL_SUBJECTS, _DECLINE_TEMPLATES, normalise_lang


def _decline_html(text_body):
    """Render a plain-text decline body as a branded HTML card: blank-line-separated
    paragraphs become <p>, single newlines (the sign-off) become <br>. Escaped. The
    sign-off team name (the line after the salutation in the final paragraph) is bolded
    in the HTML only — the plain-text fallback stays clean."""
    import html as _h
    paras = [p.strip() for p in (text_body or '').split('\n\n') if p.strip()]
    blocks = []
    for i, p in enumerate(paras):
        esc = _h.escape(p)
        # Final paragraph + a salutation/team split → bold the team-name line.
        if i == len(paras) - 1 and '\n' in p:
            head, _sep, team = esc.rpartition('\n')
            esc = '%s\n<strong>%s</strong>' % (head, team)
        blocks.append('<p style="margin:0 0 14px;">%s</p>' % esc.replace('\n', '<br>'))
    return _html_email_shell(''.join(blocks))


def send_decline_email(to_email, applicant_name, programme_name, category='', lang='en'):
    """Send the right decline email for a rejection bucket, as HTML (branded, warm) with a
    plain-text fallback — From info@, reply-to help@. merit/need/interview get bucket-specific
    copy (the interview bucket thanks the student for their time and for submitting their
    documents); ineligible/contractual/unknown fall back to the generic warm decline (FAIL_*)."""
    if not to_email:
        return False
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    subjects, bodies = _DECLINE_TEMPLATES.get(category, (FAIL_SUBJECTS, FAIL_BODIES))
    frontend = _P.frontend_url
    fmt = {'name': name, 'programme': programme_name,
           'link': f'{frontend}/scholarship/application'}
    subject = subjects[lang].format(programme=programme_name)
    text_body = bodies[lang].format(**fmt)
    return _send_html(
        to_email, subject, text_body, _decline_html(text_body),
        from_email=_P.email_from,
        reply_to=[_P.email_support],
    )
