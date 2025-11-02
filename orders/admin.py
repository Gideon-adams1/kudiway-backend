from django.contrib import admin
from .models import Product, PartnerListing, Order, OrderItem


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "vendor", "created_at")
    list_filter = ("category", "vendor")
    search_fields = ("name", "description")


@admin.register(PartnerListing)
class PartnerListingAdmin(admin.ModelAdmin):
    list_display = ("partner", "product", "markup", "resale_price", "created_at")
    search_fields = ("product__name", "partner__username")
    list_filter = ("partner",)
    readonly_fields = ("resale_price",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_name_snapshot", "quantity", "price", "partner")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "payment_method", "status", "total_amount", "created_at")
    list_filter = ("status", "payment_method")
    readonly_fields = ("subtotal_amount", "total_amount")
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("product_name_snapshot", "quantity", "price", "partner", "order")
    list_filter = ("partner", "order__status")
