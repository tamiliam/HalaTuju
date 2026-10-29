"""The student's own maintenance answers, SERVED (student maintenance Sprint 1, 2026-10-29).

A mixin for ``serializers.ApplicationReadSerializer`` (which sits at its ``oversize_files``
allowance, so the fields live here). The student page never re-derives any of these from statuses:

  * ``in_maintenance``     — ``maintenance_scope.is_in_maintenance`` (awarded with a live wallet,
                             active, maintenance);
  * ``has_file``           — ``maintenance_scope.has_file``: in maintenance, or closed after it
                             (read-only). Decides who reaches the in-programme page;
  * ``can_record_results`` — ``in_programme.can_record_results`` (active / maintenance only until
                             Sprint 4 — adversarial review M2). Decides whether the form shows;
  * ``support_paused``     — ``maintenance.is_on_hold``. The COARSE answer the student sees instead
                             of the raw ``maintenance_substate`` (review L5): probation is a staff
                             flag and never reaches her screen. The admin serializer keeps the field.

All four read fields already on the row — no query.
"""
from rest_framework import serializers


class StudentMaintenanceFields(serializers.Serializer):
    in_maintenance = serializers.SerializerMethodField()
    has_file = serializers.SerializerMethodField()
    can_record_results = serializers.SerializerMethodField()
    support_paused = serializers.SerializerMethodField()

    def get_in_maintenance(self, obj):
        from .maintenance_scope import is_in_maintenance
        return is_in_maintenance(obj)

    def get_has_file(self, obj):
        from .maintenance_scope import has_file
        return has_file(obj)

    def get_can_record_results(self, obj):
        from .in_programme import can_record_results
        return can_record_results(obj)

    def get_support_paused(self, obj):
        from .maintenance import is_on_hold
        return is_on_hold(obj)
