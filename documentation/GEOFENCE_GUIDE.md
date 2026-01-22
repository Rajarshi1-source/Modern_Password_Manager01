# Geofencing & Impossible Travel Detection Guide

> **Physics-based Security**: Uses the laws of physics to detect impossible login patterns

## Overview

Geofencing with Impossible Travel Detection adds a physics-based layer of security to your Password Manager. It detects:

- **Impossible Travel**: Logins from locations that would require traveling faster than physically possible
- **Cloned Sessions**: Two active sessions in different locations at the same time
- **Trusted Zones**: Define locations where additional verification isn't needed

## How It Works

### Physics-Based Detection

The system calculates distance using the **Haversine formula** (great-circle distance) and determines if travel between two login locations is physically possible:

| Travel Mode | Max Speed | Example |
|------------|-----------|---------|
| Walking | 6 km/h | ~5 km in 1 hour |
| Driving | 200 km/h | ~200 km in 1 hour |
| High-Speed Rail | 400 km/h | ~400 km in 1 hour |
| Commercial Flight | 920 km/h | ~920 km in 1 hour |
| **IMPOSSIBLE** | >1200 km/h | Supersonic speed |

### What Happens When Detected

1. **Normal Travel** (walking/driving): Login proceeds normally
2. **Flight Speed**: Requires MFA verification OR matching travel itinerary
3. **Impossible Speed**: Login is **blocked** and marked for investigation

## Features

### 🛡️ Trusted Zones

Define locations where you regularly log in:
- **Home** - Skip MFA when logging in from home
- **Office** - Your workplace location
- **Custom zones** - Any frequently visited location

Each zone has:
- Center coordinates (latitude/longitude)
- Radius (50m - 10km)
- Trust settings (skip MFA, require MFA outside)

### ✈️ Travel Itineraries

Pre-register your travel to prevent false alerts:
1. Add departure and arrival cities
2. Enter flight details (optional)
3. **Verify via Amadeus/Sabre API** with your booking reference

### 🔄 Location Recording

The app captures your location (with permission) during login to:
- Build location history
- Detect travel patterns
- Identify impossible travel immediately

## Setup

### 1. Enable Location Access

When prompted, allow location access in your browser for enhanced security.

### 2. Create Trusted Zones

Navigate to **Security > Geofencing > Trusted Zones**:
1. Click "Add Zone"
2. Enter a name (Home, Office, etc.)
3. Use "Current Location" or enter coordinates manually
4. Set the radius (default: 500m)
5. Save

### 3. Pre-Register Travel (Optional)

Before traveling, add your itinerary:
1. Go to **Security > Geofencing > Travel Plans**
2. Click "Add Trip"
3. Enter departure/arrival cities and times
4. Add booking reference for automatic verification

## Administrator Setup (Backend)

### Environment Variables

Add to your `.env` file:

```bash
# Feature Flags
GEOFENCE_ENABLED=True
IMPOSSIBLE_TRAVEL_ENABLED=True

# Amadeus API (Optional - for flight verification)
AMADEUS_API_KEY=your_key
AMADEUS_API_SECRET=your_secret
AMADEUS_ENVIRONMENT=test  # or production

# Speed Thresholds (optional overrides)
TRAVEL_SPEED_FLIGHT=920
TRAVEL_SPEED_SUPERSONIC=1200
```

### Amadeus API Setup

1. Register at [developers.amadeus.com](https://developers.amadeus.com/)
2. Create a new project
3. Get your API key and secret
4. Add credentials to environment

> **Note**: Amadeus integration is optional. Without it, travel verification is manual.

## Security Considerations

### Privacy

- Location data is encrypted at rest
- Automatically deleted after 90 days
- User consent required for GPS access
- Compliant with GDPR (right to delete data)

### Timestamp Security

- All timestamps are NTP-verified (server-side)
- Client timestamps are not trusted
- Prevents clock manipulation attacks

## Troubleshooting

### "Location access denied"

- Check browser permissions
- Allow location access for the site
- GPS fallback to IP geolocation (less accurate)

### "Impossible travel detected" during legitimate travel

1. Check for pre-registered itinerary
2. Verify your booking with PNR
3. Confirm as "legitimate" if it was you

### False positives with VPN

- VPN IP locations may trigger false alerts
- Add your VPN exit locations as trusted zones
- Or disable VPN during login

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/security/geofence/zones/` | GET/POST | List/create trusted zones |
| `/api/security/geofence/zones/<id>/` | PUT/DELETE | Update/delete zones |
| `/api/security/geofence/location/record/` | POST | Record GPS location |
| `/api/security/geofence/travel/events/` | GET | List travel alerts |
| `/api/security/geofence/travel/verify/` | POST | Verify booking |
| `/api/security/geofence/itinerary/` | GET/POST | Manage itineraries |

## Related Documentation

- [Security Dashboard](.SECURITY_GUIDE.md)
- [Two-Factor Authentication](./MFA_GUIDE.md)
- [Device Management](./DEVICE_GUIDE.md)
