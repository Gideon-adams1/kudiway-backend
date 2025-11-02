from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import Profile, KudiPoints  # ✅ include KudiPoints


# ============================================================
# 🧍 USER REGISTRATION
# ============================================================
@api_view(["POST"])
@permission_classes([AllowAny])
def register_user(request):
    """
    Register a new user account.
    """
    data = request.data
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not username or not password:
        return Response({"error": "Username and password are required."}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists."}, status=400)

    user = User.objects.create_user(username=username, email=email, password=password)
    Profile.objects.get_or_create(user=user)
    KudiPoints.objects.get_or_create(user=user)  # ✅ create points wallet

    return Response({"message": "User registered successfully."}, status=201)


# ============================================================
# 🔐 USER LOGIN
# ============================================================
@api_view(["POST"])
@permission_classes([AllowAny])
def login_user(request):
    """
    Log in a user and return a success response.
    """
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(request, username=username, password=password)

    if user is not None:
        login(request, user)
        return Response({"message": "Login successful.", "username": user.username})
    return Response({"error": "Invalid credentials."}, status=401)


# ============================================================
# 🚪 USER LOGOUT
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_user(request):
    """
    Log out the current user.
    """
    logout(request)
    return Response({"message": "Logout successful."})


# ============================================================
# 👤 GET CURRENT USER
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """
    Get info for the currently authenticated user.
    """
    user = request.user
    profile = getattr(user, "profile", None)
    points, _ = KudiPoints.objects.get_or_create(user=user)

    data = {
        "username": user.username,
        "email": user.email,
        "phone_number": getattr(profile, "phone_number", ""),
        "bio": getattr(profile, "bio", ""),
        "profile_picture": (
            profile.profile_picture.url if getattr(profile, "profile_picture", None) else None
        ),
        "is_verified_partner": getattr(profile, "is_verified_partner", False),
        "is_vendor": getattr(profile, "is_vendor", False),
        "points_balance": float(points.balance),  # ✅ include points in profile
    }

    return Response(data, status=200)


# ============================================================
# 🛠️ UPDATE PROFILE
# ============================================================
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """
    Update user's profile information.
    """
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)
    data = request.data

    user.email = data.get("email", user.email)
    user.save()

    profile.phone_number = data.get("phone_number", profile.phone_number)
    profile.bio = data.get("bio", profile.bio)

    # Handle verification fields (admin controlled)
    if "is_verified_partner" in data:
        profile.is_verified_partner = bool(data["is_verified_partner"])
    if "is_vendor" in data:
        profile.is_vendor = bool(data["is_vendor"])

    profile.save()

    return Response({"message": "Profile updated successfully."}, status=200)


# ============================================================
# 🧾 GET PROFILE DETAILS (Verified Partner / Vendor)
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_profile(request):
    """
    Return the current user's profile details.
    """
    user = request.user
    profile = getattr(user, "profile", None)
    points, _ = KudiPoints.objects.get_or_create(user=user)

    return Response({
        "username": user.username,
        "email": user.email,
        "phone_number": getattr(profile, "phone_number", ""),
        "bio": getattr(profile, "bio", ""),
        "profile_picture": (
            profile.profile_picture.url if getattr(profile, "profile_picture", None) else None
        ),
        "is_verified_partner": getattr(profile, "is_verified_partner", False),
        "is_vendor": getattr(profile, "is_vendor", False),
        "points_balance": float(points.balance),
    }, status=200)


# ============================================================
# 🏆 GET USER POINTS BALANCE
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_points(request):
    """
    Return only the user's KudiPoints balance.
    """
    points, _ = KudiPoints.objects.get_or_create(user=request.user)
    return Response({"points": float(points.balance)}, status=200)
# ============================================================
# 💎 GET KUDI POINTS BALANCE
# ============================================================
from users.models import KudiPoints

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_kudi_points(request):
    """
    Return the current user's KudiPoints balance.
    """
    user = request.user
    points, _ = KudiPoints.objects.get_or_create(user=user)

    return Response({
        "username": user.username,
        "points_balance": float(points.balance),
        "points_value_cedis": round(points.balance / 10, 2),  # 10 pts = ₵1
        "last_updated": points.updated_at,
    }, status=200)

