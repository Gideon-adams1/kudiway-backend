from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils.text import slugify
import uuid


# ============================================================
# 🛍️ PRODUCT MODEL (Supports real image uploads)
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

    # ✅ Use ImageField for real uploads
    image = models.ImageField(upload_to="products/", null=True, blank=True)
    image2 = models.ImageField(upload_to="products/", null=True, blank=True)
    image3 = models.ImageField(upload_to="products/", null=True, blank=True)
    image4 = models.ImageField(upload_to="products/", null=True, blank=True)
    image5 = models.ImageField(upload_to="products/", null=True, blank=True)

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


# ============================================================
# 🤝 PARTNER LISTING MODEL (Resell & Earn)
# ============================================================
class PartnerListing(models.Model):
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
    resale_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True)
    slug = models.SlugField(unique=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Automatically calculate resale price and create unique slug."""
        if not self.resale_price:
            self.resale_price = (self.product.price or 0) + self.markup

        if not self.slug:
            base_slug = slugify(f"{self.partner.username}-{self.product.name}")
            unique_id = uuid.uuid4().hex[:6]
            self.slug = f"{base_slug}-{unique_id}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.partner} resells {self.product.name} (+₵{self.markup})"


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
        if self.pk:
            self.recompute_totals()
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
        help_text="If the item was sold through a partner, this links the reseller.",
    )

    def line_total(self):
        return self.price * self.quantity

    def save(self, *args, **kwargs):
        if not self.product_name_snapshot and self.product:
            self.product_name_snapshot = getattr(self.product, "name", str(self.product))
        if not self.product_image_snapshot and self.product:
            img = getattr(self.product, "image", "")
            self.product_image_snapshot = str(img or "")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name_snapshot or self.product} ×{self.quantity}"
