from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator


# ============================================================
# 🖼️ Helper for profile image uploads
# ============================================================
def profile_upload_path(instance, filename):
    """
    Dynamic path for each user’s profile picture.
    Example: profiles/gideon/profile.jpg
    """
    return f"profiles/{instance.user.username}/{filename}"


# ============================================================
# 👤 USER PROFILE MODEL
# ============================================================
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Basic info
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to=profile_upload_path, null=True, blank=True
    )

    # Partner program flags
    is_verified_partner = models.BooleanField(default=False)
    partner_application_status = models.CharField(
        max_length=20,
        default="none",  # none, pending, approved, rejected
        choices=[
            ("none", "None"),
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
    )

    # 🔗 Social / influence info for partner eligibility
    social_media_platform = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ("TikTok", "TikTok"),
            ("Instagram", "Instagram"),
            ("Facebook", "Facebook"),
            ("YouTube", "YouTube"),
            ("Snapchat", "Snapchat"),
            ("X", "X (Twitter)"),
            ("Other", "Other"),
        ],
        help_text="Primary social media platform used to promote Kudiway.",
    )

    social_media_handle = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Handle or profile link (e.g., @gideonadams).",
    )

    social_followers = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total followers on primary social account.",
    )

    # Multiple video review links allowed (YouTube, TikTok, Drive, etc.)
    video_review_links = models.JSONField(
        default=list,
        blank=True,
        null=True,
        help_text="List of URLs to product review videos.",
    )

    # Vendor flag (for store owners / sellers)
    is_vendor = models.BooleanField(default=False)

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

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="points"
    )
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
    """
    Automatically create Profile + Points wallet for every new user.
    Also ensures legacy users always have both.
    """
    if created:
        Profile.objects.create(user=instance)
        KudiPoints.objects.create(user=instance)
    else:
        Profile.objects.get_or_create(user=instance)
        KudiPoints.objects.get_or_create(user=instance)


# ============================================================
# ⭐ (OPTIONAL) KUDI PARTNER MODEL (extra analytics layer)
# ============================================================
class KudiPartner(models.Model):
    """
    Optional extra model if you want a separate partner analytics object.
    NOTE: Current partner logic mainly uses Profile fields.
    """

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
        help_text="Total purchases on Kudiway (GHS).",
    )
    followers_count = models.PositiveIntegerField(
        default=0,
        help_text="Social media followers.",
    )
    avg_engagement = models.PositiveIntegerField(
        default=0,
        help_text="Average likes/comments/views per post.",
    )
    primary_platform = models.CharField(
        max_length=50,
        blank=True,
        help_text="Platform: Instagram / TikTok / YouTube, etc.",
    )
    social_handle = models.CharField(
        max_length=100,
        blank=True,
        help_text="@username or profile link.",
    )
    has_video_review = models.BooleanField(
        default=False,
        help_text="Has posted at least one Kudiway product review video.",
    )

    # Partner status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="NEW",
    )

    requirements_met = models.BooleanField(
        default=False,
        help_text="True when ₵500+ spent, 1000+ followers, and verified review.",
    )

    # Meta fields
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"KudiPartner<{self.user.username}>"


# ============================================================
# 🤝 (OPTIONAL) PARTNER APPLICATION MODEL
# ============================================================
class PartnerApplication(models.Model):
    """
    Optional dedicated model to store detailed partner applications.
    Current API logic uses Profile.partner_application_status,
    but you can use this for deeper audit/history if needed.
    """

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="partner_application",
    )

    instagram_link = models.URLField(blank=True, null=True)
    tiktok_link = models.URLField(blank=True, null=True)
    youtube_link = models.URLField(blank=True, null=True)

    followers = models.PositiveIntegerField(default=0)
    video_review_link = models.URLField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pending",
    )
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} – {self.status}"
