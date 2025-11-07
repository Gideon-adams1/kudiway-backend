from rest_framework import serializers
from .models import Order, OrderItem, Product, PartnerListing

# ============================================================
# 🌍 Helper: Build absolute or Cloudinary URL
# ============================================================
def build_full_url(request, image_field):
    """Return a valid absolute URL (handles Cloudinary public_id or full URL)"""
    if not image_field:
        return None

    try:
        url = image_field.url  # works for Django FileFields
    except Exception:
        url = str(image_field)  # fallback if it's stored as plain text

    # ✅ If it's already a full URL
    if url.startswith("http"):
        return url.replace("http://", "https://")

    # ✅ If it's a Cloudinary public_id (no slashes, short string)
    if len(url) < 100 and "/" not in url:
        return f"https://res.cloudinary.com/dmpymbirt/image/upload/{url}.jpg"

    # ✅ Otherwise build absolute URI for local files
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
    price = serializers.DecimalField(source="resale_price", max_digits=10, decimal_places=2, read_only=True)
    partner = serializers.CharField(source="partner.username", read_only=True)
    is_resale = serializers.SerializerMethodField()

    product = serializers.SerializerMethodField()

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

    class Meta:
        model = OrderItem
        fields = ["id", "product_name", "image", "price", "quantity", "line_total"]

    def get_image(self, obj):
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
    items = OrderItemSerializer(many=True, read_only=True)
    down_payment = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    interest = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    credit_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    due_date = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "vendor",
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
        ]
        read_only_fields = [
            "id",
            "user",
            "vendor",
            "subtotal_amount",
            "total_amount",
            "status",
            "created_at",
            "updated_at",
        ]
