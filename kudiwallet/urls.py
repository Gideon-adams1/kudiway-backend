# kudiwallet/urls.py

from django.urls import path
from . import views, api  # ✅ include api for wallet detail endpoint + credit endpoints

urlpatterns = [
    # 🪙 Main wallet info (used by the React Native app)
    path("", api.WalletDetailView.as_view(), name="wallet-detail"),

    # 💰 Core wallet actions
    path("deposit/", views.deposit, name="deposit"),
    path("withdraw/", views.withdraw_from_savings, name="withdraw"),
    path("transfer-to-savings/", views.deposit_to_savings, name="deposit_to_savings"),
    path("summary/", views.wallet_summary, name="wallet_summary"),
    path("update_balance/", views.update_wallet_balance, name="update-wallet-balance"),
    path("transactions/", views.transaction_history, name="transaction_history"),

    # 💳 Credit features
    # ✅ FIX: Removed broken function view: views.credit_purchase_list (doesn't exist)
    # ✅ Keep the API class-based view for credit purchase history/creation
    path("credit-purchase/", api.CreditPurchaseView.as_view(), name="credit-purchase"),
    path("borrow/", views.make_credit_purchase, name="make_credit_purchase"),
    path("repay/", api.RepayCreditView.as_view(), name="repay_credit"),
    path("credit-score/", views.get_credit_score, name="get_credit_score"),
    path("request-limit-increase/", views.request_limit_increase, name="request_limit_increase"),

    # 🧾 KYC routes
    path("upload/", views.upload_kyc, name="upload_kyc"),
    path("status/", views.get_kyc_status, name="get_kyc_status"),
    path("approve_kyc/<int:kyc_id>/", views.approve_kyc_admin, name="approve_kyc_admin"),
    path("reject_kyc/<int:kyc_id>/", views.reject_kyc_admin, name="reject_kyc_admin"),

    # 🔔 Notifications (in-app)
    path("notifications/", views.list_notifications, name="list_notifications"),
    path("notifications/ack/", views.ack_notifications, name="ack_notifications"),

    # 📲 MoMo Payment Integration
    path("momo-pay/", views.momo_payment_request, name="momo_payment_request"),
    path("momo-status/<str:reference_id>/", views.momo_payment_status, name="momo_payment_status"),
    path("momo-callback/", views.momo_callback, name="momo_callback"),
]
