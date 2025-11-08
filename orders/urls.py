# orders/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # ============================================================
    # 🏬 STORE ROUTES
    # ============================================================
    # 🔹 Get all products (vendor + partner listings)
    path("products/", views.list_products, name="list_products"),

    # 🔹 Get details for a single product (by ID)
    path("products/<int:pk>/", views.get_product, name="get_product"),

    # ============================================================
    # 🧾 ORDER ROUTES
    # ============================================================
    # 🔹 Create a new order (checkout)
    path("create/", views.create_order, name="create_order"),

    # 🔹 Get logged-in user’s past orders
    path("user-orders/", views.list_orders, name="list_orders"),

    # ============================================================
    # 🤝 PARTNER LISTINGS (Resell & Earn)
    # ============================================================
    # 🔹 Create or update a resale listing
    path("create-partner-listing/", views.create_partner_listing, name="create_partner_listing"),

    # 🔹 Get all resale listings for the current verified partner
    path("my-listings/", views.get_partner_listings, name="get_partner_listings"),

    # ============================================================
    # 🔗 AFFILIATE / REFERRAL LINK
    # ============================================================
    # 🔹 New endpoint — used when someone opens a referral link (e.g., /orders/referral/abc123/)
    path("referral/<str:ref_code>/", views.get_referral_product, name="get_referral_product"),
]
