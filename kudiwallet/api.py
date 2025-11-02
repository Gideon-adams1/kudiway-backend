from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import Wallet, CreditPurchase, Transaction
from .serializers import WalletSerializer, CreditPurchaseSerializer


# ================================
# 💼 Wallet Detail View
# ================================
class WalletDetailView(APIView):
    """
    GET /api/wallet/
    Returns the current user's wallet info.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            wallet = Wallet.objects.get(user=request.user)
        except Wallet.DoesNotExist:
            return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = WalletSerializer(wallet)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
# ================================
# 💳 Credit Purchase View (Buy Now, Pay Later)
# ================================
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal
from .models import CreditPurchase, Transaction
from .serializers import CreditPurchaseSerializer


class CreditPurchaseView(APIView):
    """
    POST /api/wallet/credit-purchase/
    Creates a credit purchase (BNPL) transaction.
    Request Body:
    {
        "total_amount": 200,
        "down_payment_percent": 20
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            wallet = Wallet.objects.get(user=request.user)
        except Wallet.DoesNotExist:
            return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)

        total_amount = Decimal(request.data.get("total_amount", 0))
        down_payment_percent = Decimal(request.data.get("down_payment_percent", 20))  # Default 20%

        if total_amount <= 0:
            return Response({"error": "Invalid total amount"}, status=status.HTTP_400_BAD_REQUEST)

        down_payment = total_amount * (down_payment_percent / 100)
        credit_amount = total_amount - down_payment

        # 🧮 Check if user has enough balance for down payment
        if wallet.balance < down_payment:
            return Response({"error": "Insufficient wallet balance for down payment"}, status=status.HTTP_400_BAD_REQUEST)

        # 🧾 Deduct down payment instantly
        wallet.balance -= down_payment
        wallet.credit_balance += credit_amount
        wallet.save()

        # 💰 Log transaction
        Transaction.objects.create(
            user=request.user,
            transaction_type="credit_purchase",
            amount=total_amount,
            description=f"BNPL purchase of ₵{total_amount:.2f} (₵{down_payment:.2f} down, ₵{credit_amount:.2f} on credit)",
        )

        # 🗓️ Create Credit Purchase record
        purchase = CreditPurchase.objects.create(
            user=request.user,
            wallet=wallet,
            total_amount=total_amount,
            down_payment=down_payment,
            credit_amount=credit_amount,
            interest_rate=Decimal("5.00"),
            penalty_rate=Decimal("1.00"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        serializer = CreditPurchaseSerializer(purchase)
        return Response(
            {
                "message": "Credit purchase successful",
                "purchase": serializer.data,
                "new_balance": wallet.balance,
                "credit_balance": wallet.credit_balance,
            },
            status=status.HTTP_201_CREATED,
        )


# ================================
# 💳 Credit Purchase View (Buy Now, Pay Later)
# ================================
class CreditPurchaseView(APIView):
    """
    POST /api/wallet/credit-purchase/
    Creates a credit purchase (BNPL) transaction.
    Request Body:
    {
        "total_amount": 200,
        "down_payment_percent": 20
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            wallet = Wallet.objects.get(user=request.user)
        except Wallet.DoesNotExist:
            return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)

        total_amount = Decimal(request.data.get("total_amount", 0))
        down_payment_percent = Decimal(request.data.get("down_payment_percent", 20))  # Default 20%

        if total_amount <= 0:
            return Response({"error": "Invalid total amount"}, status=status.HTTP_400_BAD_REQUEST)

        down_payment = total_amount * (down_payment_percent / 100)
        credit_amount = total_amount - down_payment

        # 🧮 Check if user has enough balance for down payment
        if wallet.balance < down_payment:
            return Response({"error": "Insufficient wallet balance for down payment"}, status=status.HTTP_400_BAD_REQUEST)

        # 🧾 Deduct down payment instantly
        wallet.balance -= down_payment
        wallet.credit_balance += credit_amount
        wallet.save()

        # 💰 Log transaction
        Transaction.objects.create(
            user=request.user,
            transaction_type="credit_purchase",
            amount=total_amount,
            description=f"BNPL purchase of ₵{total_amount:.2f} (₵{down_payment:.2f} down, ₵{credit_amount:.2f} on credit)",
        )

        # 🗓️ Create Credit Purchase record
        purchase = CreditPurchase.objects.create(
            user=request.user,
            wallet=wallet,
            total_amount=total_amount,
            down_payment=down_payment,
            credit_amount=credit_amount,
            interest_rate=Decimal("5.00"),
            penalty_rate=Decimal("1.00"),
            due_date=timezone.now().date() + timedelta(days=14),
        )

        serializer = CreditPurchaseSerializer(purchase)
        return Response(
            {
                "message": "Credit purchase successful",
                "purchase": serializer.data,
                "new_balance": wallet.balance,
                "credit_balance": wallet.credit_balance,
            },
            status=status.HTTP_201_CREATED,
        )
# ================================
# 💸 Credit Repayment API
# ================================
from django.db.models import Sum

class RepayCreditView(APIView):
    """
    POST /api/wallet/repay/
    Allows user to repay part or all of their credit.
    Example:
    {
        "amount": 50
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            wallet = Wallet.objects.get(user=request.user)
        except Wallet.DoesNotExist:
            return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)

        amount = Decimal(request.data.get("amount", 0))
        if amount <= 0:
            return Response({"error": "Invalid repayment amount"}, status=status.HTTP_400_BAD_REQUEST)

        # 🧮 Check wallet balance
        if wallet.balance < amount:
            return Response({"error": "Insufficient wallet balance"}, status=status.HTTP_400_BAD_REQUEST)

        # 🧾 Get active credit purchases
        active_purchases = CreditPurchase.objects.filter(user=request.user, status="Pending").order_by("due_date")
        if not active_purchases.exists():
            return Response({"error": "No active credit purchases found"}, status=status.HTTP_400_BAD_REQUEST)

        total_due = Decimal(0)
        for purchase in active_purchases:
            # Apply penalty if overdue
            if timezone.now().date() > purchase.due_date:
                overdue_days = (timezone.now().date() - purchase.due_date).days
                penalty = (purchase.credit_amount * purchase.penalty_rate / 100) * overdue_days
                purchase.total_due = purchase.total_due + penalty
                purchase.save()

            total_due += purchase.total_due

        if wallet.credit_balance <= 0:
            return Response({"message": "No credit balance to repay."}, status=status.HTTP_200_OK)

        # 🏦 Deduct from wallet
        wallet.balance -= amount
        wallet.save()

        # 💳 Apply repayment to purchases
        remaining = amount
        for purchase in active_purchases:
            if remaining <= 0:
                break

            if remaining >= purchase.total_due:
                remaining -= purchase.total_due
                wallet.credit_balance -= purchase.credit_amount
                purchase.status = "Paid"
                purchase.save()
            else:
                purchase.total_due -= remaining
                wallet.credit_balance -= remaining
                remaining = 0
                purchase.save()

        wallet.save()

        # 🧾 Log transaction
        Transaction.objects.create(
            user=request.user,
            transaction_type="repay",
            amount=amount,
            description=f"Credit repayment of ₵{amount:.2f}",
        )

        # 💹 Update credit score
        wallet.update_credit_score()

        return Response(
            {
                "message": "Repayment successful",
                "amount_paid": amount,
                "remaining_credit_balance": wallet.credit_balance,
                "current_balance": wallet.balance,
                "credit_score": wallet.credit_score,
            },
            status=status.HTTP_200_OK,
        )
