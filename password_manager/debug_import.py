"""Debug script to get full traceback from security imports"""
import os
import sys
import traceback

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.settings')

try:
    import django
    django.setup()
    print("Django loaded successfully")
    
    # Now try to import the problematic modules
    print("\n1. Testing security.tasks import...")
    from security.tasks import check_for_breaches
    print("   check_for_breaches imported:", check_for_breaches)
    
    print("\n2. Testing security.serializers import...")
    from security.serializers import SocialMediaAccountSerializer
    print("   SocialMediaAccountSerializer imported:", SocialMediaAccountSerializer)
    
    print("\n3. Testing security.urls import...")
    from security import urls
    print("   security.urls imported successfully")
    
    print("\n✓ All imports successful!")
    
except Exception as e:
    print("\n\n========== FULL TRACEBACK ==========")
    traceback.print_exc()
    print("=====================================\n")
