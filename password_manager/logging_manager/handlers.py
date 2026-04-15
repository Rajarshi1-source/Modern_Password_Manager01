import logging
import threading

_in_emit = threading.local()

# Errors that indicate the DB table doesn't exist yet (pre-migration startup).
# Silently skip rather than printing a traceback on every boot.
_TABLE_MISSING_ERRORS = (
    'does not exist',        # psycopg / PostgreSQL
    'no such table',         # SQLite
    'doesn\'t exist',        # MySQL
    'Table',                 # generic fallback
)


def _is_table_missing(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(phrase.lower() in msg for phrase in _TABLE_MISSING_ERRORS)


class DatabaseLogHandler(logging.Handler):
    def emit(self, record):
        if getattr(_in_emit, 'active', False):
            return
        _in_emit.active = True
        try:
            from django.db import DatabaseError

            from .models import SystemLog

            request = getattr(record, 'request', None)
            user = None
            ip_address = None
            user_agent = ''
            request_path = ''
            request_method = ''

            if request:
                user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
                ip_address = request.META.get('REMOTE_ADDR')
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                request_path = request.path
                request_method = request.method

            SystemLog.objects.create(
                level=record.levelname,
                logger_name=record.name,
                message=self.format(record),
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
                request_path=request_path,
                request_method=request_method
            )
        except Exception as exc:
            # Silently discard writes that fail because the table doesn't
            # exist yet (e.g. during `manage.py migrate` on a fresh DB).
            if _is_table_missing(exc):
                return
            self.handleError(record)
        finally:
            _in_emit.active = False
