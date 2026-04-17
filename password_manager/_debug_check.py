import os
print('DEBUG env=', repr(os.environ.get('DEBUG')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.settings')
import django
django.setup()
from django.conf import settings
print('settings.DEBUG=', settings.DEBUG)
print('settings.SECURE_SSL_REDIRECT=', settings.SECURE_SSL_REDIRECT)
