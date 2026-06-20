from django.urls import path, include
from rest_framework.routers import SimpleRouter
from vault.views import ApiVaultItemViewSet, CrudVaultItemViewSet
from vault.views.folder_views import FolderViewSet
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from . import views
from .views.backup_views import BackupViewSet

# PR D (2026-06): vault URLconf rewrite — fixes three independent routing
# defects (all verified with django.urls.resolve/reverse in the canny venv):
#
#   1. `path('', vault_root)` at ^$ shadowed the list, so GET /api/vault/
#      hit the info view instead of ApiVaultItemViewSet.list.
#   2. The empty-prefix r'' ModelViewSet detail route ^(?P<pk>[^/.]+)/$ is a
#      greedy catch-all; registered before folders/backups/items it captured
#      every sibling sub-route as detail(pk='folders'|'backups'|'items'|…).
#   3. CrudVaultItemViewSet was registered at r'vault' under an include
#      already mounted at /api/vault/, so its `sync` action lived at the
#      double-prefixed /api/vault/vault/sync/ while the frontend (api.js,
#      vaultService.js) calls /api/vault/sync/ (a POST->405 dead route).
#
# Fixes: SimpleRouter (no auto API-root at ^$), explicit-prefix viewsets
# registered before the empty-prefix one, vault_root relocated to meta/,
# the r'vault' cruft dropped (its routes/names are referenced nowhere) and
# `sync` mounted explicitly at /api/vault/sync/, and every custom path()
# placed BEFORE the router include so the detail catch-all cannot shadow it.

# SimpleRouter (not DefaultRouter): DefaultRouter prepends an auto API-root
# view at ^$, which would itself shadow the r'' list route we want to serve
# GET /api/vault/.
router = SimpleRouter()

# Explicit-prefix viewsets FIRST so their list/detail routes are matched
# before the empty-prefix detail catch-all registered last.
# API endpoints for folder management
router.register(r'folders', FolderViewSet, basename='folders')
# API endpoints for backup management
router.register(r'backups', BackupViewSet, basename='backup')
# Explicit items prefix (same viewset as the empty-prefix one below); kept
# because callers reference /api/vault/items/ directly.
router.register(r'items', views.VaultItemViewSet, basename='vault-items')

# Empty-prefix registration LAST. Its detail route ^(?P<pk>[^/.]+)/$ is a
# greedy single-segment catch-all, so it must come after every sibling
# sub-route. This serves the list/create at /api/vault/, the item detail
# (and favorite PATCH) at /api/vault/{id}/, and the detail=False actions
# (get_salt, verify_auth, statistics, check_initialization) — those action
# routes are emitted before the detail route within this registration, so
# they still resolve correctly.
router.register(r'', ApiVaultItemViewSet, basename='api-vault')


@api_view(['GET'])
def vault_root(request, format=None):
    """Browsable index for vault endpoints.

    Relocated off ^$ to /api/vault/meta/ in PR D so GET /api/vault/ reaches
    the items list. ``name='vault-root'`` is preserved so the API root view
    (api/urls.py) can still ``reverse('vault-root')``.

    ``sync`` now reverses to /api/vault/sync/ (the explicit path below),
    where the frontend already posts — not the old double-prefixed
    /api/vault/vault/sync/.
    """
    return Response({
        'items': reverse('vault-items-list', request=request, format=format),
        'sync': reverse('vault-sync', request=request, format=format),
        'search': reverse('vault-search', request=request, format=format),
    })


# Combine all URL patterns. Custom path() routes come BEFORE the router
# include so the empty-prefix detail catch-all cannot shadow them.
urlpatterns = [
    # Browsable index, relocated off ^$ (was the cause of the shadowed list).
    path('meta/', vault_root, name='vault-root'),

    # Real cross-device sync. The CrudVaultItemViewSet.sync @action mounted
    # explicitly at /api/vault/sync/ (where api.js / vaultService.js post).
    # Replaces the accidental double-prefixed /api/vault/vault/sync/ route;
    # name 'vault-sync' is preserved for reverse() in vault_root.
    path('sync/', CrudVaultItemViewSet.as_view({'post': 'sync'}), name='vault-sync'),

    path('search/', views.search, name='vault-search'),

    path('create_backup/', BackupViewSet.as_view({'post': 'create_backup'}), name='create-backup'),
    path('restore_backup/<uuid:pk>/', BackupViewSet.as_view({'post': 'restore'}), name='restore-backup'),

    # Shared Folders API
    path('shared-folders/', include('vault.urls_shared_folders')),

    # Auth URLs for the browsable API (optional)
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),

    # Router-generated URLs LAST so the empty-prefix detail catch-all is the
    # final pattern tried.
    path('', include(router.urls)),
]
