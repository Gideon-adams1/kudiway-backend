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

    # ✅ Cloudinary images
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
        """Ensure all Cloudinary URLs are HTTPS and normalized."""
        for field_name in ["image", "image2", "image3", "image4", "image5"]:
            field = getattr(self, field_name)
            if field:
                try:
                    # CloudinaryField with .url
                    url = str(field.url).replace("http://", "https://")
                    setattr(self, field_name, url)
                except Exception:
                    # If it's already a string (stored URL or public id)
                    if isinstance(field, str) and field.startswith("http"):
                        setattr(self, field_name, field.replace("http://", "https://"))
                    elif isinstance(field, str) and len(field) < 100 and "/" not in field:
                        setattr(
                            self,
                            field_name,
                            f"https://res.cloudinary.com/dmpymbirt/image/upload/{field}.jpg",
                        )
        super().save(*args, **kwargs)


# ============================================================
# 🤝 PARTNER LISTING MODEL (Affiliate / Resale)
# ============================================================
class PartnerListing(models.Model):
    """
    Verified partner resells a Kudiway product with a profit markup.
    Buyers only see the final (base + markup) price via the referral link.
    """

    partner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="partner_listings",
    )
    product = models.ForeignKey(
        "Product",
        on_delete=models.CASCADE,
        related_name="partner_products",
    )

    markup = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True)
    referral_code = models.CharField(max_length=50, unique=True, blank=True)
    referral_url = models.URLField(blank=True, null=True)
    clicks = models.PositiveIntegerField(default=0)
    sales_count = models.PositiveIntegerField(default=0)
    total_profit = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Accumulates total confirmed profit from completed sales."
    )
    slug = models.SlugField(unique=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Generate unique slug, referral code, and final price."""
        # 🧮 Compute resale price
        base = self.product.price or Decimal("0.00")
        self.final_price = base + (self.markup or Decimal("0.00"))

        # 🪪 Unique slug + referral code
        if not self.slug:
            base_slug = slugify(f"{self.partner.username}-{self.product.name}")
            unique_id = uuid.uuid4().hex[:6]
            self.slug = f"{base_slug}-{unique_id}"

        if not self.referral_code:
            self.referral_code = uuid.uuid4().hex[:8]

        # 🌐 Construct referral URL
        base_domain = "https://kudiwayapp.com"  # 🔁 replace with production domain if needed
        self.referral_url = f"{base_domain}/r/{self.referral_code}"

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

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    vendor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="vendor_orders",
        null=True,
        blank=True,
    )
    partner = models.ForeignKey(  # optional overall partner on order (not required if tracked per item)
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="partner_sales",
        null=True,
        blank=True,
    )
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.WALLET,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
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
        """
        Recalculate totals & distribute partner profit ONLY after payment confirmation.
        - Profit per line = max(item.price - product.base_price, 0) * quantity
        - Accumulate into PartnerListing.total_profit
        - Increment PartnerListing.sales_count by quantity
        """
        # If updating an existing order, recompute subtotal/total
        if self.pk:
            self.recompute_totals()

            # 💰 Confirmed earnings only when paid or delivered
            if self.status in [self.Status.PAID, self.Status.DELIVERED]:
                for item in self.items.all():
                    if item.partner:
                        # Safely get the base price from product (fallback to 0 if product missing)
                        base_price = getattr(item.product, "price", None)
                        if base_price is None:
                            base_price = Decimal("0.00")

                        # Profit per unit
                        unit_profit = item.price - base_price
                        if unit_profit < 0:
                            unit_profit = Decimal("0.00")

                        # Total profit for the line
                        line_profit = unit_profit * item.quantity
                        if line_profit > 0:
                            # Find the listing (if it exists) to attribute the sale
                            listing = PartnerListing.objects.filter(
                                partner=item.partner,
                                product=item.product
                            ).first()

                            if listing:
                                listing.sales_count += item.quantity
                                listing.total_profit = (listing.total_profit or Decimal("0.00")) + line_profit
                                # Persist safely
                                listing.save(update_fields=["sales_count", "total_profit"])

        super().save(*args, **kwargs)


# ============================================================
# 📦 ORDER ITEM MODEL
# ============================================================
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        related_name="order_items",
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    product_name_snapshot = models.CharField(max_length=200, blank=True, default="")
    product_image_snapshot = models.URLField(blank=True, default="")
    partner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="partner_order_items",
        help_text="If the item was sold through a partner referral link.",
    )

    def line_total(self):
        return self.price * self.quantity

    def save(self, *args, **kwargs):
        """Preserve product snapshots for history."""
        if not self.product_name_snapshot and self.product:
            self.product_name_snapshot = getattr(self.product, "name", str(self.product))
        if not self.product_image_snapshot and self.product:
            img = getattr(self.product, "image", "")
            if img:
                try:
                    self.product_image_snapshot = str(img.url).replace("http://", "https://")
                except Exception:
                    if isinstance(img, str):
                        if img.startswith("http"):
                            self.product_image_snapshot = img.replace("http://", "https://")
                        elif len(img) < 100 and "/" not in img:
                            self.product_image_snapshot = (
                                f"https://res.cloudinary.com/dmpymbirt/image/upload/{img}.jpg"
                            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name_snapshot or self.product} ×{self.quantity}"
