"""W3C Verifiable Credentials + DID implementation.

Supports ``did:key`` (Ed25519) for end users and ``did:web`` for the vault
issuer. Credentials are stored in IPFS (Pinata), Arweave, and optionally
anchored on-chain via the existing blockchain app.
"""

default_app_config = "decentralized_identity.apps.DecentralizedIdentityConfig"
