from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone


# ============================================================
# 🖼️ Helper for profile image uploads
# ============================================================
def profile_upload_path(instance, filename):
    """Dynamic path for each user’s profile picture."""
    return f"profiles/{instance.user.username}/{filename}"


# ============================================================
# 👤 USER PROFILE MODEL
# ============================================================
class Profile(models.Model):
    """
    Extended user profile that stores contact info, picture, and user role flags.
    Each user automatically has one Profile (created via signals below).
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile"
    )
    profile_picture = models.ImageField(
        upload_to=profile_upload_path, blank=True, null=True
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)

    # ✅ Partner & Vendor flags
    is_verified_partner = models.BooleanField(default=False)
    is_vendor = models.BooleanField(default=False)

    # ✅ Partner eligibility helpers
    social_followers = models.IntegerField(default=0)
    # Links to TikTok/IG/YouTube/X reviews etc.
    video_review_links = models.JSONField(default=list, blank=True)

    # ✅ Partner application status
    # "none" → never applied
    # "pending" → submitted, waiting review
    # "approved" → verified partner
    # "rejected" → reviewed but rejected
    PARTNER_APP_STATUSES = [
        ("none", "None"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    partner_application_status = models.CharField(
        max_length=20,
        choices=PARTNER_APP_STATUSES,
        default="none",
    )

    def __str__(self):
        return f"{self.user.username}'s Profile"

    @property
    def points_balance(self):
        """
        Quick access to the user's KudiPoints balance.
        Returns 0 if the user has no points wallet (failsafe).
        """
        return self.user.points.balance if hasattr(self.user, "points") else 0



# ============================================================
# 💎 KUDIWAY POINTS WALLET MODEL
# ============================================================
class KudiPoints(models.Model):
    """Tracks reward points for each user."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="points")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} – {self.balance} pts"

    # ➕ Add points
    def add_points(self, amount):
        if amount > 0:
            self.balance += amount
            self.save(update_fields=["balance", "updated_at"])
            return True
        return False

    # ➖ Redeem points
    def redeem_points(self, amount):
        if amount > 0 and self.balance >= amount:
            self.balance -= amount
            self.save(update_fields=["balance", "updated_at"])
            return True
        return False


# ============================================================
# 🧩 SIGNALS — AUTO-CREATE PROFILE & POINTS
# ============================================================
@receiver(post_save, sender=User)
def create_related_user_objects(sender, instance, created, **kwargs):
    """Automatically create Profile + Points wallet for every new user."""
    if created:
        Profile.objects.create(user=instance)
        KudiPoints.objects.create(user=instance)
    else:
        Profile.objects.get_or_create(user=instance)
        KudiPoints.objects.get_or_create(user=instance)


# ============================================================
# ⭐ KUDI PARTNER MODEL (RESELLER PROGRAM)
# ============================================================
class KudiPartner(models.Model):
    STATUS_CHOICES = [
        ("NEW", "New"),
        ("PENDING", "Pending Review"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kudi_partner",
    )

    # Requirements tracking
    total_spent_ghs = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Total purchases on Kudiway (GHS)."
    )
    followers_count = models.PositiveIntegerField(
        default=0,
        help_text="Social media followers."
    )
    avg_engagement = models.PositiveIntegerField(
        default=0,
        help_text="Average likes/comments/views per post."
    )
    primary_platform = models.CharField(
        max_length=50,
        blank=True,
        help_text="Platform: Instagram / TikTok / YouTube"
    )
    social_handle = models.CharField(
        max_length=100,
        blank=True,
        help_text="@username or profile link"
    )
    has_video_review = models.BooleanField(
        default=False,
        help_text="Has posted at least one Kudiway product review video."
    )

    # Partner status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="NEW",
    )

    requirements_met = models.BooleanField(
        default=False,
        help_text="Auto true when ₵500+ spent, 1000 followers, + verified review."
    )

    # Meta fields
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'KudiPartner<{self.user.username}>'
# ============================================================
# 🤝 PARTNER APPLICATION MODEL
# ============================================================
class PartnerApplication(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="partner_application")
    instagram_link = models.URLField(blank=True, null=True)
    tiktok_link = models.URLField(blank=True, null=True)
    youtube_link = models.URLField(blank=True, null=True)

    followers = models.PositiveIntegerField(default=0)

    video_review_link = models.URLField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} – {self.status}"
