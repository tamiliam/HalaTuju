"""`decision_mail` on the admin detail read (TD-358, audit sprint A2.6): '' / 'no_address' / 'unsent'
(`services.decision_mail.untold_reason`) — the student was not emailed her decision, so an officer must
tell her another way. Appended in `to_representation`, not declared as a field, so the host serializer
file does not grow (the same pattern as `serializers_admin_gift.ServesTheGift`). Admin-only: never mix
it into a student-facing serializer."""
from .services.decision_mail import untold_reason


class ServesTheDecisionMail:
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['decision_mail'] = untold_reason(instance)
        return data
