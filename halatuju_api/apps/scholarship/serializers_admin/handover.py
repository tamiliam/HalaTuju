"""TD-613: the handover answers the cockpit's Reviewer card and the list picker read, served by ONE
mixin so the detail and the list cannot drift (review F2). Each is the service's own rule, never a
copy: `assignable` (`services.is_assignable`), `needs_new_holder` (`services.needs_new_holder`) and
`may_unassign` (`services.may_unassign`, the unassign rule `assign_reviewer` refuses by). The web
reads only these, never a role. The fields are declared on each serializer (DRF reads declared
fields from Serializer classes only)."""


class ServesTheHandover:
    def get_assignable(self, obj):
        from ..services import is_assignable
        return is_assignable(obj)

    def get_needs_new_holder(self, obj):
        from ..services import needs_new_holder
        return needs_new_holder(obj)

    def get_may_unassign(self, obj):
        from ..services import may_unassign
        return may_unassign(obj)
