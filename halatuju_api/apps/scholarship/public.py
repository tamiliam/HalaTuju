"""The public face of the scholarship app, for the OTHER apps (audit A3.13, RD-04, TD-414).

The courses app reaches back into scholarship for a short list of things (the programme and
document models, the family copy rules, the WhatsApp and e-mail senders, the platform constants).
Before this module each of those was imported from whichever scholarship file held it. This
facade is the one door; a scholarship file behind it may move without courses noticing. It is the
mirror of `apps/courses/public.py` (A3.12).

Rules:
- Re-export only. Nothing here computes, so the facade adds no behaviour. A re-exported name is the
  SAME object as the one in its home module (`public.whatsapp is apps.scholarship.whatsapp`).
- A test that replaces a name patches it where the CALLER looks it up. Modules are re-exported as
  modules, so `mock.patch('apps.scholarship.whatsapp.send_otp')` still lands on the object courses
  calls.
- Callers import from here INSIDE a function, never at module level: this module loads the
  scholarship models, and the back-edge must not run at app-load (the code-standards budget
  `courses_to_scholarship_module_level_imports` stays 0).
- Part 1 covers the five courses files that are free to move. `views_admin` (and the staff_*
  files) still import scholarship directly; they join when their owning sprints land.
"""
from . import birth_state, constants, emails, identity, whatsapp
from .family import (
    DECIDED_STATUSES,
    PROFILE_FAMILY_FIELDS,
    PROFILE_PATHWAY_FIELDS,
    copy_family_roster,
    copy_pathway,
)
from .models import ApplicantDocument, Programme

__all__ = [
    'ApplicantDocument', 'DECIDED_STATUSES', 'PROFILE_FAMILY_FIELDS', 'PROFILE_PATHWAY_FIELDS',
    'Programme', 'birth_state', 'constants', 'copy_family_roster', 'copy_pathway', 'emails',
    'identity', 'whatsapp',
]
