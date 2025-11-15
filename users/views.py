from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db.models import Sum
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import (
    IsAuthenticated,
    AllowAny,
    IsAdminUser,
)
from rest_framework.response import Response

from .models import Profile, KudiPoints
from orders.models import Order


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
        return Response(
            {"error": "Username and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(username=username).exists():
        return Response(
            {"error": "Username already exists."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.create_user(
        username=username, email=email, password=password
    )
    # Profile & KudiPoints are created via signals

    return Response(
        {"message": "User registered successfully."},
        status=status.HTTP_201_CREATED,
    )


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
        return Response(
            {"message": "Login successful.", "username": user.username}
        )
    return Response(
        {"error": "Invalid credentials."},
        status=status.HTTP_401_UNAUTHORIZED,
    )


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
            profile.profile_picture.url
            if getattr(profile, "profile_picture", None)
            else None
        ),
        "is_verified_partner": getattr(profile, "is_verified_partner", False),
        "is_vendor": getattr(profile, "is_vendor", False),
        "social_followers": getattr(profile, "social_followers", 0),
        "video_review_links": getattr(profile, "video_review_links", []),
        "partner_application_status": getattr(
            profile, "partner_application_status", "none"
        ),
        "points_balance": float(points.balance),
    }

    return Response(data, status=status.HTTP_200_OK)


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

    # Client MAY update social followers & video links
    if "social_followers" in data:
        try:
            profile.social_followers = int(data["social_followers"])
        except (TypeError, ValueError):
            pass

    if "video_review_links" in data and isinstance(
        data["video_review_links"], list
    ):
        profile.video_review_links = data["video_review_links"]

    # Handle verification flags (normally admin controlled)
    if "is_verified_partner" in data:
        profile.is_verified_partner = bool(data["is_verified_partner"])
    if "is_vendor" in data:
        profile.is_vendor = bool(data["is_vendor"])

    profile.save()

    return Response(
        {"message": "Profile updated successfully."},
        status=status.HTTP_200_OK,
    )


# ============================================================
# 🧾 GET PROFILE DETAILS
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

    return Response(
        {
            "username": user.username,
            "email": user.email,
            "phone_number": getattr(profile, "phone_number", ""),
            "bio": getattr(profile, "bio", ""),
            "profile_picture": (
                profile.profile_picture.url
                if getattr(profile, "profile_picture", None)
                else None
            ),
            "is_verified_partner": getattr(
                profile, "is_verified_partner", False
            ),
            "is_vendor": getattr(profile, "is_vendor", False),
            "social_followers": getattr(profile, "social_followers", 0),
            "video_review_links": getattr(profile, "video_review_links", []),
            "partner_application_status": getattr(
                profile, "partner_application_status", "none"
            ),
            "points_balance": float(points.balance),
        },
        status=status.HTTP_200_OK,
    )


# ============================================================
# 🏆 GET USER POINTS BALANCE (simple)
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_points(request):
    """
    Return only the user's KudiPoints balance.
    """
    points, _ = KudiPoints.objects.get_or_create(user=request.user)
    return Response({"points": float(points.balance)}, status=status.HTTP_200_OK)


# ============================================================
# 💎 GET KUDI POINTS BALANCE (with cedi value)
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_kudi_points(request):
    """
    Return the current user's KudiPoints balance.
    """
    user = request.user
    points, _ = KudiPoints.objects.get_or_create(user=user)

    return Response(
        {
            "username": user.username,
            "points_balance": float(points.balance),
            "points_value_cedis": round(float(points.balance) / 10, 2),  # 10 pts = ₵1
            "last_updated": points.updated_at,
        },
        status=status.HTTP_200_OK,
    )


# ============================================================
# 🤝 PARTNER STATUS ENDPOINT
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def partner_status(request):
    """
    Return full partner eligibility + application status.
    """
    user = request.user
    profile = user.profile

    # 1️⃣ KYC requirement
    kyc = getattr(user, "kyc_profile", None)
    kyc_status = kyc.status if kyc else "Missing"

    # 2️⃣ Total purchases requirement (PAID orders only)
    total_spent = (
        Order.objects.filter(user=user, status=Order.Status.PAID)
        .aggregate(Sum("total_amount"))["total_amount__sum"]
        or 0
    )
    meets_spend_requirement = float(total_spent) >= 500

    # 3️⃣ Social followers requirement
    social_followers = getattr(profile, "social_followers", 0)
    meets_social_requirement = social_followers >= 1000

    # 4️⃣ Video review requirement
    video_links = getattr(profile, "video_review_links", []) or []
    has_video_review = len(video_links) > 0

    # 5️⃣ Can apply?
    can_apply = (
        kyc_status == "Approved"
        and meets_spend_requirement
        and meets_social_requirement
        and has_video_review
        and not profile.is_verified_partner
        and profile.partner_application_status not in ["pending", "approved"]
    )

    return Response(
        {
            "is_verified_partner": profile.is_verified_partner,
            "application_status": profile.partner_application_status,
            "kyc_status": kyc_status,
            "total_spent": float(total_spent),
            "meets_spend_requirement": meets_spend_requirement,
            "social_followers": social_followers,
            "meets_social_requirement": meets_social_requirement,
            "video_review_links": video_links,
            "has_video_review": has_video_review,
            "can_apply": can_apply,
        },
        status=status.HTTP_200_OK,
    )


# ============================================================
# 📩 APPLY TO BECOME PARTNER
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def apply_partner(request):
    """
    User submits application to become a verified partner.
    We re-check eligibility and then mark application as pending.
    """
    user = request.user
    profile = user.profile

    if profile.is_verified_partner:
        return Response(
            {"error": "You are already a verified partner."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if profile.partner_application_status == "pending":
        return Response(
            {"error": "You already have an application under review."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Use same logic as partner_status
    kyc = getattr(user, "kyc_profile", None)
    kyc_status = kyc.status if kyc else "Missing"

    total_spent = (
        Order.objects.filter(user=user, status=Order.Status.PAID)
        .aggregate(Sum("total_amount"))["total_amount__sum"]
        or 0
    )
    meets_spend_requirement = float(total_spent) >= 500

    social_followers = getattr(profile, "social_followers", 0)
    meets_social_requirement = social_followers >= 1000

    video_links = getattr(profile, "video_review_links", []) or []
    has_video_review = len(video_links) > 0

    can_apply = (
        kyc_status == "Approved"
        and meets_spend_requirement
        and meets_social_requirement
        and has_video_review
    )

    if not can_apply:
        return Response(
            {
                "error": "You do not meet all requirements yet.",
                "kyc_status": kyc_status,
                "total_spent": float(total_spent),
                "social_followers": social_followers,
                "video_review_links": video_links,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    profile.partner_application_status = "pending"
    profile.save(update_fields=["partner_application_status"])

    return Response(
        {
            "message": "Your application has been submitted and will be reviewed by the Kudiway team.",
            "application_status": profile.partner_application_status,
        },
        status=status.HTTP_200_OK,
    )


# ============================================================
# ✅ ADMIN: APPROVE PARTNER
# ============================================================
@api_view(["POST"])
@permission_classes([IsAdminUser])
def approve_partner(request, user_id):
    """
    Admin endpoint to approve a user as a verified partner.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"error": "User not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    profile = user.profile
    profile.is_verified_partner = True
    profile.partner_application_status = "approved"
    profile.save(update_fields=["is_verified_partner", "partner_application_status"])

    return Response(
        {
            "message": f"{user.username} has been approved as a Kudiway Partner.",
            "user_id": user.id,
        },
        status=status.HTTP_200_OK,
    )
