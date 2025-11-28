from django.urls import path, re_path
from . import views

urlpatterns = [
    # ============================================================
    # 🏬 STORE ROUTES
    # ============================================================
    # List all products
    path("products/", views.list_products, name="list_products"),

    # Get a single product
    path("products/<int:pk>/", views.get_product, name="get_product"),

    # ============================================================
    # 🧾 ORDERS
    # ============================================================
    # Create an order
    path("create/", views.create_order, name="create_order"),

    # Get user order history
    path("user-orders/", views.list_orders, name="list_orders"),

    # For UploadReviewScreen — purchased items list
    path("purchased-items/", views.purchased_items, name="purchased_items"),

    # See all orders (admin or debugging)
    path("all/", views.list_all_orders, name="orders-all"),

    # ============================================================
    # 🤝 PARTNER LISTINGS (Affiliate Resell)
    # ============================================================
    # Create or update partner (reseller) listing
    path("create-partner-listing/", views.create_partner_listing, name="create_partner_listing"),

    # Get all listings for a partner
    path("my-listings/", views.get_partner_listings, name="get_partner_listings"),

    # ============================================================
    # 🔗 REFERRAL SYSTEM
    # ============================================================
    # Return listing + product info when referral link is opened
    path("referral/<str:ref_code>/", views.get_referral_product, name="get_referral_product"),

    # Short redirect (used on website)
    re_path(r"^r/(?P<ref_code>[A-Za-z0-9]+)/$", views.get_referral_product, name="get_referral_product_short"),

    # Web checkout landing page (deep links into app)
    path("checkout/<str:ref_code>/", views.referral_checkout, name="referral_checkout"),
]
