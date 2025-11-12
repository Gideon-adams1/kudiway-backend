from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta, date

# =========================
# 💼 Wallet Model
# =========================
class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))          # 💼 Wallet funds
    savings_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))  # 🪙 Savings
    credit_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))   # 💳 Credit owed
    created_at = models.DateTimeField(auto_now_add=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("500.00"))
    credit_score = models.PositiveIntegerField(default=600)
    phone_number = models.CharField(max_length=10, blank=True, null=True, unique=True)


    def __str__(self):
        return f"{self.user.username}'s Wallet"

    # ✅ Utility method to safely update balance and log a transaction
    def update_balance(self, amount: Decimal, transaction_type: str, description: str = ""):
        """Adjusts wallet balance and logs a transaction automatically."""
        new_balance = self.balance + Decimal(amount)
        if new_balance < 0:
            raise ValueError("Insufficient funds")

        self.balance = new_balance
        self.save()

        # 🧾 Automatically log the transaction
        Transaction.objects.create(
            user=self.user,
            transaction_type=transaction_type,
            amount=abs(amount),
            description=description or f"Wallet {transaction_type} of ₵{abs(amount)}",
        )
        return self.balance

    # ✅ Credit score adjustment method
    def update_credit_score(self):
        """Auto-adjust credit score monthly based on repayment behavior and credit usage."""
        if self.credit_balance == 0:
            self.credit_score = min(self.credit_score + 10, 1000)
        elif self.credit_balance > (self.credit_limit * Decimal("0.8")):
            self.credit_score = max(self.credit_score - 15, 300)
        elif self.credit_balance < (self.credit_limit * Decimal("0.5")):
            self.credit_score = min(self.credit_score + 5, 1000)
        if self.savings_balance > (self.credit_balance * Decimal("0.5")):
            self.credit_score = min(self.credit_score + 3, 1000)
        self.save()
        return self.credit_score


# =========================
# 📜 Transaction Model
# =========================
class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ("deposit", "Deposit"),
        ("withdraw", "Withdraw"),
        ("borrow", "Borrow"),
        ("repay", "Repay"),
        ("transfer", "Transfer"),
        ("credit_purchase", "Credit Purchase"),
        ("limit_increase", "Limit Increase"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    description = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} ₵{self.amount:.2f}"

    class Meta:
        ordering = ["-timestamp"]


# =========================
# 💳 Unified Credit Purchase Model
# =========================
class CreditPurchase(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("PAID", "Paid"),
        ("DEFAULTED", "Defaulted"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="credit_purchases")
    item_name = models.CharField(max_length=150, default="Store Purchase")  # ✅ From your app’s BNPL flow
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    down_payment = models.DecimalField(max_digits=12, decimal_places=2)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("5.00"))
    penalty_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.00"))
    due_date = models.DateField(default=timezone.now() + timedelta(days=14))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.item_name} (₵{self.credit_amount})"

    def total_due(self):
        """Calculate total owed including interest and penalty if overdue"""
        base_due = self.credit_amount * (Decimal("1.00") + (self.interest_rate / Decimal("100")))
        if date.today() > self.due_date:
            penalty = self.credit_amount * (self.penalty_rate / Decimal("100"))
            return base_due + penalty
        return base_due


# =========================
# 🪪 Helper for File Uploads
# =========================
def kyc_upload_path(instance, filename):
    """Dynamic upload path for KYC files"""
    return f"kyc/{instance.user.username}/{filename}"


# =========================
# 🧾 KYC Model
# =========================
class KYC(models.Model):
    ID_TYPES = [
        ('Passport', 'Passport'),
        ('Driver’s License', 'Driver’s License'),
        ('National ID', 'National ID'),
        ('Voter ID', 'Voter ID'),
    ]

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="kyc_profile")
    full_name = models.CharField(max_length=150, default="Unknown")
    id_type = models.CharField(max_length=50, choices=ID_TYPES, default="Unknown")
    id_number = models.CharField(max_length=50, default="Unknown")
    id_front = models.ImageField(upload_to=kyc_upload_path, blank=True, null=True)
    id_back = models.ImageField(upload_to=kyc_upload_path, blank=True, null=True)
    selfie = models.ImageField(upload_to=kyc_upload_path, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    remarks = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.status}"
# --- MoMo callback log ---
# ✅ Logs every MoMo callback that hits your system
class MomoCallbackLog(models.Model):
    reference_id = models.CharField(max_length=100)
    status = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payer_id = models.CharField(max_length=50)
    raw = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.reference_id} - {self.status}"


# ✅ In-app notification system (for wallet events)
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    delivered = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}: {self.title}"
