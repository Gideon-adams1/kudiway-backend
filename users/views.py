from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import Profile, KudiPoints
from orders.models import Order   # ✅ needed for spend requirement
from .models import PartnerApplication
from django.db import models


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
        return Response({"error": "Username and password are required."}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists."}, status=400)

    user = User.objects.create_user(username=username, email=email, password=password)
    Profile.objects.get_or_create(user=user)
    KudiPoints.objects.get_or_create(user=user)

    return Response({"message": "User registered successfully."}, status=201)


# ============================================================
# 🔐 USER LOGIN
# ============================================================
@api_view(["POST"])
@permission_classes([AllowAny])
def login_user(request):
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

    data = {
        "username": user.username,
        "email": user.email,
        "phone_number": profile.phone_number,
        "bio": profile.bio,
        "profile_picture": profile.profile_picture.url if profile.profile_picture else None,
        "is_verified_partner": profile.is_verified_partner,
        "partner_application_status": profile.partner_application_status,
        "is_vendor": profile.is_vendor,
        "points_balance": float(points.balance),
    }

    return Response(data, status=200)


# ============================================================
# 🛠️ UPDATE PROFILE
# ============================================================
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    profile = user.profile
    data = request.data

    user.email = data.get("email", user.email)
    user.save()

    profile.phone_number = data.get("phone_number", profile.phone_number)
    profile.bio = data.get("bio", profile.bio)
    profile.social_links = data.get("social_links", profile.social_links)
    profile.video_review_links = data.get("video_review_links", profile.video_review_links)
    profile.save()

    return Response({"message": "Profile updated successfully."}, status=200)


# ============================================================
# 🧾 GET PROFILE DETAILS
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
        "partner_application_status": profile.partner_application_status,
        "social_links": profile.social_links,
        "video_review_links": profile.video_review_links,
        "points_balance": float(points.balance),
    }, status=200)


# ============================================================
# 🏆 GET USER POINTS BALANCE
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_points(request):
    points, _ = KudiPoints.objects.get_or_create(user=request.user)
    return Response({"points": float(points.balance)}, status=200)


# ============================================================
# 💎 GET KUDI POINTS (WITH CEDIS VALUE)
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_kudi_points(request):
    user = request.user
    points, _ = KudiPoints.objects.get_or_create(user=user)

    return Response({
        "username": user.username,
        "points_balance": float(points.balance),
        "points_value_cedis": round(points.balance / 10, 2),
        "last_updated": points.updated_at,
    }, status=200)


# ============================================================
# ⭐ PARTNER ELIGIBILITY STATUS
# ============================================================
PARTNER_MIN_SPEND = 500
PARTNER_MIN_FOLLOWERS = 1000


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def partner_status(request):
    user = request.user
    profile = user.profile

    # 1️⃣ KYC requirement
    kyc_profile = getattr(user, "kyc_profile", None)
    kyc_status = getattr(kyc_profile, "status", "Pending")

    # 2️⃣ Total spent
    paid_orders = Order.objects.filter(
        user=user,
        status__in=[Order.Status.PAID, Order.Status.DELIVERED]
    )
    total_spent = sum(o.total_amount for o in paid_orders)
    meets_spend = total_spent >= PARTNER_MIN_SPEND

    # 3️⃣ Social followers requirement
    social_links = profile.social_links or {}
    social_followers = int(social_links.get("followers", 0))
    meets_social = social_followers >= PARTNER_MIN_FOLLOWERS

    # 4️⃣ Video review requirement
    video_links = profile.video_review_links or []
    has_video_review = len(video_links) > 0

    # 🟡 Final decision
    can_apply = meets_spend and meets_social and has_video_review and (kyc_status == "Approved")

    return Response({
        "kyc_status": kyc_status,
        "total_spent": float(total_spent),
        "meets_spend_requirement": meets_spend,

        "social_links": social_links,
        "social_followers": social_followers,
        "meets_social_requirement": meets_social,

        "video_review_links": video_links,
        "has_video_review": has_video_review,

        "can_apply": can_apply,
        "application_status": profile.partner_application_status,
    }, status=200)
