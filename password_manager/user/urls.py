from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from . import views

@api_view(['GET'])
def user_root(request, format=None):
    """Entry point for user endpoints"""
    return Response({
        'profile': reverse('user-profile', request=request, format=format),
        'emergency-access': reverse('user-emergency-access', request=request, format=format),
        'preferences': reverse('user-preferences', request=request, format=format),
    })

# If you have ViewSets, you can register them here
router = DefaultRouter()
# router.register(r'profiles', views.UserProfileViewSet, basename='user-profile')

urlpatterns = [
    path('', user_root, name='user-root'),
    
    # Include any router-generated URLs
    path('', include(router.urls)),
    
    # Individual endpoints for user operations
    path('profile/', views.profile, name='user-profile'),
    path('preferences/', views.preferences, name='user-preferences'),
    
    # Emergency access main endpoint
    path('emergency-access/', views.emergency_access, name='user-emergency-access'),
    
    # Emergency contacts URLs
    path('emergency-contacts/', views.emergency_contacts, name='emergency-contacts'),
    path('emergency-contacts/<int:contact_id>/', views.emergency_contact_update, name='emergency-contact-update'),
    path('emergency-invitation-response/', views.respond_to_invitation, name='emergency-invitation-response'),
    path('emergency-request/', views.request_emergency_access, name='emergency-request'),
    path('emergency-request-response/', views.respond_to_access_request, name='emergency-request-response'),
    path('emergency-access-requests/', views.check_access_requests, name='emergency-access-requests'),
    path('emergency-vault/<uuid:request_id>/', views.access_emergency_vault, name='emergency-vault'),
]
