from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


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

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    profile_picture = models.ImageField(upload_to=profile_upload_path, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)

    # ✅ Partner & Vendor flags
    is_verified_partner = models.BooleanField(default=False)
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
    """
    Tracks reward points for every user.
    These points are earned through reselling, referrals, or activity.
    10 points = ₵1 (set in your reward logic).
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="points")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} – {self.balance} pts"

    # ➕ Add points to user's balance
    def add_points(self, amount):
        """
        Safely increase user's points balance.
        Example: add_points(200) → adds 200 points.
        """
        if amount > 0:
            self.balance += amount
            self.save(update_fields=["balance", "updated_at"])
            return True
        return False

    # ➖ Redeem points for checkout
    def redeem_points(self, amount):
        """
        Deduct points (e.g., when user pays with points).
        Returns True if successful.
        """
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
    Automatically create Profile and KudiPoints wallet for every new user.
    Ensures no user exists without these linked objects.
    """
    if created:
        Profile.objects.create(user=instance)
        KudiPoints.objects.create(user=instance)
    else:
        # Ensure both exist for legacy users
        Profile.objects.get_or_create(user=instance)
        KudiPoints.objects.get_or_create(user=instance)
