from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import Sum
from .models import Profile, KudiPoints

# ======================================================
# INLINE: Show Points inside User
# ======================================================
class KudiPointsInline(admin.StackedInline):
    model = KudiPoints
    extra = 0
    readonly_fields = ("balance", "updated_at")


# ======================================================
# INLINE: Show Profile inside User
# ======================================================
class ProfileInline(admin.StackedInline):
    model = Profile
    extra = 0
    readonly_fields = (
        "partner_application_status",
        "is_verified_partner",
        "social_followers",
        "video_review_links",
    )


# ======================================================
# USER ADMIN PANEL
# ======================================================
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "email",
        "is_staff",
        "partner_status",
        "total_followers",
        "application_status",
        "kyc_status",
        "total_spent_display",
        "video_reviews_count",
    )
    search_fields = ("username", "email")
    list_filter = ("profile__partner_application_status",)

    inlines = [ProfileInline, KudiPointsInline]

    # Partner approved?
    def partner_status(self, obj):
        return "Yes" if obj.profile.is_verified_partner else "No"

    # Partner application status: none/pending/approved/rejected
    def application_status(self, obj):
        return obj.profile.partner_application_status.capitalize()

    # Number of social followers
    def total_followers(self, obj):
        return obj.profile.social_followers

    # Video review count
    def video_reviews_count(self, obj):
        return len(obj.profile.video_review_links or [])

    # KYC status
    def kyc_status(self, obj):
        kyc = getattr(obj, "kyc_profile", None)
        return kyc.status if kyc else "Missing"

    # Total purchases (paid orders only)
    def total_spent_display(self, obj):
        from orders.models import Order

        total = (
            Order.objects.filter(user=obj, status=Order.Status.PAID)
            .aggregate(Sum("total_amount"))["total_amount__sum"]
            or 0
        )
        return f"₵{total:.2f}"


# Remove default User admin & re-register
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# ======================================================
# ADMIN ACTIONS FOR APPROVAL & REJECTION
# ======================================================
@admin.action(description="Approve selected as Kudiway Partners")
def approve_selected(modeladmin, request, queryset):
    for user in queryset:
        profile = user.profile
        profile.is_verified_partner = True
        profile.partner_application_status = "approved"
        profile.save()


@admin.action(description="Reject selected partner applications")
def reject_selected(modeladmin, request, queryset):
    for user in queryset:
        profile = user.profile
        profile.is_verified_partner = False
        profile.partner_application_status = "rejected"
        profile.save()


# ======================================================
# PARTNER APPLICATION REVIEW PANEL
# (Admin view ONLY)
# ======================================================
class PartnerReviewAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "kyc_status",
        "total_spent_display",
        "social_followers",
        "video_reviews_count",
        "status",
    )
    actions = [approve_selected, reject_selected]

    def username(self, obj):
        return obj.username

    def kyc_status(self, obj):
        kyc = getattr(obj, "kyc_profile", None)
        return kyc.status if kyc else "Missing"

    def total_spent_display(self, obj):
        from orders.models import Order
        total = (
            Order.objects.filter(user=obj, status=Order.Status.PAID)
            .aggregate(Sum("total_amount"))["total_amount__sum"]
            or 0
        )
        return f"₵{total:.2f}"

    def social_followers(self, obj):
        return obj.profile.social_followers

    def video_reviews_count(self, obj):
        return len(obj.profile.video_review_links or [])

    def status(self, obj):
        return obj.profile.partner_application_status.capitalize()


# OPTIONAL: Register a special “Partner Review” section in admin
admin.site.register(Profile)
admin.site.register(KudiPoints)
