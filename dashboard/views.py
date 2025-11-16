# dashboard/views.py
from django.contrib.auth.models import User
from django.db.models import Sum, Count, F
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from users.models import Profile, KudiPoints
from orders.models import Product, Order, OrderItem, PartnerListing


# =========================================================
# 📊 1. ADMIN OVERVIEW DASHBOARD
# =========================================================
@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_overview(request):
    """
    High-level overview for Kudiway admins:
    - Users, partners, pending applications
    - Orders + revenue
    - Product inventory (total + low stock)
    """
    # 👤 Users & partners
    total_users = User.objects.count()
    total_partners = Profile.objects.filter(is_verified_partner=True).count()
    pending_applications = Profile.objects.filter(
        partner_application_status="pending"
    ).count()

    # 🧾 Orders & revenue
    total_orders = Order.objects.count()
    paid_orders = Order.objects.filter(status=Order.Status.PAID)
    total_revenue = (
        paid_orders.aggregate(Sum("total_amount"))["total_amount__sum"] or 0
    )

    # 📦 Products & inventory
    total_products = Product.objects.count()
    low_stock_products = Product.objects.filter(stock__lte=5).count()

    # 🔝 Top 5 selling products (by quantity)
    top_products_qs = (
        OrderItem.objects.values("product_name_snapshot")
        .annotate(
            total_sold=Sum("quantity"),
            total_sales=Sum(F("price") * F("quantity")),
        )
        .order_by("-total_sold")[:5]
    )
    top_products = [
        {
            "name": item["product_name_snapshot"],
            "total_sold": int(item["total_sold"] or 0),
            "total_sales": float(item["total_sales"] or 0),
        }
        for item in top_products_qs
    ]

    data = {
        "users": {
            "total_users": total_users,
            "total_partners": total_partners,
            "pending_partner_applications": pending_applications,
        },
        "orders": {
            "total_orders": total_orders,
            "paid_orders": paid_orders.count(),
            "total_revenue": float(total_revenue),
        },
        "inventory": {
            "total_products": total_products,
            "low_stock_products": low_stock_products,
        },
        "top_products": top_products,
    }

    return Response(data, status=status.HTTP_200_OK)


# =========================================================
# 📈 2. PARTNER PERFORMANCE DASHBOARD
# =========================================================
@api_view(["GET"])
@permission_classes([IsAdminUser])
def partner_performance(request):
    """
    Analytics focused on partners:
    - Top earning partners (by total_profit from PartnerListing)
    - Total clicks & sales driven
    """
    # Group by partner and sum metrics from PartnerListing
    partner_stats_qs = (
        PartnerListing.objects.values("partner_id", "partner__username")
        .annotate(
            total_profit=Sum("total_profit"),
            total_clicks=Sum("clicks"),
            total_sales=Sum("sales_count"),
        )
        .order_by("-total_profit")
    )

    partner_stats = [
        {
            "partner_id": row["partner_id"],
            "username": row["partner__username"],
            "total_profit": float(row["total_profit"] or 0),
            "total_clicks": int(row["total_clicks"] or 0),
            "total_sales": int(row["total_sales"] or 0),
        }
        for row in partner_stats_qs
    ]

    data = {
        "total_partners_tracked": len(partner_stats),
        "partners": partner_stats,
    }

    return Response(data, status=status.HTTP_200_OK)
