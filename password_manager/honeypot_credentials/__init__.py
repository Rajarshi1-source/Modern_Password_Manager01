"""
honeypot_credentials
====================

Believable but fake credentials served to attackers who compromise the vault.
Any access to a honeypot triggers a silent alarm to the real owner and
records a forensic trail (IP, UA, geo, session) for post-incident analysis.

Everything honeypot-related is isolated from the real vault retrieve path
so a bug in this app can never expose real plaintext.
"""

default_app_config = 'honeypot_credentials.apps.HoneypotCredentialsConfig'
