from django.contrib import admin
from django.urls import path, include
from kudiwallet import views as wallet_views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # ✅ User & Auth
    path('api/users/', include('users.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # ✅ Wallet Core
    path('api/wallet/summary/', wallet_views.wallet_summary, name='wallet_summary'),
    path('api/wallet/deposit/', wallet_views.deposit, name='deposit'),
    path('api/wallet/transfer-to-savings/', wallet_views.deposit_to_savings, name='deposit_to_savings'),
    path('api/wallet/withdraw/', wallet_views.withdraw_from_savings, name='withdraw_from_savings'),
    path('api/wallet/transactions/', wallet_views.transaction_history, name='transaction_history'),

    # ✅ Credit / BNPL routes
    path('api/wallet/credit-purchase/', wallet_views.make_credit_purchase, name='credit_purchase'),
    path('api/wallet/repay/', wallet_views.repay_credit, name='repay_credit'),
    path('api/wallet/credit-purchases/', wallet_views.credit_purchase_list, name='credit_purchase_list'),
    path('api/wallet/credit-score/', wallet_views.get_credit_score, name='get_credit_score'),
    path('api/wallet/request-limit-increase/', wallet_views.request_limit_increase, name='request_limit_increase'),

    # ✅ KYC
    path('api/kyc/upload/', wallet_views.upload_kyc, name='upload_kyc'),
    path('api/kyc/status/', wallet_views.get_kyc_status, name='get_kyc_status'),
    path('api/kyc/approve/<int:kyc_id>/', wallet_views.approve_kyc_admin, name='approve_kyc_admin'),
    path('api/kyc/reject/<int:kyc_id>/', wallet_views.reject_kyc_admin, name='reject_kyc_admin'),

    # ✅ Other app routes
    path('api/orders/', include('orders.urls')),
]

# ✅ Media files (images, KYC docs, etc.)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
