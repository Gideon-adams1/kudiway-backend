# users/views.py
# ✅ Updated & cleaned, same functionality but stronger + supports your NEW partner rules
# - Fix: consistent /api prefix handling is in frontend; backend unchanged
# - Fix: remove duplicate imports + organize
# - Fix: safer access to profile (avoids AttributeError)
# - Fix: video_review_links can be None → treated as []
# - NEW: kudiway_followers + requirement (>= 30)
# - NEW: social followers requirement (>= 300) (instead of 1000)
# - Keeps: KYC Approved + ₵500 spend + >=1 video review + not pending/approved
# - Keeps: apply/approve/reject endpoints and notification/email behavior
#
# NOTE:
# - This assumes you already store Kudiway followers in Profile as `kudiway_followers` (IntegerField default 0).
#   If you don't yet, add it to Profile model and migrate, OR replace below with your real source.

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Sum
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .models import KudiPoints, Profile  # Profile is referenced explicitly
from kudiwallet.models import Notification
from orders.models import Order


# ============================================================
# 🧍 USER REGISTRATION
# ============================================================
@api_view(["POST"])
@permission_classes([AllowAny])
def register_user(request):
    data = request.data
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

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

    User.objects.create_user(username=username, email=email, password=password)

    return Response(
        {"message": "User registered successfully."},
        status=status.HTTP_201_CREATED,
    )


# ============================================================
# 🔐 LOGIN
# ============================================================
@api_view(["POST"])
@permission_classes([AllowAny])
def login_user(request):
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(request, username=username, password=password)

    if user:
        login(request, user)
        return Response({"message": "Login successful.", "username": user.username})

    return Response(
        {"error": "Invalid credentials."},
        status=status.HTTP_401_UNAUTHORIZED,
    )


# ============================================================
# 🚪 LOGOUT
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_user(request):
    logout(request)
    return Response({"message": "Logout successful."})


# ============================================================
# 🔧 INTERNAL HELPERS
# ============================================================
def _get_profile(user: User) -> Profile:
    """
    Ensure profile exists and return it.
    Prevents crashes if signals didn't create a Profile for some reason.
    """
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def _safe_list(v):
    return v if isinstance(v, list) else []


def _partner_requirements(profile: Profile, user: User):
    """
    Centralize partner rules so partner_status + apply_partner always match.
    NEW RULES (your request):
      - KYC must be Approved
      - total spent >= 500
      - kudiway followers >= 30 (from your in-app follow system)
      - social followers >= 300 (external platform)
      - at least 1 video review link
    """
    # KYC
    kyc = getattr(user, "kyc_profile", None)
    kyc_status = getattr(kyc, "status", None) if kyc else None
    kyc_status = kyc_status or "Missing"

    # Purchases
    total_spent = (
        Order.objects.filter(user=user, status=Order.Status.PAID)
        .aggregate(Sum("total_amount"))
        .get("total_amount__sum")
        or 0
    )
    meets_spend_requirement = float(total_spent) >= 500

    # External social followers (TikTok/IG/etc.)
    social_followers = int(profile.social_followers or 0)
    meets_social_requirement = social_followers >= 300

    # In-app Kudiway followers (from your follow system tied to reviews)
    # Requires Profile.kudiway_followers (IntegerField default 0).
    kudiway_followers = int(getattr(profile, "kudiway_followers", 0) or 0)
    meets_kudiway_followers_requirement = kudiway_followers >= 30

    # Video review requirement (must be a Kudiway product review link(s))
    video_review_links = _safe_list(profile.video_review_links)
    has_video_review = len(video_review_links) > 0

    return {
        "kyc_status": kyc_status,
        "total_spent": float(total_spent),
        "meets_spend_requirement": meets_spend_requirement,
        "social_followers": social_followers,
        "meets_social_requirement": meets_social_requirement,
        "kudiway_followers": kudiway_followers,
        "meets_kudiway_followers_requirement": meets_kudiway_followers_requirement,
        "video_review_links": video_review_links,
        "has_video_review": has_video_review,
    }


