from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


# ============================================================
# 🖼 Helper for profile image uploads
# ============================================================
def profile_upload_path(instance, filename):
    return f"profiles/{instance.user.username}/{filename}"


# ============================================================
# 👤 User Profile
# ============================================================
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    profile_picture = models.ImageField(upload_to=profile_upload_path, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)

    # ✅ Partner & Vendor verification flags
    is_verified_partner = models.BooleanField(default=False)
    is_vendor = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s Profile"


# ============================================================
# 💎 KudiPoints Wallet
# ============================================================
class KudiPoints(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="points")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} – {self.balance} pts"

    # ➕ Add points to user's balance
    def add_points(self, amount):
        if amount > 0:
            self.balance += amount
            self.save(update_fields=["balance", "updated_at"])
            return True
        return False

    # ➖ Redeem points for purchases
    def redeem_points(self, amount):
        if amount > 0 and self.balance >= amount:
            self.balance -= amount
            self.save(update_fields=["balance", "updated_at"])
            return True
        return False


# ============================================================
# 🧩 SIGNALS — Auto-create related objects
# ============================================================

@receiver(post_save, sender=User)
def create_related_user_objects(sender, instance, created, **kwargs):
    """
    Automatically create Profile and KudiPoints wallet for every new user.
    """
    if created:
        Profile.objects.create(user=instance)
        KudiPoints.objects.create(user=instance)
    else:
        # Ensure both related objects exist
        Profile.objects.get_or_create(user=instance)
        KudiPoints.objects.get_or_create(user=instance)
