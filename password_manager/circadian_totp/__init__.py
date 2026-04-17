"""Biological-clock-modulated TOTP app.

Uses a user's circadian rhythm (sleep/wake phase) as an additional factor
derived from wearable data so that knowing the TOTP secret alone does not
suffice to generate valid codes.
"""

default_app_config = "circadian_totp.apps.CircadianTotpConfig"
