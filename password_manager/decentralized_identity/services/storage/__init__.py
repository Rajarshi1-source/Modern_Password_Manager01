"""Pluggable storage backends for Verifiable Credentials.

All backends are optional: if the corresponding environment variable is not
configured the upload short-circuits returning ``None`` and the caller simply
records a ``None`` reference in the ``VerifiableCredential.storage_refs`` map.
"""

from .arweave_storage import upload_to_arweave  # noqa: F401
from .chain_anchor import anchor_commitment  # noqa: F401
from .ipfs_storage import upload_to_ipfs  # noqa: F401
