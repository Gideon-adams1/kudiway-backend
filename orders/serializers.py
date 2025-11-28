from decimal import Decimal
from rest_framework import serializers
from .models import Order, OrderItem, Product, PartnerListing


# ============================================================
# 🌍 UNIVERSAL SAFE URL BUILDER
# Works for CloudinaryField, snapshot strings, relative URLs
# ============================================================
def build_full_url(request, image):
    """
    Returns a fully qualified image URL.
    Handles:
      - CloudinaryField → .url
      - Regular string URLs → returned as https://
      - Cloudinary public_id strings → auto-expand
      - Relative paths → converted via request.build_absolute_uri
    """

    if not image:
        return None

    # 1️⃣ CloudinaryField: get the real URL
    try:
        url = image.url
    except Exception:
        url = str(image)

    if not url:
        return None

    # 2️⃣ If already full URL:
    if url.startswith("http"):
        return url.replace("http://", "https://")

    # 3️⃣ Cloudinary public ID (no slashes, short)
    if len(url) < 150 and "/" not in url:
        # Example: "kdf82kd92" → expand to cloudinary URL
        return f"https://res.cloudinary.com/dmpymbirt/image/upload/{url}.jpg"

    # 4️⃣ Local relative path
    if request:
        return request.build_absolute_uri(url)

    return url


# ============================================================
# 🛍️ PRODUCT SERIALIZER
# (Used everywhere: Store, PartnerListing, etc.)
# ============================================================
class ProductSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.username", read_only=True)
    oldPrice = serializers.DecimalField(
        source="old_price", max_digits=10, decimal_places=2, read_only=True
    )

    # 5 images guaranteed
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
# (Used when someone opens referral link)
# ============================================================
class PartnerListingSerializer(serializers.ModelSerializer):
    partner = serializers.CharField(source="partner.username", read_only=True)

    # Product fields forwarded
    name = serializers.CharField(source="product.name", read_only=True)
    description = serializers.CharField(source="product.description", read_only=True)
    category = serializers.CharField(source="product.category", read_only=True)
    rating = serializers.FloatField(source="product.rating", read_only=True)
    oldPrice = serializers.DecimalField(
        source="product.old_price", max_digits=10, decimal_places=2, read_only=True
    )
    base_price = serializers.DecimalField(
        source="product.price", max_digits=10, decimal_places=2, read_only=True
    )

    # Product included as nested serializer
    product = serializers.SerializerMethodField()
    is_resale = serializers.SerializerMethodField()

    # Partner sale images
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
        return build_full_url(self.context.get("request"), obj.product.image)

    def get_image2(self, obj):
        return build_full_url(self.context.get("request"), obj.product.image2)

    def get_image3(self, obj):
        return build_full_url(self.context.get("request"), obj.product.image3)

    def get_image4(self, obj):
        return build_full_url(self.context.get("request"), obj.product.image4)

    def get_image5(self, obj):
        return build_full_url(self.context.get("request"), obj.product.image5)


# ============================================================
# 📦 ORDER ITEM SERIALIZER
# (Used in My Orders, dashboard, etc.)
# ============================================================
class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(
        source="product_name_snapshot", read_only=True
    )
    image = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()
    partner = serializers.CharField(
        source="partner.username", read_only=True, default=None
    )

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

        # 1️⃣ Snapshot FIRST (most accurate)
        if obj.product_image_snapshot:
            return build_full_url(request, obj.product_image_snapshot)

        # 2️⃣ Fallback to product image
        if obj.product and obj.product.image:
            return build_full_url(request, obj.product.image)

        return None

    def get_line_total(self, obj):
        return obj.price * obj.quantity


# ============================================================
# 🧾 ORDER SERIALIZER
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
