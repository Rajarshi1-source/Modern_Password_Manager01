"""
Support tool: restore an account locked by a recovery notice's "this wasn't
me" link, after support has confirmed the owner's identity.

Refuses an account that was disabled for any other reason, so it cannot lift
an administrator's ban. See recovery_notice.unlock_locked_account for what it
removes and how the owner signs in again.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from auth_module.models import RecoveryNotice
from auth_module.recovery_notice import unlock_locked_account


class Command(BaseCommand):
    help = "Restore an account locked from a recovery notice's cancel link."

    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
        parser.add_argument('--operator', required=True, help='Who is running this (for the audit log).')
        parser.add_argument('--reason', required=True, help='Ticket and how identity was confirmed.')

    def handle(self, *args, **opts):
        if not opts['operator'].strip() or not opts['reason'].strip():
            raise CommandError('--operator and --reason must not be empty')
        with transaction.atomic():
            user = User.objects.select_for_update().filter(username=opts['username']).first()
            if user is None:
                raise CommandError(f"user '{opts['username']}' not found")
            if user.is_active:
                raise CommandError('the account is not locked')
            if not RecoveryNotice.objects.filter(user=user, locked_account=True).exists():
                raise CommandError('the account was not locked from a recovery notice; refusing')
            unlock_locked_account(user, opts['operator'], opts['reason'])
        self.stdout.write(
            f"Unlocked '{user.username}'. Its sign-in password and passkeys were removed; the owner "
            f'was emailed at {user.email} and sets a new password with "Forgot password".'
        )
