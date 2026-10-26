from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import transaction

from .login_verifier import (
    LEGACY_PASSWORD_FIELD,
    VERIFIER_SCHEME,
    is_login_verifier,
    migrate_legacy_login,
    mark_login_verifier,
)

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    
    # 'lv1' when ``password`` is a login verifier derived in the browser
    # (see auth_module/login_verifier.py) rather than the master password.
    login_verifier = serializers.ChoiceField(choices=[VERIFIER_SCHEME], required=False, write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'login_verifier']

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        if data.get('login_verifier') and not is_login_verifier(data['password']):
            raise serializers.ValidationError("password is not a login verifier")
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        verifier_scheme = validated_data.pop('login_verifier', None)
        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data['username'],
                email=validated_data.get('email', ''),
                password=validated_data['password']
            )
            if verifier_scheme:
                mark_login_verifier(user)
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, style={'input_type': 'password'}, write_only=True)
    
    def validate(self, data):
        migrate_legacy_login(
            data['username'], data['password'], self.initial_data.get(LEGACY_PASSWORD_FIELD),
        )
        user = authenticate(username=data['username'], password=data['password'])
        if user and user.is_active:
            data['user'] = user
            return data
        raise serializers.ValidationError("Invalid credentials")

class MasterPasswordSerializer(serializers.Serializer):
    auth_hash = serializers.CharField(required=True)
