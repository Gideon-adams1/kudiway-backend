from django.contrib import admin
from .models import Profile, KudiPoints

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_verified_partner", "is_vendor")
    list_filter = ("is_verified_partner", "is_vendor")
    search_fields = ("user__username", "user__email")

@admin.register(KudiPoints)
class KudiPointsAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")
    search_fields = ("user__username",)
