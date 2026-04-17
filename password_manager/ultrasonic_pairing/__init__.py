"""Ultrasonic device pairing app.

Supports short-range, over-the-air cryptographic pairing using
inaudible (18.5 / 19.5 kHz) audio FSK as the out-of-band channel
for a standard ECDH-with-SAS exchange. Two purposes are supported:

* ``device_enroll`` — attach a new device to an existing account.
* ``item_share``   — hand off an encrypted vault item in person.
"""

default_app_config = 'ultrasonic_pairing.apps.UltrasonicPairingConfig'
