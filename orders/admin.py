from django.contrib import admin
from django.db.models import Sum, Count
from .models import Product, PartnerListing, Order, OrderItem


# ======================================================
# PRODUCT ADMIN
# ======================================================
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "category",
        "price",
        "stock",
        "vendor",
        "created_at",
        "discount_percent",
    )
    search_fields = ("name", "vendor__username", "category")
    list_filter = ("category", "created_at")
    ordering = ("-created_at",)


# ======================================================
# PARTNER LISTING ADMIN (Partner Analytics)
# ======================================================
@admin.register(PartnerListing)
class PartnerListingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "partner",
        "product",
        "markup",
        "final_price",
        "clicks",
        "sales_count",
        "total_profit",
        "created_at",
    )
    readonly_fields = (
        "final_price",
        "referral_url",
        "referral_code",
        "clicks",
        "sales_count",
        "total_profit",
        "created_at",
    )
    search_fields = ("partner__username", "product__name", "referral_code")
    list_filter = ("created_at", "partner")
    ordering = ("-created_at",)

    # Display in admin list
    def total_profit_display(self, obj):
        return f"₵{obj.total_profit:.2f}"


# ======================================================
# ORDER ITEM INLINE
# ======================================================
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "product_name_snapshot",
        "product_image_snapshot",
        "price",
        "quantity",
        "partner",
        "line_total_display",
    )

    def line_total_display(self, obj):
        return f"₵{obj.line_total():.2f}"


# ======================================================
# ORDER ADMIN (Tracking buyer + partner activity)
# ======================================================
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "total_amount_display",
        "payment_method",
        "status",
        "partner_involved",
        "created_at",
    )
    list_filter = (
        "status",
        "payment_method",
        "created_at",
        "items__partner",
    )
    search_fields = ("id", "user__username")
    inlines = [OrderItemInline]
    ordering = ("-created_at",)

    # Display helpers
    def total_amount_display(self, obj):
        return f"₵{obj.total_amount:.2f}"

    def partner_involved(self, obj):
        """
        Show whether this order had partner-resold items.
        """
        has_partner = obj.items.filter(partner__isnull=False).exists()
        return "Yes" if has_partner else "No"


# ======================================================
# ADMIN DASHBOARD SUMMARY (Custom Panel)
# ======================================================
class OrdersOverviewAdmin(admin.ModelAdmin):
    change_list_template = "admin/orders_overview.html"

    def changelist_view(self, request, extra_context=None):
        # Summary statistics
        stats = {
            "total_orders": Order.objects.count(),
            "total_revenue": Order.objects.filter(
                status=Order.Status.PAID
            ).aggregate(Sum("total_amount"))["total_amount__sum"]
            or 0,

            "total_partner_sales": OrderItem.objects.filter(
                partner__isnull=False
            ).count(),

            "total_partner_profit": PartnerListing.objects.aggregate(
                Sum("total_profit")
            )["total_profit__sum"]
            or 0,

            "total_clicks": PartnerListing.objects.aggregate(
                Sum("clicks")
            )["clicks__sum"]
            or 0,

            "total_resell_items": PartnerListing.objects.aggregate(
                Count("id")
            )["id__count"],
        }

        extra_context = extra_context or {}
        extra_context["stats"] = stats
        return super().changelist_view(request, extra_context=extra_context)


# (Optional) register summary panel
# Uncomment if you create admin/orders_overview.html
# admin.site.register(Order, OrdersOverviewAdmin)
