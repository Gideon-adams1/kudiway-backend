from django.urls import path, re_path
from . import views
from .views import my_listings

urlpatterns = [
    # ============================================================
    # 🏬 STORE ROUTES
    # ============================================================
    # 🔹 Get all products (main Kudiway store)
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
    # 🤝 PARTNER LISTINGS (Affiliate Resell)
    # ============================================================
    # 🔹 Create or update a resale listing
    path("create-partner-listing/", views.create_partner_listing, name="create_partner_listing"),

    # 🔹 Get all resale listings for the current verified partner
    path("my-listings/", views.get_partner_listings, name="get_partner_listings"),

    # ============================================================
    # 🔗 AFFILIATE / REFERRAL LINKS
    # ============================================================
    # 🔹 Used when a buyer opens a referral link (API endpoint)
    path("referral/<str:ref_code>/", views.get_referral_product, name="get_referral_product"),

    # 🔹 Web-friendly short route for deep links (e.g., https://kudiwayapp.com/r/abc123)
    re_path(r"^r/(?P<ref_code>[A-Za-z0-9]+)/$", views.get_referral_product, name="get_referral_product_short"),
    path("checkout/<str:ref_code>/", views.referral_checkout, name="referral_checkout"),
    
    path("all/", views.list_all_orders, name="orders-all"),
    path("purchased-items/", views.purchased_items, name="purchased_items"),

    

]
