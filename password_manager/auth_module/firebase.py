import firebase_admin
from firebase_admin import credentials, auth, db
from django.conf import settings
import os
import json

# Initialize Firebase - TEMPORARILY DISABLED FOR MIGRATIONS
firebase_initialized = False

def create_custom_token(user_id):
    """Create a custom Firebase token for a user"""
    if not firebase_initialized:
        return "firebase-disabled-for-migrations"
    try:
        custom_token = auth.create_custom_token(str(user_id))
        return custom_token.decode('utf-8')
    except Exception as e:
        print(f"Error creating Firebase token: {e}")
        return None

def sync_item_to_firebase(user_id, item):
    """Sync an item to Firebase Realtime Database"""
    if not firebase_initialized:
        return True
    try:
        ref = db.reference(f'users/{user_id}/vault/{item.id}')
        ref.set({
            'id': str(item.id),
            'item_id': item.item_id,
            'encrypted_data': item.encrypted_data,
            'item_type': item.item_type,
            'updated_at': item.updated_at.isoformat(),
            'favorite': item.favorite,
            'last_modified': {'.sv': 'timestamp'}  # Server value for timestamp
        })
        return True
    except Exception as e:
        print(f"Error syncing to Firebase: {e}")
        return False

def remove_item_from_firebase(user_id, item_id):
    """Remove an item from Firebase Realtime Database"""
    if not firebase_initialized:
        return True
    try:
        ref = db.reference(f'users/{user_id}/vault/{item_id}')
        ref.delete()
        return True
    except Exception as e:
        print(f"Error removing from Firebase: {e}")
        return False
