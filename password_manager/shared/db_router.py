"""
Primary / Replica database router.

Sends all writes to ``default`` and reads to ``replica`` (if configured).
When no ``replica`` database is defined in ``DATABASES``, all operations
transparently fall through to ``default``.

Enable in settings.py::

    DATABASE_ROUTERS = ['shared.db_router.PrimaryReplicaRouter']
"""

from django.conf import settings


def _replica_configured() -> bool:
    return 'replica' in getattr(settings, 'DATABASES', {})


class PrimaryReplicaRouter:
    """Route reads to the replica, writes to the primary."""

    def db_for_read(self, model, **hints):
        if _replica_configured():
            return 'replica'
        return 'default'

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        db_set = {'default', 'replica'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == 'default'
