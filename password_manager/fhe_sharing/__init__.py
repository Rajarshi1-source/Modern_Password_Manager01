"""
FHE Sharing - Homomorphic Password Sharing

Enables users to share passwords via FHE-encrypted autofill tokens.
Recipients can USE (autofill) passwords but CANNOT SEE them.

Use cases:
- Team accounts with need-to-use separation
- Temporary contractor access
- Compliance: "Need to use, need to know"
"""

default_app_config = 'fhe_sharing.apps.FheSharingConfig'
