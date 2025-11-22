from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db.models import Sum
from django.conf import settings
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response

from .models import Profile, KudiPoints
from orders.models import Order
from kudiwallet.models import Notification


# ============================================================
# 🧍 USER REGISTRATION
# ============================================================
@api_view(["POST"])
@permission_classes([AllowAny])
def register_user(request):
    data = request.data
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not username or not password:
        return Response({"error": "Username and password are required."},
                        status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists."},
                        status=status.HTTP_400_BAD_REQUEST)

    User.objects.create_user(username=username, email=email, password=password)

    return Response({"message": "User registered successfully."},
                    status=status.HTTP_201_CREATED)


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

    return Response({"error": "Invalid credentials."},
                    status=status.HTTP_401_UNAUTHORIZED)


# ============================================================
# 🚪 LOGOUT
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_user(request):
    logout(request)
    return Response({"message": "Logout successful."})


# ============================================================
# 👤 GET CURRENT USER
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    user = request.user
    profile = user.profile
    points, _ = KudiPoints.objects.get_or_create(user=user)

    return Response({
        "username": user.username,
        "email": user.email,
        "phone_number": profile.phone_number,
        "bio": profile.bio,
        "profile_picture": profile.profile_picture.url if profile.profile_picture else None,
        "is_verified_partner": profile.is_verified_partner,
        "is_vendor": profile.is_vendor,
        "social_media_platform": profile.social_media_platform,
        "social_media_handle": profile.social_media_handle,
        "social_followers": profile.social_followers,
        "video_review_links": profile.video_review_links,
        "partner_application_status": profile.partner_application_status,
        "points_balance": float(points.balance),
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    })


# ============================================================
# 🛠 UPDATE PROFILE
# ============================================================
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    profile = user.profile
    data = request.data

    # Update user fields
    if "email" in data:
        user.email = data["email"]
        user.save()

    # Update profile basic fields
    profile.phone_number = data.get("phone_number", profile.phone_number)
    profile.bio = data.get("bio", profile.bio)

    # NEW — Social media platform
    if "social_media_platform" in data:
        profile.social_media_platform = data.get("social_media_platform") or ""

    # NEW — Social media handle
    if "social_media_handle" in data:
        profile.social_media_handle = data.get("social_media_handle") or ""

    # NEW — Social followers
    if "social_followers" in data:
        try:
            profile.social_followers = int(data["social_followers"])
        except (TypeError, ValueError):
            pass

    # NEW — Review video links (array)
    if "video_review_links" in data and isinstance(data["video_review_links"], list):
        profile.video_review_links = data["video_review_links"]

    # Admin-controlled flags (optional)
    if "is_verified_partner" in data:
        profile.is_verified_partner = bool(data["is_verified_partner"])

    if "is_vendor" in data:
        profile.is_vendor = bool(data["is_vendor"])

    profile.save()

    return Response({"message": "Profile updated successfully."},
                    status=status.HTTP_200_OK)


# ============================================================
# 📄 GET PROFILE
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_profile(request):
    user = request.user
    profile = user.profile
    points, _ = KudiPoints.objects.get_or_create(user=user)

    return Response({
        "username": user.username,
        "email": user.email,
        "phone_number": profile.phone_number,
        "bio": profile.bio,
        "profile_picture": profile.profile_picture.url if profile.profile_picture else None,
        "is_verified_partner": profile.is_verified_partner,
        "is_vendor": profile.is_vendor,
        "social_media_platform": profile.social_media_platform,
        "social_media_handle": profile.social_media_handle,
        "social_followers": profile.social_followers,
        "video_review_links": profile.video_review_links,
        "partner_application_status": profile.partner_application_status,
        "points_balance": float(points.balance),
    })


# ============================================================
# ⭐ GET KUDI POINTS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_points(request):
    points, _ = KudiPoints.objects.get_or_create(user=request.user)
    return Response({"points": float(points.balance)})


