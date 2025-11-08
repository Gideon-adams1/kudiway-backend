from django.contrib import admin
from .models import Profile, KudiPoints


# ============================================================
# 👤 Profile Admin
# ============================================================
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_verified_partner", "is_vendor", "phone_number")
    list_filter = ("is_verified_partner", "is_vendor")
    search_fields = ("user__username", "user__email", "phone_number")
    ordering = ("user__username",)
    readonly_fields = ("id",)

    fieldsets = (
        ("User Information", {"fields": ("user", "profile_picture", "phone_number", "bio")}),
        ("Verification Status", {"fields": ("is_verified_partner", "is_vendor")}),
    )


# ============================================================
# 💎 KudiPoints Admin
# ============================================================
@admin.register(KudiPoints)
class KudiPointsAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")
    search_fields = ("user__username",)
    readonly_fields = ("updated_at",)
    ordering = ("-updated_at",)
