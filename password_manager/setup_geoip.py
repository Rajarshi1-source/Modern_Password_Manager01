#!/usr/bin/env python3
"""
GeoIP Database Setup Script for Password Manager

This script helps you set up the MaxMind GeoLite2 databases required for
location-based security features in the password manager.

Run this script to:
1. Create the GeoIP directory
2. Download the required database files
3. Verify the setup

Requirements:
- MaxMind account (free) - https://www.maxmind.com/en/geolite2/signup
- MaxMind license key
"""

import os
import sys
import urllib.request
import gzip
import tarfile
import shutil
from pathlib import Path

def get_base_dir():
    """Get the base directory of the Django project."""
    return Path(__file__).resolve().parent

def get_geoip_path():
    """Get the GeoIP path from environment or use default."""
    base_dir = get_base_dir()
    return os.environ.get('GEOIP_PATH', base_dir / 'geoip')

def create_geoip_directory():
    """Create the GeoIP directory if it doesn't exist."""
    geoip_path = get_geoip_path()
    Path(geoip_path).mkdir(parents=True, exist_ok=True)
    print(f"✓ GeoIP directory created/verified: {geoip_path}")
    return geoip_path

def check_databases_exist(geoip_path):
    """Check if the required database files already exist."""
    city_db = Path(geoip_path) / 'GeoLite2-City.mmdb'
    country_db = Path(geoip_path) / 'GeoLite2-Country.mmdb'
    
    city_exists = city_db.exists()
    country_exists = country_db.exists()
    
    if city_exists and country_exists:
        print("✓ Both GeoIP databases already exist!")
        print(f"  - City database: {city_db}")
        print(f"  - Country database: {country_db}")
        return True
    elif city_exists:
        print(f"✓ City database exists: {city_db}")
        print(f"✗ Country database missing: {country_db}")
        return False
    elif country_exists:
        print(f"✗ City database missing: {city_db}")
        print(f"✓ Country database exists: {country_db}")
        return False
    else:
        print("✗ Both GeoIP databases are missing")
        return False

def download_with_license_key():
    """Download databases using MaxMind license key."""
    license_key = input("\nEnter your MaxMind license key: ").strip()
    
    if not license_key:
        print("✗ License key is required!")
        return False
    
    geoip_path = get_geoip_path()
    
    databases = {
        'GeoLite2-City': 'https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key={}&suffix=tar.gz',
        'GeoLite2-Country': 'https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-Country&license_key={}&suffix=tar.gz'
    }
    
    for db_name, url_template in databases.items():
        print(f"\n📥 Downloading {db_name}...")
        
        url = url_template.format(license_key)
        tar_filename = f"{db_name}.tar.gz"
        tar_path = Path(geoip_path) / tar_filename
        
        try:
            # Download the tar.gz file
            urllib.request.urlretrieve(url, tar_path)
            print(f"✓ Downloaded {tar_filename}")
            
            # Extract the .mmdb file
            with tarfile.open(tar_path, 'r:gz') as tar:
                # Find the .mmdb file in the archive
                mmdb_file = None
                for member in tar.getmembers():
                    if member.name.endswith('.mmdb'):
                        mmdb_file = member
                        break
                
                if mmdb_file:
                    # Extract to a temporary location
                    tar.extract(mmdb_file, geoip_path)
                    
                    # Move to the correct location
                    extracted_path = Path(geoip_path) / mmdb_file.name
                    final_path = Path(geoip_path) / f"{db_name}.mmdb"
                    
                    shutil.move(str(extracted_path), str(final_path))
                    print(f"✓ Extracted {db_name}.mmdb")
                else:
                    print(f"✗ Could not find .mmdb file in {tar_filename}")
                    return False
            
            # Clean up the tar file
            tar_path.unlink()
            
            # Clean up any extracted directories
            for item in Path(geoip_path).iterdir():
                if item.is_dir() and item.name.startswith('GeoLite2'):
                    shutil.rmtree(item)
            
        except Exception as e:
            print(f"✗ Error downloading {db_name}: {e}")
            return False
    
    return True

def verify_setup():
    """Verify that the GeoIP setup is working correctly."""
    print("\n🔍 Verifying GeoIP setup...")
    
    try:
        import django
        from django.conf import settings
        
        # Set up Django settings
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.settings')
        django.setup()
        
        from django.contrib.gis.geoip2 import GeoIP2
        
        # Test GeoIP functionality
        g = GeoIP2()
        
        # Test with a known IP address (Google's public DNS)
        test_ip = '8.8.8.8'
        
        try:
            country = g.country(test_ip)
            city = g.city(test_ip)
            
            print(f"✓ GeoIP is working correctly!")
            print(f"  Test IP: {test_ip}")
            print(f"  Country: {country['country_name']} ({country['country_code']})")
            if city.get('city'):
                print(f"  City: {city['city']}")
            
            return True
            
        except Exception as e:
            print(f"✗ GeoIP test failed: {e}")
            return False
            
    except ImportError as e:
        print(f"✗ Django import failed: {e}")
        print("  Make sure you're running this from the Django project directory")
        return False
    except Exception as e:
        print(f"✗ Setup verification failed: {e}")
        return False

def print_manual_instructions():
    """Print manual setup instructions."""
    geoip_path = get_geoip_path()
    
    print(f"""
📋 Manual Setup Instructions:

1. Register for a free MaxMind account:
   https://www.maxmind.com/en/geolite2/signup

2. Generate a license key in your MaxMind account:
   https://www.maxmind.com/en/accounts/current/license-key

3. Download the following databases:
   - GeoLite2-City (mmdb format)
   - GeoLite2-Country (mmdb format)

4. Extract and place the .mmdb files in:
   {geoip_path}

   The files should be named:
   - GeoLite2-City.mmdb
   - GeoLite2-Country.mmdb

5. Restart your Django development server

Alternative: Set the GEOIP_PATH environment variable to use a different directory.
""")

def main():
    """Main setup function."""
    print("🌍 MaxMind GeoIP Database Setup")
    print("=" * 40)
    
    # Create GeoIP directory
    geoip_path = create_geoip_directory()
    
    # Check if databases already exist
    if check_databases_exist(geoip_path):
        choice = input("\nDatabases already exist. Do you want to verify the setup? (y/n): ").strip().lower()
        if choice == 'y':
            verify_setup()
        return
    
    print("\n📋 Setup Options:")
    print("1. Automatic download (requires MaxMind license key)")
    print("2. Show manual setup instructions")
    print("3. Verify existing setup")
    print("4. Exit")
    
    choice = input("\nSelect an option (1-4): ").strip()
    
    if choice == '1':
        if download_with_license_key():
            print("\n✅ Download completed!")
            verify_setup()
        else:
            print("\n❌ Download failed. Please try manual setup.")
            print_manual_instructions()
    
    elif choice == '2':
        print_manual_instructions()
    
    elif choice == '3':
        verify_setup()
    
    elif choice == '4':
        print("👋 Goodbye!")
        return
    
    else:
        print("❌ Invalid choice!")
        return

if __name__ == '__main__':
    main() 