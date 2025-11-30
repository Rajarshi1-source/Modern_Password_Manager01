# Import models from the new vault_models module
from .vault_models import EncryptedVaultItem
from .folder_models import VaultFolder

# Import models from other specialized modules
from .Breach_Alerts import BreachAlert
from .Key_derivation_models import UserSalt, AuditLog, DeletedItem
from .shared_folder_models import (
    SharedFolder,
    SharedFolderMember,
    SharedVaultItem,
    SharedFolderKey,
    SharedFolderActivity
)

# Expose these models at the module level
__all__ = [
    'EncryptedVaultItem',
    'VaultFolder',
    'BreachAlert',
    'UserSalt',
    'AuditLog',
    'DeletedItem',
    'SharedFolder',
    'SharedFolderMember',
    'SharedVaultItem',
    'SharedFolderKey',
    'SharedFolderActivity',
]

# This ensures all parts of the application can import these models as:
# from vault.models import EncryptedVaultItem, BreachAlert, etc.
