from django.urls import path, re_path
from . import views

urlpatterns = [
    # ============================================================
    # 🏬 STORE ROUTES
    # ============================================================
    path("products/", views.list_products, name="list_products"),
    path("products/<int:pk>/", views.get_product, name="get_product"),

    # ============================================================
    # 🧾 ORDERS
    # ============================================================
    path("create/", views.create_order, name="create_order"),
    path("user-orders/", views.list_orders, name="list_orders"),
    path("all/", views.list_all_orders, name="orders-all"),  # ADMIN

    # ============================================================
    # 🤝 PARTNER LISTINGS
    # ============================================================
    path("create-partner-listing/", views.create_partner_listing, name="create_partner_listing"),
    path("my-listings/", views.get_partner_listings, name="get_partner_listings"),

    # ============================================================
    # 🎥 PURCHASED ITEMS
    # ============================================================
    path("purchased-items/", views.purchased_items, name="purchased_items"),

    # ============================================================
    # 🔗 REFERRAL HANDLERS
    # ============================================================
    path("referral/<str:ref_code>/", views.get_referral_product, name="get_referral_product"),

    # Short link support (for website)
    re_path(r"^r/(?P<ref_code>[A-Za-z0-9]+)/$", views.get_referral_product, name="get_referral_product_short"),

    # HTML page for referral checkout (deep link entry)
    path("checkout/<str:ref_code>/", views.referral_checkout, name="referral_checkout"),
]
