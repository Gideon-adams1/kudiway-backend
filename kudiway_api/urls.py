# kudiway_api/urls.py

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from orders import views as order_views
from orders.models import PartnerListing


# -----------------------------------------------------
# REFERRAL SHORT URL REDIRECT
# -----------------------------------------------------
def referral_redirect(request, ref_code):
    """
    Redirects https://kudiway.com/r/<ref_code>
    → API: /api/orders/referral/<ref_code>/
    """
    try:
        listing = PartnerListing.objects.get(referral_code=ref_code)
        listing.clicks += 1
        listing.save(update_fields=["clicks"])
        return redirect(f"/api/orders/referral/{ref_code}/")
    except PartnerListing.DoesNotExist:
        return redirect("/not-found/")


# -----------------------------------------------------
# URL PATTERNS
# -----------------------------------------------------
urlpatterns = [
    # -----------------------------------------------------
    # Admin
    # -----------------------------------------------------
    path("admin/", admin.site.urls),

    # -----------------------------------------------------
    # Auth
    # -----------------------------------------------------
    path("api/users/", include("users.urls")),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api-auth/", include("rest_framework.urls")),

    # -----------------------------------------------------
    # Wallet (single source of truth)
    # -----------------------------------------------------
    # ✅ IMPORTANT: let kudiwallet.urls define ALL wallet endpoints
    # This prevents duplicates + avoids missing view names
    path("api/wallet/", include("kudiwallet.urls")),

    # -----------------------------------------------------
    # Store + Orders (MAIN)
    # -----------------------------------------------------
    path("api/orders/", include("orders.urls")),

    # -----------------------------------------------------
    # Admin Dashboard
    # -----------------------------------------------------
    path("api/admin-dashboard/", include("dashboard.urls")),

    # -----------------------------------------------------
    # Referral Short URLs
    # -----------------------------------------------------
    path("r/<slug:ref_code>/", referral_redirect, name="referral_short"),
    path("checkout/<slug:ref_code>/", order_views.referral_checkout, name="referral_checkout_page"),

    # -----------------------------------------------------
    # Global Video Review System
    # -----------------------------------------------------
    path("api/reviews/", include("reviews.urls")),
]

# -----------------------------------------------------
# Media Files (dev)
# -----------------------------------------------------
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
