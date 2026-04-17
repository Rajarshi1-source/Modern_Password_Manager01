"""Self-destruct viewsets."""

from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import PolicyStatus, SelfDestructEvent, SelfDestructPolicy
from .serializers import SelfDestructEventSerializer, SelfDestructPolicySerializer


class SelfDestructPolicyViewSet(viewsets.ModelViewSet):
    """CRUD over self-destruct policies for the authenticated user."""

    permission_classes = [IsAuthenticated]
    serializer_class = SelfDestructPolicySerializer

    def get_queryset(self):
        return SelfDestructPolicy.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        policy = self.get_object()
        policy.status = PolicyStatus.REVOKED
        policy.last_denied_reason = 'revoked'
        policy.save(update_fields=['status', 'last_denied_reason', 'updated_at'])
        return Response(self.get_serializer(policy).data)


class SelfDestructEventViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = SelfDestructEventSerializer

    def get_queryset(self):
        return SelfDestructEvent.objects.filter(
            policy__user=self.request.user,
        ).order_by('-created_at')
