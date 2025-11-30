#!/usr/bin/env python
"""
Script to install the correct WebAuthn dependencies for Python 3.13
"""
import subprocess
import sys
import os

def install_dependencies():
    print("Installing correct WebAuthn and FIDO2 dependencies for the password manager...")
    
    # List of packages to install
    packages = [
        "fido2==1.1.0",         # Specific version that works with our code
        "cryptography>=40.0.0",  # Required for FIDO2 operations
        "pyOpenSSL>=23.0.0",     # Required for WebAuthn operations
        "cbor2>=5.4.6",          # Required for CTAP message format
        "legacy-cgi>=2.0.0"      # Required for Python 3.13 compatibility
    ]
    
    try:
        # Install each package
        for package in packages:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        
        print("\nSuccessfully installed all dependencies!")
        print("You can now run `python manage.py makemigrations` and `python manage.py migrate`")
        
    except subprocess.CalledProcessError as e:
        print(f"Error installing packages: {e}")
        return False
    
    return True

if __name__ == "__main__":
    install_dependencies() 