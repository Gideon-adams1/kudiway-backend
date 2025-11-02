# orders/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # ============================================================
    # 🏬 STORE ROUTES
    # ============================================================
    path("products/", views.list_products, name="list_products"),
    path("products/<int:pk>/", views.get_product, name="get_product"),  # ✅ Single product details

    # ============================================================
    # 🛍️ ORDER ROUTES
    # ============================================================
    path("create/", views.create_order, name="create_order"),
    path("user-orders/", views.list_orders, name="list_orders"),

    # ============================================================
    # 🤝 PARTNER LISTINGS (Resale)
    # ============================================================
    # ✅ Matches what the frontend calls
    path("create-partner-listing/", views.create_partner_listing, name="create_partner_listing"),

    # ✅ Allow verified partners to fetch *their own listings*
    path("my-listings/", views.get_partner_listings, name="get_partner_listings"),
]
