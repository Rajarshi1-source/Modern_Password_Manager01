"""
DRF viewsets for honeypot management.

Two resources are exposed:

* ``HoneypotCredentialViewSet`` — CRUD over the planted honeypots.
* ``HoneypotAccessEventViewSet`` — read-only forensic log.

The decoy password is NEVER returned by these endpoints; the owner can
inspect the decoy via a dedicated ``reveal`` action when needed (for
debugging / red-team drills).
"""

from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    DecoyStrategy,
    HoneypotAccessEvent,
    HoneypotCredential,
    HoneypotTemplate,
)
from .serializers import (
    HoneypotAccessEventSerializer,
    HoneypotCredentialSerializer,
    HoneypotTemplateSerializer,
)
from .services import HoneypotService


class HoneypotCredentialViewSet(viewsets.ModelViewSet):
    """CRUD for honeypot credentials owned by the authenticated user."""

    permission_classes = [IsAuthenticated]
    serializer_class = HoneypotCredentialSerializer

    def get_queryset(self):
        return HoneypotCredential.objects.filter(user=self.request.user).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        data = request.data
        service = HoneypotService()
        hp = service.create(
            user=request.user,
            label=data.get('label') or 'Honeypot',
            strategy=data.get('strategy') or DecoyStrategy.STATIC,
            template_id=data.get('template') or None,
            alert_channels=data.get('alert_channels'),
            fake_site=data.get('fake_site'),
            fake_username=data.get('fake_username'),
            decoy_password=data.get('decoy_password'),
        )
        return Response(
            self.get_serializer(hp).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def rotate(self, request, pk=None):
        """Manually rotate the decoy password."""
        hp = self.get_object()
        HoneypotService().rotate_decoy(hp)
        return Response(self.get_serializer(hp).data)

    @action(detail=True, methods=['get'])
    def reveal(self, request, pk=None):
        """Owner-only decoy peek for red-team drills. Does NOT fire alerts."""
        hp = self.get_object()
        return Response(HoneypotService().reveal_decoy(hp))


class HoneypotAccessEventViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Read-only access to forensic events for the authenticated user."""

    permission_classes = [IsAuthenticated]
    serializer_class = HoneypotAccessEventSerializer

    def get_queryset(self):
        return HoneypotAccessEvent.objects.filter(
            honeypot__user=self.request.user,
        ).select_related('honeypot').order_by('-accessed_at')


class HoneypotTemplateViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Built-in templates are global and read-only from the API."""

    permission_classes = [IsAuthenticated]
    serializer_class = HoneypotTemplateSerializer
    queryset = HoneypotTemplate.objects.all().order_by('name')
