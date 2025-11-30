# GeoIP Database Setup Guide

This guide will help you set up MaxMind's GeoLite2 databases for location-based security features in the password manager.

## 🌍 Why GeoIP?

The password manager uses GeoIP databases to:
- Detect unusual login locations
- Calculate threat scores based on geographic patterns
- Provide enhanced security monitoring
- Generate location-based security alerts

## 📋 Prerequisites

- Python 3.8+ with Django
- MaxMind account (free)
- Internet connection for downloading databases

## 🚀 Quick Setup

### Option 1: Automated Setup (Recommended)

1. **Run the setup script:**
   ```bash
   cd password_manager
   python setup_geoip.py
   ```

2. **Follow the prompts:**
   - Choose option 1 for automatic download
   - Enter your MaxMind license key when prompted
   - The script will download and configure everything

### Option 2: Manual Setup

1. **Create MaxMind Account:**
   - Go to https://www.maxmind.com/en/geolite2/signup
   - Register for a free account
   - Verify your email address

2. **Generate License Key:**
   - Log into your MaxMind account
   - Go to https://www.maxmind.com/en/accounts/current/license-key
   - Click "Generate new license key"
   - Save the license key securely

3. **Download Databases:**
   - Download GeoLite2-City (MMDB format)
   - Download GeoLite2-Country (MMDB format)
   - Extract the .mmdb files

4. **Place Database Files:**
   ```bash
   # Create GeoIP directory
   mkdir -p password_manager/geoip
   
   # Move the database files
   mv GeoLite2-City.mmdb password_manager/geoip/
   mv GeoLite2-Country.mmdb password_manager/geoip/
   ```

## ⚙️ Configuration

### Django Settings

The GeoIP configuration is automatically set in `settings.py`:

```python
# GeoIP Database Configuration
GEOIP_PATH = os.environ.get('GEOIP_PATH', os.path.join(BASE_DIR, 'geoip'))
GEOIP_CITY = 'GeoLite2-City.mmdb'
GEOIP_COUNTRY = 'GeoLite2-Country.mmdb'
```

### Environment Variables

You can customize the GeoIP database location:

```bash
# Set custom GeoIP path
export GEOIP_PATH="/path/to/your/geoip/databases"
```

### Directory Structure

After setup, your directory should look like:

```
password_manager/
├── geoip/
│   ├── GeoLite2-City.mmdb
│   └── GeoLite2-Country.mmdb
├── setup_geoip.py
└── ...
```

## 🔍 Verification

### Test GeoIP Functionality

1. **Using the setup script:**
   ```bash
   python setup_geoip.py
   # Choose option 3: "Verify existing setup"
   ```

2. **Manual testing:**
   ```python
   # In Django shell
   python manage.py shell
   
   from django.contrib.gis.geoip2 import GeoIP2
   g = GeoIP2()
   
   # Test with a known IP
   country = g.country('8.8.8.8')
   city = g.city('8.8.8.8')
   
   print(f"Country: {country['country_name']}")
   print(f"City: {city.get('city', 'Unknown')}")
   ```

### Expected Output

If everything is working correctly, you should see:
```
✓ GeoIP is working correctly!
  Test IP: 8.8.8.8
  Country: United States (US)
  City: Mountain View
```

## 🔧 Usage in Account Protection

The Account Protection system uses GeoIP in several ways:

### Location Detection
```python
from password_manager.security.services.account_protection import AccountProtectionService

service = AccountProtectionService()
location = service.get_location_from_ip('8.8.8.8')
print(location)  # {'country': 'US', 'city': 'Mountain View', ...}
```

### Threat Scoring
- Logins from unusual countries increase threat score
- Distance from user's typical locations affects risk assessment
- New locations trigger security alerts

### Security Alerts
- "Unusual location" alerts for foreign countries
- "Location anomaly" detection for significant distance changes
- Geo-fencing capabilities for high-security accounts

## 🛠️ Troubleshooting

### Common Issues

1. **"GeoIP database not found" Error:**
   ```bash
   # Check if files exist
   ls -la password_manager/geoip/
   
   # Verify permissions
   chmod 644 password_manager/geoip/*.mmdb
   ```

2. **"Invalid license key" Error:**
   - Verify your license key is correct
   - Check that your MaxMind account is active
   - Ensure you're using the correct API format

3. **"Database corrupted" Error:**
   - Re-download the database files
   - Verify the download completed successfully
   - Check disk space and permissions

### Database Updates

MaxMind updates their databases regularly. Set up automatic updates:

```bash
# Add to crontab for monthly updates
0 0 1 * * /path/to/password_manager/setup_geoip.py --auto-update
```

## 📊 Performance Considerations

### Database Size
- GeoLite2-City: ~70MB
- GeoLite2-Country: ~6MB
- Memory usage: ~100-200MB when loaded

### Optimization Tips
1. **Caching:** Django caches GeoIP lookups automatically
2. **Memory:** Databases are loaded into memory for fast access
3. **Updates:** Schedule updates during low-traffic periods

## 🔒 Security & Privacy

### Data Handling
- IP addresses are not stored permanently
- Only location metadata is retained
- Complies with GDPR and privacy regulations

### Accuracy Limitations
- City-level accuracy: ~75-85%
- Country-level accuracy: ~95-99%
- VPN/Proxy detection: Limited
- Mobile networks: May show carrier location

## 📚 Additional Resources

- [MaxMind GeoLite2 Documentation](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data)
- [Django GeoIP2 Documentation](https://docs.djangoproject.com/en/stable/ref/contrib/gis/geoip2/)
- [Account Protection Service Documentation](../security/services/account_protection.py)

## 🆘 Support

If you encounter issues:

1. Check the Django logs: `tail -f logs/debug.log`
2. Run the verification script: `python setup_geoip.py`
3. Review the MaxMind license key setup
4. Ensure all dependencies are installed: `pip install -r requirements.txt`

For production deployments, consider upgrading to MaxMind's paid GeoIP2 databases for improved accuracy and additional features. 