"""Social Proof-Based Recovery.

A web-of-trust recovery module that lets a quorum of vouchers (existing users
or external DIDs) release Shamir shards of a master recovery secret. Uses
Ed25519 signatures, Pedersen/Schnorr equality proofs, and the existing
``password_reputation`` ledger for stake management.
"""

default_app_config = "social_recovery.apps.SocialRecoveryConfig"
