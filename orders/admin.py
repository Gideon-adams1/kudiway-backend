from django.contrib import admin
from .models import Product, PartnerListing, Order, OrderItem


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "price", "stock", "vendor", "created_at")
    search_fields = ("name", "vendor__username", "category")
    list_filter = ("category", "created_at")
    ordering = ("-created_at",)


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
        "created_at",
    )
    readonly_fields = ("final_price", "referral_url", "referral_code", "clicks", "sales_count", "created_at")
    search_fields = ("partner__username", "product__name", "referral_code")
    list_filter = ("created_at",)
    ordering = ("-created_at",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_name_snapshot", "price", "quantity", "partner")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "total_amount", "payment_method", "status", "created_at")
    list_filter = ("status", "payment_method", "created_at")
    search_fields = ("user__username",)
    inlines = [OrderItemInline]
    ordering = ("-created_at",)
