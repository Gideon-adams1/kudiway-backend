from decimal import Decimal
from rest_framework import serializers
from .models import Order, OrderItem, Product, PartnerListing

# ============================================================
# 🌍 Helper — SAFE & CONSISTENT URL BUILDER
# ============================================================
def build_full_url(request, image_field):
    """Return absolute URL or Cloudinary URL for any image payload."""
    if not image_field:
        return None

    # 1️⃣ If CloudinaryField → get `.url`
    try:
        url = image_field.url
    except Exception:
        url = str(image_field)

    if not url:
        return None

    # 2️⃣ If full http/https — normalize to https
    if url.startswith("http"):
        return url.replace("http://", "https://")

    # 3️⃣ Cloudinary public ID (short string, no slash)
    if len(url) < 100 and "/" not in url:
        return f"https://res.cloudinary.com/dmpymbirt/image/upload/{url}.jpg"

    # 4️⃣ Local media fallback
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
    name = serializers.CharField(source="product.name", read_only=True)
    description = serializers.CharField(source="product.description", read_only=True)
    category = serializers.CharField(source="product.category", read_only=True)
    rating = serializers.FloatField(source="product.rating", read_only=True)
    oldPrice = serializers.DecimalField(source="product.old_price", max_digits=10, decimal_places=2, read_only=True)
    base_price = serializers.DecimalField(source="product.price", max_digits=10, decimal_places=2, read_only=True)
    partner = serializers.CharField(source="partner.username", read_only=True)

    product = serializers.SerializerMethodField()
    is_resale = serializers.SerializerMethodField()

    image = serializers.SerializerMethodField()
    image2 = serializers.SerializerMethodField()
    image3 = serializers.SerializerMethodField()
    image4 = serializers.SerializerMethodField()
    image5 = serializers.SerializerMethodField()

    total_profit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = PartnerListing
        fields = [
            "id",
            "name",
            "description",
            "base_price",
            "final_price",
            "markup",
            "total_profit",
            "oldPrice",
            "category",
            "rating",
            "image",
            "image2",
            "image3",
            "image4",
            "image5",
            "partner",
            "referral_code",
            "referral_url",
            "is_resale",
            "product",
            "clicks",
            "sales_count",
            "created_at",
        ]

    def get_is_resale(self, obj):
        return True

    def get_product(self, obj):
        if not obj.product:
            return None
        return ProductSerializer(obj.product, context=self.context).data

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
# 🧾 ORDER ITEM SERIALIZER (UPDATED — GUARANTEED IMAGE)
# ============================================================
class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product_name_snapshot", read_only=True)
    image = serializers.SerializerMethodField()   # Unified image field
    line_total = serializers.SerializerMethodField()
    partner = serializers.CharField(source="partner.username", read_only=True, default=None)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "order",
            "product_id",
            "product_name",
            "image",
            "price",
            "quantity",
            "line_total",
            "partner",
            "review_product_id",
        ]

    def get_image(self, obj):
        request = self.context.get("request")

        # 1️⃣ First choice: snapshot (guaranteed correct)
        if obj.product_image_snapshot:
            return build_full_url(request, obj.product_image_snapshot)

        # 2️⃣ Live product image
        if obj.product and obj.product.image:
            return build_full_url(request, obj.product.image)

        return None

    def get_line_total(self, obj):
        return obj.price * obj.quantity


# ============================================================
# 💳 ORDER SERIALIZER
# ============================================================
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "items",
            "payment_method",
            "total_amount",
            "status",
            "created_at",
        ]

        read_only_fields = ["id", "user", "created_at"]
