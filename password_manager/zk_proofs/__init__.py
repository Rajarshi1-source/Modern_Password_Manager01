"""
Zero-Knowledge Password Verification Protocol.

Implements a pluggable provider interface for ZK proofs over password-derived
commitments. The default provider uses Pedersen commitments + Schnorr proofs of
equality on secp256k1; future providers (Groth16/PLONK zk-SNARKs) can register
themselves under the same `ZKProofProvider` interface without touching callers.
"""

default_app_config = "zk_proofs.apps.ZkProofsConfig"
