from django.urls import path
from . import views

urlpatterns = [
    # Alias management
    path('aliases/', views.list_aliases, name='list_aliases'),
    path('aliases/create/', views.create_alias, name='create_alias'),
    path('aliases/<int:alias_id>/', views.alias_detail, name='alias_detail'),
    path('aliases/<int:alias_id>/toggle/', views.toggle_alias, name='toggle_alias'),
    path('aliases/<int:alias_id>/activity/', views.alias_activity, name='alias_activity'),
    
    # Provider management
    path('providers/', views.list_providers, name='list_providers'),
    path('providers/configure/', views.configure_provider, name='configure_provider'),
]

