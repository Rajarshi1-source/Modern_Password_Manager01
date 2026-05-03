# Layered Recovery Mesh views package.
#
# Each view module here is purely additive REST surface for the
# wrapped-DEK + recovery factor + time-locked recovery flows.
#
# ZK invariant: nothing in this package decrypts a wrapped blob.
# Server validates envelope shape only. The blob (and any recovery
# secret used to derive a KEK) is opaque ciphertext from the server's
# point of view.
