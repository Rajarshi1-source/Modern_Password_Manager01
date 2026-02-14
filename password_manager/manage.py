#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # Suppress liboqs installation spam on local Windows development
    # This mocks the module so imports raise ImportError immediately instead of running the installer
    if os.name == 'nt' and not os.environ.get('DOCKER_CONTAINER'):
        sys.modules['oqs'] = None

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