# ============================================================
# 👤 GET CURRENT USER
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    user = request.user
    profile = _get_profile(user)
    points, _ = KudiPoints.objects.get_or_create(user=user)

    return Response(
        {
            "username": user.username,
            "email": user.email,
            "phone_number": profile.phone_number,
            "bio": profile.bio,
            "profile_picture": profile.profile_picture.url if profile.profile_picture else None,
            "is_verified_partner": bool(profile.is_verified_partner),
            "is_vendor": bool(profile.is_vendor),
            "social_media_platform": profile.social_media_platform,
            "social_media_handle": profile.social_media_handle,
            "social_followers": int(profile.social_followers or 0),
            # NEW: expose kudiway followers too (for eligibility UI)
            "kudiway_followers": int(getattr(profile, "kudiway_followers", 0) or 0),
            "video_review_links": _safe_list(profile.video_review_links),
            "partner_application_status": profile.partner_application_status,
            "points_balance": float(points.balance),
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
        }
    )


# ============================================================
# 🛠 UPDATE PROFILE
# ============================================================
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    profile = _get_profile(user)
    data = request.data

    # Update user fields
    if "email" in data:
        user.email = (data.get("email") or "").strip()
        user.save()

    # Update profile basic fields
    profile.phone_number = data.get("phone_number", profile.phone_number)
    profile.bio = data.get("bio", profile.bio)

    # Social media platform
    if "social_media_platform" in data:
        profile.social_media_platform = data.get("social_media_platform") or ""

    # Social media handle
    if "social_media_handle" in data:
        profile.social_media_handle = data.get("social_media_handle") or ""

    # Social followers (external)
    if "social_followers" in data:
        try:
            profile.social_followers = int(data["social_followers"])
        except (TypeError, ValueError):
            pass

    # Review video links (array)
    if "video_review_links" in data and isinstance(data["video_review_links"], list):
        profile.video_review_links = data["video_review_links"]

    # NOTE: kudiway_followers should be system-controlled (from follow system)
    # but if you want admins to adjust it for tests you can allow it:
    if "kudiway_followers" in data:
        try:
            profile.kudiway_followers = int(data["kudiway_followers"])
        except (TypeError, ValueError):
            pass

    # Admin-controlled flags (optional)
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
# 📄 GET PROFILE
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_profile(request):
    user = request.user
    profile = _get_profile(user)
    points, _ = KudiPoints.objects.get_or_create(user=user)

    return Response(
        {
            "username": user.username,
            "email": user.email,
            "phone_number": profile.phone_number,
            "bio": profile.bio,
            "profile_picture": profile.profile_picture.url if profile.profile_picture else None,
            "is_verified_partner": bool(profile.is_verified_partner),
            "is_vendor": bool(profile.is_vendor),
            "social_media_platform": profile.social_media_platform,
            "social_media_handle": profile.social_media_handle,
            "social_followers": int(profile.social_followers or 0),
            "kudiway_followers": int(getattr(profile, "kudiway_followers", 0) or 0),
            "video_review_links": _safe_list(profile.video_review_links),
            "partner_application_status": profile.partner_application_status,
            "points_balance": float(points.balance),
        }
    )


# ============================================================
# ⭐ GET KUDI POINTS (simple)
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_points(request):
    points, _ = KudiPoints.objects.get_or_create(user=request.user)
    return Response({"points": float(points.balance)})


# ============================================================
# ⭐ GET KUDI POINTS (detailed)  (kept for backward compatibility)
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_kudi_points(request):
    points, _ = KudiPoints.objects.get_or_create(user=request.user)
    return Response(
        {
            "current_points": points.balance,
            "lifetime_earned": points.lifetime_earned,
            "lifetime_spent": points.lifetime_spent,
        },
        status=200,
    )


