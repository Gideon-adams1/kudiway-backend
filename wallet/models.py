from django.conf import settings
from django.db import models
from decimal import Decimal


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    savings_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    credit_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("500.00"))
    credit_score = models.IntegerField(default=650)

    def __str__(self):
        return f"{self.user.username} Wallet — ₵{self.balance}"

    @property
    def available_credit(self):
        return max(Decimal("0.00"), self.credit_limit - self.credit_balance)

    def deposit(self, amount):
        self.balance += Decimal(amount)
        self.save()

    def withdraw(self, amount):
        if self.balance < Decimal(amount):
            raise ValueError("Insufficient funds.")
        self.balance -= Decimal(amount)
        self.save()

    def repay_credit(self, amount):
        self.credit_balance -= Decimal(amount)
        if self.credit_balance < 0:
            self.credit_balance = 0
        self.save()
