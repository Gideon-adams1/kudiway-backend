from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils.text import slugify
import uuid
from cloudinary.models import CloudinaryField


# ============================================================
# 🛍️ PRODUCT MODEL (Cloudinary image uploads)
# ============================================================
class Product(models.Model):
    CATEGORY_CHOICES = [
        ("Phones", "Phones"),
        ("Accessories", "Accessories"),
        ("Electronics", "Electronics"),
        ("Gadgets", "Gadgets"),
        ("Fashion", "Fashion"),
        ("Other", "Other"),
    ]

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, default="Other")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rating = models.FloatField(default=4.5)
    stock = models.PositiveIntegerField(default=0)

    # Cloudinary images
    image = CloudinaryField("image", blank=True, null=True)
    image2 = CloudinaryField("image", blank=True, null=True)
    image3 = CloudinaryField("image", blank=True, null=True)
    image4 = CloudinaryField("image", blank=True, null=True)
    image5 = CloudinaryField("image", blank=True, null=True)

    vendor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="products",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def discount_percent(self):
        if self.old_price and self.old_price > 0:
            return round(((self.old_price - self.price) / self.old_price) * 100, 1)
        return 0

    def save(self, *args, **kwargs):
        # Normalize image URLs to HTTPS
        for field_name in ["image", "image2", "image3", "image4", "image5"]:
            field = getattr(self, field_name)
            if field:
                try:
                    url = str(field.url).replace("http://", "https://")
                    setattr(self, field_name, url)
                except Exception:
                    if isinstance(field, str) and field.startswith("http"):
                        setattr(self, field_name, field.replace("http://", "https://"))
        super().save(*args, **kwargs)


# ============================================================
# 🤝 PARTNER LISTING MODEL
# ============================================================
class PartnerListing(models.Model):
    partner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="partner_listings"
    )
    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="partner_products"
    )

    markup = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True)
    referral_code = models.CharField(max_length=50, unique=True, blank=True)
    referral_url = models.URLField(blank=True, null=True)
    clicks = models.PositiveIntegerField(default=0)
    sales_count = models.PositiveIntegerField(default=0)
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    slug = models.SlugField(unique=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        base = self.product.price or Decimal("0.00")
        self.final_price = base + (self.markup or Decimal("0.00"))

        if not self.slug:
            base_slug = slugify(f"{self.partner.username}-{self.product.name}")
            unique_id = uuid.uuid4().hex[:6]
            self.slug = f"{base_slug}-{unique_id}"

        if not self.referral_code:
            self.referral_code = uuid.uuid4().hex[:8]

        self.referral_url = f"https://kudiway.com/r/{self.referral_code}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.partner.username} resells {self.product.name} (+₵{self.markup})"


# ============================================================
# 🧾 ORDER MODEL
# ============================================================
class Order(models.Model):
    class PaymentMethod(models.TextChoices):
        WALLET = "wallet", "Wallet"
        CREDIT = "credit", "Credit"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    vendor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="vendor_orders", null=True, blank=True
    )
    partner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="partner_sales", null=True, blank=True
    )
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.WALLET)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} — {self.user} — ₵{self.total_amount}"

    def recompute_totals(self):
        subtotal = Decimal("0.00")
        for item in self.items.all():
            subtotal += item.price * item.quantity
        self.subtotal_amount = subtotal
        self.total_amount = subtotal
        return self.total_amount

    def save(self, *args, **kwargs):
        from users.models import Profile  # avoid circular import

        is_update = self.pk is not None
        old_status = None

        if is_update:
            old_status = Order.objects.get(pk=self.pk).status
            self.recompute_totals()

        super().save(*args, **kwargs)

        # --------------------- Partner Eligibility ---------------------
        if is_update and old_status != "paid" and self.status == "paid":
            profile = Profile.objects.get(user=self.user)
            profile.total_spent += float(self.total_amount)

            qualifies = (
                profile.total_spent >= 500
                and profile.followers_count >= 1000
                and profile.video_reviews_count >= 1
                and self.user.kyc_profile.status == "Approved"
            )

            if qualifies:
                profile.is_partner_approved = True

            profile.save()

        # --------------------- Partner Profit ---------------------
        if is_update and self.status in ["paid", "delivered"]:
            for item in self.items.all():
                if item.partner and item.product:
                    base_price = getattr(item.product, "price", Decimal("0.00"))
                    profit = max(item.price - base_price, Decimal("0.00")) * item.quantity

                    if profit > 0:
                        listing = PartnerListing.objects.filter(
                            partner=item.partner, product=item.product
                        ).first()
                        if listing:
                            listing.sales_count += item.quantity
                            listing.total_profit += profit
                            listing.save(update_fields=["sales_count", "total_profit"])


# ============================================================
# 📦 ORDER ITEM MODEL (UPDATED)
# ============================================================
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, related_name="order_items", null=True, blank=True
    )

    price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    # Snapshots
    product_name_snapshot = models.CharField(max_length=255, blank=True, default="")
    product_image_snapshot = models.URLField(blank=True, default="")

    # Used by review system
    review_product_id = models.CharField(max_length=50, blank=True, null=True)

    partner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="partner_order_items",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.product_name_snapshot:
            return f"OrderItem #{self.id} — {self.product_name_snapshot}"
        return f"OrderItem #{self.id} — {self.product.name if self.product else 'Unknown'}"

    def save(self, *args, **kwargs):
        # -------------------------------------------------------
        # Always save product name snapshot
        # -------------------------------------------------------
        if self.product:
            self.product_name_snapshot = self.product.name

        # -------------------------------------------------------
        # Always save product image snapshot
        # -------------------------------------------------------
        if self.product:
            try:
                url = str(self.product.image.url)
                if url:
                    self.product_image_snapshot = url
            except Exception:
                pass

        super().save(*args, **kwargs)

        # -------------------------------------------------------
        # Ensure review_product_id always exists
        # -------------------------------------------------------
        if not self.review_product_id:
            rid = str(self.product.id) if self.product else f"OI-{self.id}"
            OrderItem.objects.filter(pk=self.pk).update(review_product_id=rid)
            self.review_product_id = rid
