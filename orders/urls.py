# orders/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # -----------------------------------------------------
    # Store
    # -----------------------------------------------------
    path("products/", views.list_products, name="list_products"),
    path("products/<int:pk>/", views.get_product, name="get_product"),

    # -----------------------------------------------------
    # Orders
    # -----------------------------------------------------
    path("create/", views.create_order, name="create_order"),
    path("user-orders/", views.list_orders, name="list_orders"),

    # -----------------------------------------------------
    # Purchased Items (for UploadReviewScreen)
    # -----------------------------------------------------
    path("purchased-items/", views.purchased_items, name="purchased_items"),

    # -----------------------------------------------------
    # Partner – Create listing only
    # (You removed get_partner_listings, so do not include it)
    # -----------------------------------------------------
    path(
        "create-partner-listing/",
        views.create_partner_listing,
        name="create_partner_listing",
    ),

    # -----------------------------------------------------
    # Referral (Web checkout flows only)
    # -----------------------------------------------------
    path(
        "checkout/<str:ref_code>/",
        views.referral_checkout,
        name="referral_checkout",
    ),

    # -----------------------------------------------------
    # Admin – List all orders
    # -----------------------------------------------------
    path("all/", views.list_all_orders, name="orders-all"),
]
