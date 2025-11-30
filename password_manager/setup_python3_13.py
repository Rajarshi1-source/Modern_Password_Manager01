#!/usr/bin/env python3
"""
Python 3.13 Compatibility Setup Script

This script:
1. Checks if you're running Python 3.13+
2. Installs the legacy-cgi package if needed
3. Verifies that the patch is working correctly

Usage:
    python3 setup_python3_13.py
"""

import sys
import subprocess
import importlib.util
import os

def check_python_version():
    """Check if running Python 3.13 or newer."""
    version = sys.version_info
    if version >= (3, 13):
        print(f"[✓] Running Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"[i] Running Python {version.major}.{version.minor}.{version.micro}")
        print("    This script is only needed for Python 3.13 and newer.")
        return False

def check_legacy_cgi():
    """Check if legacy-cgi is installed."""
    # Try direct import first (most reliable method)
    try:
        import legacy_cgi
        print("[✓] legacy-cgi package is installed")
        return True
    except ImportError:
        # Then check if the dist-info directory exists
        package_path = os.path.join(os.path.dirname(os.__file__), '..', 'site-packages', 'legacy_cgi-2.6.3.dist-info')
        if os.path.exists(package_path):
            print("[✓] legacy-cgi package is installed (found dist-info)")
            return True
        
        # Finally try with importlib.util
        legacy_cgi_spec = importlib.util.find_spec("legacy_cgi")
        if legacy_cgi_spec:
            print("[✓] legacy-cgi package is installed (found via importlib)")
            return True
        
        print("[✗] legacy-cgi package is not installed")
        return False

def install_legacy_cgi():
    """Install the legacy-cgi package."""
    print("Installing legacy-cgi package...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "legacy-cgi>=1.0.0"])
        print("[✓] Successfully installed legacy-cgi")
        return True
    except subprocess.CalledProcessError:
        print("[✗] Failed to install legacy-cgi")
        return False

def test_patch():
    """Test if the patching mechanism works."""
    try:
        print("Testing cgi module patch...")
        
        # First try to import directly - if this works, no patch needed
        try:
            import cgi
            print("[✓] Native cgi module exists or patch is working")
            return True
        except ImportError:
            # If direct import fails, explicitly try to import legacy_cgi
            pass
        
        # Load the legacy_cgi module and apply patch
        try:
            import legacy_cgi
            # Apply patch manually
            sys.modules['cgi'] = legacy_cgi
            # Verify patch worked by importing cgi
            import cgi
            print("[✓] Successfully patched cgi module with legacy_cgi")
            return True
        except ImportError as e:
            print(f"[✗] Failed to patch cgi module: {e}")
            return False
    except Exception as e:
        print(f"[✗] Failed to patch cgi module: {e}")
        return False

def setup_project_dependencies():
    """Install project dependencies from requirements.txt."""
    print("\nInstalling project dependencies...")
    try:
        requirements_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'requirements.txt')
        if not os.path.exists(requirements_path):
            print(f"[✗] Could not find requirements.txt at {requirements_path}")
            return False
            
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path])
        print("[✓] Successfully installed dependencies")
        return True
    except subprocess.CalledProcessError:
        print("[✗] Failed to install dependencies")
        return False

def fix_push_notifications():
    """Patch django-push-notifications to work with newer Django versions."""
    print("\nChecking and patching django-push-notifications...")
    try:
        import site
        for site_path in site.getsitepackages():
            models_path = os.path.join(site_path, 'push_notifications', 'models.py')
            if os.path.exists(models_path):
                with open(models_path, 'r') as f:
                    content = f.read()
                
                if 'from django.utils.translation import ugettext_lazy as _' in content:
                    # Replace ugettext_lazy with gettext_lazy
                    content = content.replace(
                        'from django.utils.translation import ugettext_lazy as _',
                        'from django.utils.translation import gettext_lazy as _'
                    )
                    
                    # Write back the patched file
                    with open(models_path, 'w') as f:
                        f.write(content)
                    
                    print(f"[✓] Successfully patched django-push-notifications for Django 4.2+ compatibility")
                    return True
                else:
                    print("[✓] django-push-notifications already appears compatible (no patch needed)")
                    return True
        
        print("[✗] Could not find push_notifications module to patch")
        return False
    except Exception as e:
        print(f"[✗] Failed to patch django-push-notifications: {e}")
        return False

def main():
    print("====== Python 3.13 Compatibility Setup ======")
    
    needs_setup = check_python_version()
    if not needs_setup:
        print("\nNo action needed. Your Python version doesn't require the patch.")
        return
    
    has_legacy_cgi = check_legacy_cgi()
    if not has_legacy_cgi:
        success = install_legacy_cgi()
        if not success:
            print("\nFailed to install required packages. Please install manually:")
            print("pip install legacy-cgi>=1.0.0")
            return
    
    patched = test_patch()
    if not patched:
        print("\nWarning: Patch test failed. You may encounter issues with libraries using cgi module.")
        print("Try manually installing: pip install legacy-cgi>=1.0.0")
    
    # Also fix django-push-notifications compatibility with Django 4.2+
    fix_push_notifications()
    
    print("\nSetup complete! The password manager should now work with Python 3.13+.")
    print("\nWould you like to install all project dependencies? (y/n)")
    choice = input().lower()
    if choice in ('y', 'yes'):
        setup_project_dependencies()

if __name__ == "__main__":
    main() 