"""Service layer for ambient_auth."""

from .ambient_fusion_service import (
    FusionResult,
    ingest,
    promote_context,
    rename_context,
    delete_context,
    reset_baseline,
    recompute_signal_reliability,
    list_contexts,
    recent_observations,
    ensure_profile,
    ensure_signal_configs,
    get_signal_configs,
    set_signal_config,
    latest_signal,
)

__all__ = [
    "FusionResult",
    "ingest",
    "promote_context",
    "rename_context",
    "delete_context",
    "reset_baseline",
    "recompute_signal_reliability",
    "list_contexts",
    "recent_observations",
    "ensure_profile",
    "ensure_signal_configs",
    "get_signal_configs",
    "set_signal_config",
    "latest_signal",
]
