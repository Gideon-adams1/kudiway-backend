# orders/urls.py

from django.urls import path, re_path
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
    # Partner Listings
    # -----------------------------------------------------
    path("create-partner-listing/", views.create_partner_listing, name="create_partner_listing"),

    # ❗ REMOVE get_partner_listings — it no longer exists
    # path("my-listings/", views.get_partner_listings, ... )  <-- DELETE THIS

    # -----------------------------------------------------
    # Referral / Affiliate
    # -----------------------------------------------------
    path("referral/<str:ref_code>/", views.get_referral_product, name="get_referral_product"),
    re_path(r"^r/(?P<ref_code>[A-Za-z0-9]+)/$", views.get_referral_product, name="get_referral_product_short"),
    path("checkout/<str:ref_code>/", views.referral_checkout, name="referral_checkout"),

    # -----------------------------------------------------
    # Admin Orders
    # -----------------------------------------------------
    path("all/", views.list_all_orders, name="orders-all"),

    # -----------------------------------------------------
    # Purchased Items (for UploadReviewScreen)
    # -----------------------------------------------------
    path("purchased-items/", views.purchased_items, name="purchased_items"),
]
