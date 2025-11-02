from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Profile


# 🔹 1. Register new users
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )
        # ✅ Ensure profile & wallet auto-create if signals fail
        from kudiwallet.models import Wallet
        from .models import Profile
        Wallet.objects.get_or_create(user=user)
        Profile.objects.get_or_create(user=user)
        return user


# 🔹 2. Profile serializer (nested under user)
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["profile_picture", "bio", "phone_number"]


# 🔹 3. Update user info + nested profile
class UserUpdateSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "username", "profile"]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        profile, _ = Profile.objects.get_or_create(user=instance)
        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.save()
        return instance