# ============================================================
# 🤝 PARTNER STATUS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def partner_status(request):
    user = request.user
    profile = user.profile

    # KYC
    kyc = getattr(user, "kyc_profile", None)
    kyc_status = kyc.status if kyc else "Missing"

    # Purchases
    total_spent = (
        Order.objects.filter(user=user, status=Order.Status.PAID)
        .aggregate(Sum("total_amount"))["total_amount__sum"] or 0
    )
    meets_spend_requirement = total_spent >= 500

    # Social followers
    meets_social_requirement = profile.social_followers >= 1000

    # Video review
    has_video_review = len(profile.video_review_links) > 0

    can_apply = (
        kyc_status == "Approved"
        and meets_spend_requirement
        and meets_social_requirement
        and has_video_review
        and profile.partner_application_status not in ["pending", "approved"]
    )

    return Response({
        "is_verified_partner": profile.is_verified_partner,
        "application_status": profile.partner_application_status,
        "kyc_status": kyc_status,
        "total_spent": float(total_spent),
        "meets_spend_requirement": meets_spend_requirement,
        "social_followers": profile.social_followers,
        "meets_social_requirement": meets_social_requirement,
        "video_review_links": profile.video_review_links,
        "has_video_review": has_video_review,
        "can_apply": can_apply,
    })


# ============================================================
# 📩 APPLY TO BECOME PARTNER
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def apply_partner(request):
    user = request.user
    profile = user.profile

    if profile.is_verified_partner:
        return Response({"error": "Already a verified partner."},
                        status=status.HTTP_400_BAD_REQUEST)

    if profile.partner_application_status == "pending":
        return Response({"error": "Application already pending."},
                        status=status.HTTP_400_BAD_REQUEST)

    # Eligibility checks
    kyc = getattr(user, "kyc_profile", None)
    kyc_status = kyc.status if kyc else "Missing"

    total_spent = (
        Order.objects.filter(user=user, status=Order.Status.PAID)
        .aggregate(Sum("total_amount"))["total_amount__sum"] or 0
    )

    meets_spend_requirement = total_spent >= 500
    meets_social_requirement = profile.social_followers >= 1000
    has_video_review = len(profile.video_review_links) > 0

    if not (kyc_status == "Approved"
            and meets_spend_requirement
            and meets_social_requirement
            and has_video_review):
        return Response(
            {"error": "You do not meet all requirements yet."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Set pending
    profile.partner_application_status = "pending"
    profile.save()

    return Response({
        "message": "Your application has been submitted and is under review.",
        "application_status": "pending",
    })


# ============================================================
# 🔐 ADMIN — LIST PENDING PARTNERS
# ============================================================
@api_view(["GET"])
@permission_classes([IsAdminUser])
def pending_partners(request):
    users = User.objects.filter(profile__partner_application_status="pending")
    data = [{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "followers": u.profile.social_followers,
    } for u in users]

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
        return Response({"error": "User not found."},
                        status=status.HTTP_404_NOT_FOUND)

    profile = user.profile
    profile.is_verified_partner = True
    profile.partner_application_status = "approved"
    profile.save()

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
        except:
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
        return Response({"error": "User not found."},
                        status=status.HTTP_404_NOT_FOUND)

    profile = user.profile
    profile.is_verified_partner = False
    profile.partner_application_status = "rejected"
    profile.save()

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
        except:
            pass

    Notification.objects.create(
        user=user,
        title="Partner Application Rejected",
        body="Your Kudiway Partner application was not approved.",
        data={"type": "PARTNER_REJECTED"},
    )

    return Response({"message": "Partner rejected."})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_kudi_points(request):
    user = request.user

    # Import your model here to avoid circular imports
    from .models import KudiPoints

    points, created = KudiPoints.objects.get_or_create(user=user)

    return Response({
        "current_points": points.balance,
        "lifetime_earned": points.lifetime_earned,
        "lifetime_spent": points.lifetime_spent,
    }, status=200)
