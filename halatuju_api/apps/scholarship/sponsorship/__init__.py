"""Phase E3 — the sponsor wallet + match/consent state machine.

Money model (decided with the user): a sponsor DONATES into myNADI (final, no bank
refund); their internal balance = donations − allocations that still hold (offered
/active). A sponsor funds a student IN FULL for the admin-set award amount → an
'offered' Sponsorship + an award letter; the student/guardian accepts within a
deadline → 'active', app → 'sponsored', the student leaves the pool. Not accepted
in time (or cancelled) → the allocation stops holding and the amount is back in the
sponsor's balance to redirect — never a bank refund. Tranches/disbursement = E3b.

The package (audit A3.8, 2026-11-10). ``sponsorship.py`` was split, unchanged, into the modules
beside this file and every name it held is re-exported here, so ``from apps.scholarship.sponsorship
import X`` and ``sponsorship.X`` resolve as before. A ``mock.patch`` of a name a function LOOKS UP
must name the module that holds that function, e.g.
``apps.scholarship.sponsorship.offers.send_award_offer_email`` (release_award_offer_emails) or
``sponsorship.lapse._expired_offers`` (lapse_expired_offers).
"""
from .. import branding as _branding
from .. import money
from .. import pool
from .. import status_lock as _status_lock
from ..results_review import accepted_count
from .. import usage as _usage
from ..award_revert import revert_to_pool as _revert_to_pool
from ..emails import (send_award_confirmed_email, send_award_offer_email,
                      send_award_offer_sign_email)
from ..models import Donation, Programme, Sponsorship, SponsorProfile
from ..services import is_minor, record_consent
from ..vircle import raise_setup_task

from .errors import SponsorshipError
from .wallet import (
    _amount_str, _wallet_programmes, programme_ledger, sponsor_available_total, sponsor_balance,
    sponsor_impact, sponsor_programme_balances, sponsor_statement, visible_donations,
)
from .credits import (
    CreditError, _credit_org, _is_accepted_into, cancel_admin_credit, record_admin_credit,
    sign_admin_credit,
)
from .membership import (
    MEMBERSHIP_STATUSES, MembershipError, set_programme_membership, sync_account_membership,
)
from .offers import (
    arm_sign_deadline, award_and_notify, cancel_offer, current_offer, fund_student, is_fundable,
    release_award_offer_emails,
)
from .acceptance import (
    SPONSORSHIP_CONSENT_TYPE, _finalise_award, hold_pending_award, release_pending_awards,
    respond_to_award,
)
from .lapse import (
    _expired_offers, lapse_expired_offers, lapse_holding_sponsorships, logger,
    reinstate_lapsed_sponsorship,
)
