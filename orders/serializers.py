from rest_framework import serializers
from .models import Order, OrderItem, Product, PartnerListing


# ============================================================
# 🌍 Helper — Build secure, absolute or Cloudinary URL
# ============================================================
def build_full_url(request, image_field):
    """Return an absolute, HTTPS-safe Cloudinary or media URL."""
    if not image_field:
        return None

    try:
        url = image_field.url  # Works for FileFields
    except Exception:
        url = str(image_field)  # Fallback if it's stored as string

    if not url:
        return None

    # ✅ Already a full URL
    if url.startswith("http"):
        return url.replace("http://", "https://")

    # ✅ Likely a Cloudinary public ID
    if len(url) < 100 and "/" not in url:
        return f"https://res.cloudinary.com/dmpymbirt/image/upload/{url}.jpg"

    # ✅ Local media file
    return request.build_absolute_uri(url) if request else url


# ============================================================
# 🛍️ PRODUCT SERIALIZER
# ============================================================
class ProductSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.username", read_only=True)
    oldPrice = serializers.DecimalField(source="old_price", max_digits=10, decimal_places=2, read_only=True)

    image = serializers.SerializerMethodField()
    image2 = serializers.SerializerMethodField()
    image3 = serializers.SerializerMethodField()
    image4 = serializers.SerializerMethodField()
    image5 = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "price",
            "oldPrice",
            "category",
            "rating",
            "stock",
            "image",
            "image2",
            "image3",
            "image4",
            "image5",
            "vendor_name",
            "created_at",
        ]

    def get_image(self, obj):
        return build_full_url(self.context.get("request"), obj.image)

    def get_image2(self, obj):
        return build_full_url(self.context.get("request"), obj.image2)

    def get_image3(self, obj):
        return build_full_url(self.context.get("request"), obj.image3)

    def get_image4(self, obj):
        return build_full_url(self.context.get("request"), obj.image4)

    def get_image5(self, obj):
        return build_full_url(self.context.get("request"), obj.image5)


# ============================================================
# 🤝 PARTNER LISTING SERIALIZER
# ============================================================
class PartnerListingSerializer(serializers.ModelSerializer):
    """Expose resale listings with attached base product info."""

    # 🔹 Basic product data flattening
    name = serializers.CharField(source="product.name", read_only=True)
    description = serializers.CharField(source="product.description", read_only=True)
    category = serializers.CharField(source="product.category", read_only=True)
    rating = serializers.FloatField(source="product.rating", read_only=True)
    oldPrice = serializers.DecimalField(source="product.old_price", max_digits=10, decimal_places=2, read_only=True)
    price = serializers.DecimalField(source="resale_price", max_digits=10, decimal_places=2, read_only=True)
    partner = serializers.CharField(source="partner.username", read_only=True)
    is_resale = serializers.SerializerMethodField()

    # 🔹 Nested product data
    product = serializers.SerializerMethodField()

    # 🔹 Flatten Cloudinary images
    image = serializers.SerializerMethodField()
    image2 = serializers.SerializerMethodField()
    image3 = serializers.SerializerMethodField()
    image4 = serializers.SerializerMethodField()
    image5 = serializers.SerializerMethodField()

    class Meta:
        model = PartnerListing
        fields = [
            "id",
            "name",
            "description",
            "price",
            "oldPrice",
            "category",
            "rating",
            "image",
            "image2",
            "image3",
            "image4",
            "image5",
            "partner",
            "markup",
            "is_resale",
            "product",
            "created_at",
        ]

    def get_is_resale(self, obj):
        return True

    def get_product(self, obj):
        return ProductSerializer(obj.product, context=self.context).data if obj.product else None

    def get_image(self, obj):
        return build_full_url(self.context.get("request"), getattr(obj.product, "image", None))

    def get_image2(self, obj):
        return build_full_url(self.context.get("request"), getattr(obj.product, "image2", None))

    def get_image3(self, obj):
        return build_full_url(self.context.get("request"), getattr(obj.product, "image3", None))

    def get_image4(self, obj):
        return build_full_url(self.context.get("request"), getattr(obj.product, "image4", None))

    def get_image5(self, obj):
        return build_full_url(self.context.get("request"), getattr(obj.product, "image5", None))


# ============================================================
# 🧾 ORDER ITEM SERIALIZER
# ============================================================
class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product_name_snapshot", read_only=True)
    image = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()
    partner = serializers.CharField(source="partner.username", read_only=True, default=None)

    class Meta:
        model = OrderItem
        fields = ["id", "product_name", "image", "price", "quantity", "line_total", "partner"]

    def get_image(self, obj):
        """Return secure snapshot image."""
        request = self.context.get("request")
        if obj.product_image_snapshot:
            return build_full_url(request, obj.product_image_snapshot)
        return None

    def get_line_total(self, obj):
        return obj.price * obj.quantity


# ============================================================
# 💳 ORDER SERIALIZER
# ============================================================
class OrderSerializer(serializers.ModelSerializer):
    """
    Serializes entire order, with nested items and total breakdown.
    Automatically includes partner name if order was made via reseller.
    """

    items = OrderItemSerializer(many=True, read_only=True)
    vendor_name = serializers.CharField(source="vendor.username", read_only=True, default=None)
    user_name = serializers.CharField(source="user.username", read_only=True)
    total_points_earned = serializers.SerializerMethodField()

    down_payment = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    interest = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    credit_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    due_date = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "user_name",
            "vendor_name",
            "subtotal_amount",
            "total_amount",
            "payment_method",
            "status",
            "note",
            "down_payment",
            "interest",
            "credit_amount",
            "due_date",
            "created_at",
            "updated_at",
            "items",
            "total_points_earned",
        ]
        read_only_fields = [
            "id",
            "user_name",
            "vendor_name",
            "subtotal_amount",
            "total_amount",
            "status",
            "created_at",
            "updated_at",
            "total_points_earned",
        ]

    def get_total_points_earned(self, obj):
        """Calculate total points earned from resold items."""
        total_points = 0
        for item in obj.items.all():
            if item.partner:
                base_price = getattr(item.product, "price", 0)
                profit = max(0, item.price - base_price)
                total_points += int(profit * 10)  # 10 pts = ₵1
        return total_points
