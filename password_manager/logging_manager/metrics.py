"""Prometheus metrics for backup freshness (scraped from the backend's /metrics)."""

import logging

from prometheus_client.core import GaugeMetricFamily

logger = logging.getLogger(__name__)

LAST_SUCCESS = 'vault_backup_last_success_timestamp_seconds'
LAST_SIZE = 'vault_backup_last_success_size_bytes'


class BackupStatusCollector:
    """Reads BackupStatus at scrape time.

    No successful backup yet -> timestamp 0, so the staleness alert fires
    (there is no backup). A database error -> no sample at all, which the
    ``VaultBackupMetricMissing`` alert catches, instead of a made-up value.
    """

    def describe(self):
        # Without describe(), registering would call collect() and query the
        # database during app start-up.
        return [
            GaugeMetricFamily(LAST_SUCCESS, ''),
            GaugeMetricFamily(LAST_SIZE, ''),
        ]

    def collect(self):
        from .models import BackupStatus
        try:
            rows = list(BackupStatus.objects.values_list('name', 'last_success_at', 'last_size_bytes'))
        except Exception:
            logger.warning("backup status unavailable for /metrics", exc_info=True)
            return
        ts = GaugeMetricFamily(
            LAST_SUCCESS, 'Unix time of the last successful, durable backup.', labels=['backup'])
        size = GaugeMetricFamily(
            LAST_SIZE, 'Size in bytes of the last successful backup file.', labels=['backup'])
        by_name = {name: (at, nbytes) for name, at, nbytes in rows}
        by_name.setdefault('db-backup', (None, 0))
        for name, (at, nbytes) in sorted(by_name.items()):
            ts.add_metric([name], at.timestamp() if at else 0)
            size.add_metric([name], nbytes)
        yield ts
        yield size


_registered = False


def register():
    global _registered
    if _registered:
        return
    from prometheus_client import REGISTRY
    try:
        REGISTRY.register(BackupStatusCollector())
    except ValueError:  # already registered (e.g. module reloaded)
        pass
    _registered = True
