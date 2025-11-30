# OAuth Setup Guide for Password Manager

This guide will help you configure Google, GitHub, and Apple OAuth authentication for the Password Manager application.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Google OAuth Setup](#google-oauth-setup)
- [GitHub OAuth Setup](#github-oauth-setup)
- [Apple OAuth Setup](#apple-oauth-setup)
- [Backend Configuration](#backend-configuration)
- [Testing OAuth](#testing-oauth)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before setting up OAuth, ensure you have:
- A Google, GitHub, or Apple developer account
- Access to your backend `.env` file
- Your application's redirect URIs

## Google OAuth Setup

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.developers.google.com/)
2. Click "Create Project" or select an existing project
3. Name your project (e.g., "Password Manager")

### 2. Enable Google+ API

1. In the left sidebar, go to "APIs & Services" → "Library"
2. Search for "Google+ API"
3. Click "Enable"

### 3. Configure OAuth Consent Screen

1. Go to "APIs & Services" → "OAuth consent screen"
2. Select "External" user type (or "Internal" if using Google Workspace)
3. Fill in the required information:
   - App name: Password Manager
   - User support email: your-email@example.com
   - Developer contact: your-email@example.com
4. Add scopes:
   - `.../auth/userinfo.email`
   - `.../auth/userinfo.profile`
5. Add test users (for development)
6. Click "Save and Continue"

### 4. Create OAuth Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Select "Web application"
4. Add authorized JavaScript origins:
   ```
   http://localhost:3000
   http://127.0.0.1:3000
   http://localhost:8000
   http://127.0.0.1:8000
   ```
5. Add authorized redirect URIs:
   ```
   http://localhost:8000/api/auth/oauth/google/
   http://127.0.0.1:8000/api/auth/oauth/google/
   http://localhost:3000/auth/callback
   ```
6. Click "Create"
7. Copy the **Client ID** and **Client Secret**

### 5. Update Environment Variables

Add to your `password_manager/.env` file:
```env
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
```

## GitHub OAuth Setup

### 1. Register a New OAuth App

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click "OAuth Apps" → "New OAuth App"
3. Fill in the application details:
   - **Application name**: Password Manager
   - **Homepage URL**: `http://localhost:3000`
   - **Authorization callback URL**: `http://localhost:8000/api/auth/oauth/github/`
4. Click "Register application"

### 2. Generate Client Secret

1. After registration, click "Generate a new client secret"
2. Copy the **Client ID** and **Client Secret** immediately (secret is only shown once)

### 3. Update Environment Variables

Add to your `password_manager/.env` file:
```env
GITHUB_OAUTH_CLIENT_ID=your-github-client-id
GITHUB_OAUTH_CLIENT_SECRET=your-github-client-secret
```

## Apple OAuth Setup

### 1. Prerequisites

- An Apple Developer Account (requires $99/year membership)
- Access to [Apple Developer Portal](https://developer.apple.com/)

### 2. Register an App ID

1. Go to "Certificates, Identifiers & Profiles" → "Identifiers"
2. Click "+" to create a new identifier
3. Select "App IDs" and click "Continue"
4. Select "App" and click "Continue"
5. Configure your App ID:
   - **Description**: Password Manager
   - **Bundle ID**: `com.yourcompany.passwordmanager`
6. Enable "Sign in with Apple" capability
7. Click "Continue" and then "Register"

### 3. Create a Services ID

1. Go to "Identifiers" → "+" → "Services IDs"
2. Fill in:
   - **Description**: Password Manager Web
   - **Identifier**: `com.yourcompany.passwordmanager.web`
3. Enable "Sign in with Apple"
4. Click "Configure" next to "Sign in with Apple"
5. Add domains and return URLs:
   - **Domains**: `localhost`, `127.0.0.1`
   - **Return URLs**: `http://localhost:8000/api/auth/oauth/apple/`
6. Click "Save" and then "Continue" and "Register"

### 4. Create a Private Key

1. Go to "Keys" → "+" to create a new key
2. Configure the key:
   - **Key Name**: Password Manager Sign In Key
   - Enable "Sign in with Apple"
   - Click "Configure" and select your Primary App ID
3. Click "Continue" and then "Register"
4. Download the key file (.p8)
5. Note the **Key ID**

### 5. Get Team ID

1. Go to your Apple Developer account homepage
2. Your **Team ID** is displayed in the upper right corner

### 6. Update Environment Variables

Add to your `password_manager/.env` file:
```env
APPLE_OAUTH_CLIENT_ID=com.yourcompany.passwordmanager.web
APPLE_OAUTH_KEY_ID=your-key-id
APPLE_OAUTH_TEAM_ID=your-team-id
APPLE_OAUTH_PRIVATE_KEY=/path/to/your/AuthKey_XXXXXXXXXX.p8
```

## Backend Configuration

### 1. Install Required Dependencies

Ensure these packages are in your `requirements.txt`:
```
dj-rest-auth==2.2.5
django-allauth==0.54.0
djangorestframework-simplejwt==5.2.2
```

Install them:
```bash
cd password_manager
pip install -r requirements.txt
```

### 2. Apply Migrations

```bash
python manage.py migrate
```

### 3. Create Django Sites

```bash
python manage.py shell
```

Then run:
```python
from django.contrib.sites.models import Site
site = Site.objects.get_or_create(
    id=1,
    defaults={'domain': 'localhost:3000', 'name': 'Password Manager'}
)
```

### 4. Configure Social Apps

For each provider, you need to create a SocialApp in Django admin:

```bash
python manage.py createsuperuser  # If you haven't created one
python manage.py runserver
```

1. Go to `http://127.0.0.1:8000/admin/`
2. Login with your superuser credentials
3. Navigate to "Social applications" → "Add social application"
4. For each provider (Google, GitHub, Apple):
   - **Provider**: Select the provider
   - **Name**: Provider name (e.g., "Google OAuth")
   - **Client id**: Your OAuth client ID
   - **Secret key**: Your OAuth client secret
   - **Sites**: Select your site
5. Click "Save"

## Testing OAuth

### 1. Start the Backend

```bash
cd password_manager
python manage.py runserver
```

### 2. Start the Frontend

```bash
cd frontend
npm run dev
```

### 3. Test OAuth Login

1. Navigate to `http://localhost:3000`
2. Click on "Continue with Google" (or GitHub/Apple)
3. A popup should open with the OAuth provider's login page
4. Complete the authentication
5. You should be redirected back and logged in

## Troubleshooting

### Common Issues

#### 1. "Popup was blocked"
- **Solution**: Allow popups for your site in browser settings
- Alternative: The OAuth will work in a new tab if popups are blocked

#### 2. "redirect_uri_mismatch" (Google)
- **Solution**: Ensure the redirect URI in Google Console exactly matches:
  ```
  http://localhost:8000/api/auth/oauth/google/
  ```

#### 3. "Application not found" (GitHub)
- **Solution**: Check that your GitHub OAuth app is properly registered and the client ID is correct

#### 4. "Invalid client" (Apple)
- **Solution**: Verify all Apple OAuth configurations:
  - Services ID is correct
  - Private key is properly loaded
  - Team ID and Key ID match

#### 5. CORS Errors
- **Solution**: Ensure `CORS_ALLOWED_ORIGINS` in `settings.py` includes:
  ```python
  CORS_ALLOWED_ORIGINS = [
      "http://localhost:3000",
      "http://127.0.0.1:3000",
  ]
  ```

#### 6. OAuth Provider Not Appearing
- **Check**: Environment variables are set correctly in `.env`
- **Check**: Backend server was restarted after adding env variables
- **Check**: Provider is configured in Django admin

### Debug Mode

Enable debug logging for OAuth:

In `settings.py`:
```python
LOGGING = {
    ...
    'loggers': {
        'allauth': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

## Production Deployment

### Important Changes for Production

1. **Update Redirect URIs**:
   - Replace `localhost` and `127.0.0.1` with your production domain
   - Use HTTPS URLs only

2. **Environment Variables**:
   ```env
   FRONTEND_URL=https://your-domain.com
   BACKEND_URL=https://api.your-domain.com
   ```

3. **Security Settings**:
   - Ensure `DEBUG=False`
   - Set `SECURE_SSL_REDIRECT=True`
   - Update `ALLOWED_HOSTS`
   - Update `CORS_ALLOWED_ORIGINS`

4. **OAuth Consent Screens**:
   - For Google: Submit app for verification
   - For Apple: Update domains to production domains

## Support

For issues or questions:
- Check Django-allauth documentation: https://django-allauth.readthedocs.io/
- Review provider-specific OAuth documentation
- Check application logs for detailed error messages

## Security Best Practices

1. **Never commit OAuth credentials** to version control
2. **Use environment variables** for all sensitive data
3. **Regularly rotate** OAuth client secrets
4. **Monitor OAuth usage** in provider dashboards
5. **Implement rate limiting** for OAuth endpoints
6. **Use HTTPS** in production
7. **Validate state parameters** to prevent CSRF attacks
8. **Store minimal user data** from OAuth providers