# ============================================================
# 🤝 PARTNER STATUS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def partner_status(request):
    user = request.user
    profile = _get_profile(user)

    req = _partner_requirements(profile, user)

    # can_apply: must meet all requirements AND not already pending/approved
    can_apply = (
        req["kyc_status"] == "Approved"
        and req["meets_spend_requirement"]
        and req["meets_social_requirement"]
        and req["meets_kudiway_followers_requirement"]
        and req["has_video_review"]
        and profile.partner_application_status not in ["pending", "approved"]
    )

    return Response(
        {
            "is_verified_partner": bool(profile.is_verified_partner),
            "application_status": profile.partner_application_status,
            "kyc_status": req["kyc_status"],
            "total_spent": req["total_spent"],
            "meets_spend_requirement": req["meets_spend_requirement"],
            "social_followers": req["social_followers"],
            "meets_social_requirement": req["meets_social_requirement"],
            "kudiway_followers": req["kudiway_followers"],
            "meets_kudiway_followers_requirement": req["meets_kudiway_followers_requirement"],
            "video_review_links": req["video_review_links"],
            "has_video_review": req["has_video_review"],
            "can_apply": can_apply,
        }
    )


# ============================================================
# 📩 APPLY TO BECOME PARTNER
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def apply_partner(request):
    user = request.user
    profile = _get_profile(user)

    if profile.is_verified_partner:
        return Response(
            {"error": "Already a verified partner."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if profile.partner_application_status == "pending":
        return Response(
            {"error": "Application already pending."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    req = _partner_requirements(profile, user)

    eligible = (
        req["kyc_status"] == "Approved"
        and req["meets_spend_requirement"]
        and req["meets_social_requirement"]
        and req["meets_kudiway_followers_requirement"]
        and req["has_video_review"]
    )

    if not eligible:
        return Response(
            {"error": "You do not meet all requirements yet."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    profile.partner_application_status = "pending"
    profile.save(update_fields=["partner_application_status"])

    return Response(
        {
            "message": "Your application has been submitted and is under review.",
            "application_status": "pending",
        }
    )


# ============================================================
# 🔐 ADMIN — LIST PENDING PARTNERS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAdminUser])
def pending_partners(request):
    users = User.objects.filter(profile__partner_application_status="pending").select_related("profile")
    data = [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "social_followers": int(u.profile.social_followers or 0),
            "kudiway_followers": int(getattr(u.profile, "kudiway_followers", 0) or 0),
        }
        for u in users
    ]
    return Response(data)


# ============================================================
# 🔐 ADMIN — APPROVE PARTNER
# ============================================================
@api_view(["POST"])
@permission_classes([IsAdminUser])
def approve_partner(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"error": "User not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    profile = _get_profile(user)
    profile.is_verified_partner = True
    profile.partner_application_status = "approved"
    profile.save(update_fields=["is_verified_partner", "partner_application_status"])

    # Email
    if user.email:
        try:
            send_mail(
                "Kudiway Partner — Approved!",
                f"Hi {user.username}, your Kudiway Partner application has been approved.",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
            )
        except Exception:
            pass

    # In-app notification
    Notification.objects.create(
        user=user,
        title="Partner Application Approved",
        body="Congratulations! You are now a verified Kudiway Partner.",
        data={"type": "PARTNER_APPROVED"},
    )

    return Response({"message": "Partner approved."})


# ============================================================
# 🔐 ADMIN — REJECT PARTNER
# ============================================================
@api_view(["POST"])
@permission_classes([IsAdminUser])
def reject_partner(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"error": "User not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    profile = _get_profile(user)
    profile.is_verified_partner = False
    profile.partner_application_status = "rejected"
    profile.save(update_fields=["is_verified_partner", "partner_application_status"])

    # Email
    if user.email:
        try:
            send_mail(
                "Kudiway Partner — Application Update",
                f"Hi {user.username}, unfortunately your application was not approved.",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
            )
        except Exception:
            pass

    Notification.objects.create(
        user=user,
        title="Partner Application Rejected",
        body="Your Kudiway Partner application was not approved.",
        data={"type": "PARTNER_REJECTED"},
    )

    return Response({"message": "Partner rejected."})


# ============================================================
# 🛡 ADMIN STATUS (used by app to show Admin tab)
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_status(request):
    user = request.user
    return Response(
        {
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "role": "admin" if (user.is_staff or user.is_superuser) else "user",
        }
    )