from .models import PartnerApplication, Profile
from django.utils import timezone

# ============================================================
# 📩 APPLY TO BECOME A KUDIWAY PARTNER
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def apply_partner(request):
    """
    Submit a partner application.
    Enforces: 
      - must have ₵500+ total completed purchases
    """

    user = request.user
    data = request.data

    instagram = data.get("instagram_link", "")
    tiktok = data.get("tiktok_link", "")
    youtube = data.get("youtube_link", "")
    followers = int(data.get("followers", 0))
    video_link = data.get("video_review_link", "")

    # ------------------------------
    # 1️⃣ Check minimum purchase requirement
    # ------------------------------
    from orders.models import Order

    total_spent = (
        Order.objects.filter(user=user, status=Order.Status.PAID)
        .aggregate(models.Sum("total_amount"))["total_amount__sum"]
        or 0
    )

    if total_spent < 500:
        return Response({
            "error": "You must have at least ₵500 total completed purchases to apply.",
            "total_spent": float(total_spent),
        }, status=400)

    # ------------------------------
    # 2️⃣ Create or update application
    # ------------------------------
    app, created = PartnerApplication.objects.get_or_create(user=user)

    app.instagram_link = instagram
    app.tiktok_link = tiktok
    app.youtube_link = youtube
    app.followers = followers
    app.video_review_link = video_link
    app.status = "Pending"
    app.submitted_at = timezone.now()
    app.reviewed_at = None
    app.save()

    return Response({
        "message": "Application submitted successfully. You will be reviewed shortly.",
        "status": app.status,
    }, status=201)
# ============================================================
# ✅ ADMIN: APPROVE OR REJECT PARTNER APPLICATION
# ============================================================
from rest_framework.permissions import IsAdminUser
from django.shortcuts import get_object_or_404
from .models import PartnerApplication, Profile


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdminUser])  # 🔒 Only admins
def approve_partner(request, application_id):
    """
    Approve or reject a partner application.
    Admins ONLY.
    """
    action = request.data.get("action")  # "approve" or "reject"
    remarks = request.data.get("remarks", "")

    if action not in ["approve", "reject"]:
        return Response({"error": "Invalid action. Use 'approve' or 'reject'."}, status=400)

    application = get_object_or_404(PartnerApplication, id=application_id)
    profile = application.user.profile

    if application.is_reviewed:
        return Response({"error": "This application has already been reviewed."}, status=400)

    # ✅ Approve
    if action == "approve":
        application.status = "APPROVED"
        profile.is_verified_partner = True
        profile.save()

    # ❌ Reject
    else:
        application.status = "REJECTED"

    # Update logs
    application.is_reviewed = True
    application.admin_remarks = remarks
    application.save()

    return Response({
        "message": f"Application {action}d successfully.",
        "user": application.user.username,
        "status": application.status,
        "remarks": remarks,
    }, status=200)
# ------------------------------------------
# 🤝 PARTNER STATUS ENDPOINT
# ------------------------------------------
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum
from orders.models import Order
from users.models import Profile

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def partner_status(request):
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
    meets_spend_requirement = total_spent >= 500

    # 3️⃣ Social followers requirement
    social_followers = getattr(profile, "social_followers", 0)
    meets_social_requirement = social_followers >= 1000

    # 4️⃣ Video review requirement
    video_links = getattr(profile, "video_review_links", [])
    has_video_review = len(video_links) > 0

    # 5️⃣ Can apply?
    can_apply = (
        kyc_status == "Approved"
        and meets_spend_requirement
        and meets_social_requirement
        and has_video_review
        and not profile.is_verified_partner
    )

    return Response({
        "is_verified_partner": profile.is_verified_partner,
        "kyc_status": kyc_status,
        "total_spent": float(total_spent),
        "meets_spend_requirement": meets_spend_requirement,
        "social_followers": social_followers,
        "meets_social_requirement": meets_social_requirement,
        "video_review_links": video_links,
        "has_video_review": has_video_review,
        "can_apply": can_apply,
    })
