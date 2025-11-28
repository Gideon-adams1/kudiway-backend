# kudiway_api/urls.py
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

from kudiwallet import views as wallet_views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from orders import views as order_views
from orders.models import PartnerListing


def referral_redirect(request, ref_code):
    """
    Redirect short links like https://kudiway.com/r/<ref_code>
    → to the API endpoint /api/orders/referral/<ref_code>/
    """
    try:
        listing = PartnerListing.objects.get(referral_code=ref_code)
        listing.clicks += 1
        listing.save(update_fields=["clicks"])
        return redirect(f"/api/orders/referral/{ref_code}/")
    except PartnerListing.DoesNotExist:
        return redirect("/not-found/")


urlpatterns = [
    # -----------------------------------------------------
    # Admin
    # -----------------------------------------------------
    path("admin/", admin.site.urls),

    # -----------------------------------------------------
    # User Auth
    # -----------------------------------------------------
    path("api/users/", include("users.urls")),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api-auth/", include("rest_framework.urls")),

    # -----------------------------------------------------
    # Wallet
    # -----------------------------------------------------
    path("api/wallet/summary/", wallet_views.wallet_summary, name="wallet_summary"),
    path("api/wallet/deposit/", wallet_views.deposit, name="deposit"),
    path("api/wallet/transfer-to-savings/", wallet_views.deposit_to_savings, name="deposit_to_savings"),
    path("api/wallet/withdraw/", wallet_views.withdraw_from_savings, name="withdraw_from_savings"),
    path("api/wallet/transactions/", wallet_views.transaction_history, name="transaction_history"),
    path("api/wallet/", include("kudiwallet.urls")),

    # Credit / BNPL
    path("api/wallet/credit-purchase/", wallet_views.make_credit_purchase, name="credit_purchase"),
    path("api/wallet/repay/", wallet_views.repay_credit, name="repay_credit"),
    path("api/wallet/credit-purchases/", wallet_views.credit_purchase_list, name="credit_purchase_list"),
    path("api/wallet/credit-score/", wallet_views.get_credit_score, name="get_credit_score"),
    path("api/wallet/request-limit-increase/", wallet_views.request_limit_increase, name="request_limit_increase"),

    # KYC
    path("api/kyc/upload/", wallet_views.upload_kyc, name="upload_kyc"),
    path("api/kyc/status/", wallet_views.get_kyc_status, name="get_kyc_status"),
    path("api/kyc/approve/<int:kyc_id>/", wallet_views.approve_kyc_admin, name="approve_kyc_admin"),
    path("api/kyc/reject/<int:kyc_id>/", wallet_views.reject_kyc_admin, name="reject_kyc_admin"),

    # -----------------------------------------------------
    # Orders & Store
    # -----------------------------------------------------
    path("api/orders/", include("orders.urls")),

    # -----------------------------------------------------
    # Dashboard
    # -----------------------------------------------------
    path("api/admin-dashboard/", include("dashboard.urls")),

    # -----------------------------------------------------
    # Referral Short URLs
    # -----------------------------------------------------
    path("r/<slug:ref_code>/", order_views.referral_redirect, name="referral_short"),
    path("checkout/<slug:ref_code>/", order_views.referral_checkout, name="referral_checkout_page"),

    # -----------------------------------------------------
    # Video Reviews
    # -----------------------------------------------------
    path("api/reviews/", include("reviews.urls")),
]

# -----------------------------------------------------
# Static / Media
# -----------------------------------------------------
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
