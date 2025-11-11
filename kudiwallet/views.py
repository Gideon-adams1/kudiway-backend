from decimal import Decimal, InvalidOperation
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
import uuid  # ✅ added for generating MoMo reference IDs

from .models import Wallet, Transaction, KYC, CreditPurchase
from .serializers import TransactionSerializer, KYCSerializer

# ✅ Import MoMo helper functions
from .momo import request_payment, check_payment_status


# ============================================================
# 💰 TRANSACTION UTIL
# ============================================================
def log_transaction(user, transaction_type, amount, description=""):
    """Helper to create transaction record"""
    Transaction.objects.create(
        user=user,
        transaction_type=transaction_type,
        amount=amount,
        description=description,
    )


# ============================================================
# 💼 WALLET SUMMARY
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_summary(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    return Response({
        "username": request.user.username,
        "balance": str(wallet.balance),
        "savings_balance": str(wallet.savings_balance),
        "credit_balance": str(wallet.credit_balance),
        "credit_score": wallet.credit_score,
        "credit_limit": str(wallet.credit_limit),
    })


# ============================================================
# 💳 UPDATE BALANCE (Store Checkout)
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_wallet_balance(request):
    """Update the wallet balance by a positive or negative change"""
    try:
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        change = Decimal(request.data.get("change", 0))
        description = request.data.get("description", "Wallet update")

        if change == 0:
            return Response({"error": "Change amount cannot be zero."}, status=400)

        transaction_type = "withdraw" if change < 0 else "deposit"
        wallet.balance += change

        if wallet.balance < 0:
            return Response({"error": "Insufficient funds."}, status=400)

        wallet.save()
        log_transaction(request.user, transaction_type, abs(change), description)

        return Response({
            "message": "Wallet updated successfully.",
            "balance": str(wallet.balance),
            "change": str(change),
        })
    except Exception as e:
        return Response({"error": str(e)}, status=500)


# ============================================================
# 💵 DEPOSIT
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def deposit(request):
    try:
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        amount = Decimal(request.data.get("amount", 0))
        target = request.data.get("target", "wallet").lower()

        if amount <= 0:
            return Response({"error": "Amount must be greater than zero."}, status=400)

        if target == "savings":
            wallet.savings_balance += amount
            message = f"₵{amount:.2f} deposited into savings."
        else:
            wallet.balance += amount
            message = f"₵{amount:.2f} deposited into wallet."

        wallet.save()
        log_transaction(request.user, "deposit", amount, message)
        return Response({"message": message})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


# ============================================================
# 🔄 TRANSFER WALLET → SAVINGS
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def deposit_to_savings(request):
    try:
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        amount = Decimal(request.data.get("amount", 0))

        if amount <= 0 or wallet.balance < amount:
            return Response({"error": "Insufficient funds."}, status=400)

        wallet.balance -= amount
        wallet.savings_balance += amount
        wallet.save()

        log_transaction(request.user, "transfer", amount, f"₵{amount:.2f} moved to savings.")
        return Response({"message": f"₵{amount:.2f} moved to savings."})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


# ============================================================
# 💸 WITHDRAW SAVINGS → WALLET
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def withdraw_from_savings(request):
    try:
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        amount = Decimal(request.data.get("amount", 0))

        if amount <= 0 or wallet.savings_balance < amount:
            return Response({"error": "Invalid or insufficient savings."}, status=400)

        wallet.savings_balance -= amount
        wallet.balance += amount
        wallet.save()

        log_transaction(request.user, "withdraw", amount, f"₵{amount:.2f} withdrawn from savings.")
        return Response({"message": f"₵{amount:.2f} withdrawn from savings."})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


# ============================================================
# 💳 MAKE CREDIT PURCHASE (BNPL)
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def make_credit_purchase(request):
    """
    BNPL rules:
    - Minimum 20% downpayment
    - Flat 5% interest applied on the financed portion at repayment time
    - 14-day due date
    """
    try:
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        amount = Decimal(request.data.get("amount", 0))
        item_name = request.data.get("item_name", "Store Purchase")
        down_payment = Decimal(request.data.get("down_payment", 0))

        if amount <= 0:
            return Response({"error": "Invalid amount."}, status=400)
        min_down = (amount * Decimal("0.20")).quantize(Decimal("0.01"))
        if down_payment < min_down:
            return Response({"error": f"Down payment must be at least 20% (₵{min_down})."}, status=400)
        if wallet.balance < down_payment:
            return Response({"error": "Insufficient wallet funds for downpayment."}, status=400)

        credit_principal = (amount - down_payment).quantize(Decimal("0.01"))
        if credit_principal <= 0:
            return Response({"error": "Down payment cannot cover full amount for BNPL."}, status=400)

        if wallet.credit_balance + credit_principal > wallet.credit_limit:
            return Response({"error": "Credit limit exceeded."}, status=400)

        wallet.balance -= down_payment
        wallet.credit_balance += credit_principal
        wallet.save()

        due_date = (timezone.now().date() + timedelta(days=14))
        purchase = CreditPurchase.objects.create(
            user=request.user,
            wallet=wallet,
            item_name=item_name,
            total_amount=amount,
            down_payment=down_payment,
            credit_amount=credit_principal,
            remaining_amount=credit_principal,
            interest_rate=Decimal("5.00"),
            due_date=due_date,
            status="ACTIVE",
            is_paid=False,
        )

        log_transaction(request.user, "credit_purchase", credit_principal, f"BNPL principal for {item_name}")
        log_transaction(request.user, "withdraw", down_payment, f"Down payment for {item_name}")

        interest_preview = (credit_principal * Decimal("0.05")).quantize(Decimal("0.01"))
        total_due_preview = (credit_principal + interest_preview).quantize(Decimal("0.01"))

        return Response({
            "message": (
                f"₵{amount:.2f} purchase made. ₵{down_payment:.2f} paid now. "
                f"₵{total_due_preview:.2f} (incl. 5% interest) due by {due_date}."
            ),
            "purchase": {
                "item_name": purchase.item_name,
                "principal": str(credit_principal),
                "interest_preview": str(interest_preview),
                "total_due_preview": str(total_due_preview),
                "due_date": due_date.isoformat(),
            }
        }, status=201)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


# ============================================================
# 💳 REPAY CREDIT (with interest & penalties)
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def repay_credit(request):
    """
    Repayment logic:
    - 5% simple interest calculated on outstanding principal at time of payment
    - +1% penalty per full week overdue (on principal)
    """
    try:
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        amount = Decimal(request.data.get("amount", 0))

        if amount <= 0:
            return Response({"error": "Invalid amount."}, status=400)
        if wallet.balance < amount:
            return Response({"error": "Insufficient wallet funds."}, status=400)

        purchases = CreditPurchase.objects.filter(user=request.user, is_paid=False).order_by("due_date")
        if not purchases.exists():
            return Response({"error": "No active credit purchases to repay."}, status=400)

        remaining_payment = amount
        total_interest_charged = Decimal("0.00")
        total_penalty_charged = Decimal("0.00")
        today = timezone.now().date()

        for purchase in purchases:
            if remaining_payment <= 0:
                break

            principal_due = purchase.remaining_amount
            if principal_due <= 0:
                purchase.is_paid = True
                purchase.status = "PAID"
                purchase.save()
                continue

            interest = (principal_due * Decimal("0.05")).quantize(Decimal("0.01"))
            penalty = Decimal("0.00")

            if today > purchase.due_date:
                weeks_overdue = (today - purchase.due_date).days // 7
                if weeks_overdue > 0:
                    penalty = (principal_due * Decimal("0.01") * weeks_overdue).quantize(Decimal("0.01"))

            total_due_now = (principal_due + interest + penalty).quantize(Decimal("0.01"))

            if remaining_payment >= total_due_now:
                remaining_payment -= total_due_now
                wallet.credit_balance -= principal_due
                purchase.remaining_amount = Decimal("0.00")
                purchase.is_paid = True
                purchase.status = "PAID"
                wallet.credit_score = min(wallet.credit_score + 10, 1000)
            else:
                fraction = (remaining_payment / total_due_now)
                principal_paid = (principal_due * fraction).quantize(Decimal("0.01"))
                purchase.remaining_amount = (principal_due - principal_paid).quantize(Decimal("0.01"))
                wallet.credit_balance -= principal_paid
                remaining_payment = Decimal("0.00")
                wallet.credit_score = min(wallet.credit_score + 3, 1000)

            purchase.save()
            total_interest_charged += interest
            total_penalty_charged += penalty

        wallet.balance -= amount
        wallet.save()

        log_transaction(
            request.user,
            "repay",
            amount,
            f"Credit repayment (interest ₵{total_interest_charged:.2f}, penalty ₵{total_penalty_charged:.2f})"
        )

        return Response({
            "message": f"₵{amount:.2f} repaid successfully!",
            "interest_charged": f"₵{total_interest_charged:.2f}",
            "penalty_charged": f"₵{total_penalty_charged:.2f}",
            "remaining_wallet_balance": f"₵{wallet.balance:.2f}",
            "credit_score": wallet.credit_score
        })
    except Exception as e:
        return Response({"error": str(e)}, status=500)


# ============================================================
# 💳 MOMO PAYMENT INTEGRATION
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def momo_payment_request(request):
    """
    Request payment from user's MoMo wallet.
    Example body:
    {
        "amount": 5,
        "phone": "46733123453"
    }
    """
    try:
        amount = request.data.get("amount")
        phone = request.data.get("phone")

        if not amount or not phone:
            return Response({"error": "Amount and phone are required."}, status=400)

        # ✅ FIXED: generate UUID string for the reference
        reference_id = str(uuid.uuid4())

        result = request_payment(amount, phone, reference_id=reference_id, api_key="85726dae4e4347ca8938faa71eacaa1d")

        if "error" in result:
            return Response(result, status=400)

        return Response({
            "message": "Payment request accepted",
            "reference_id": reference_id,
            "details": result
        }, status=202)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def momo_payment_status(request, reference_id):
    """Check status of a specific MoMo transaction"""
    try:
        result = check_payment_status(reference_id, api_key="85726dae4e4347ca8938faa71eacaa1d")
        return Response(result)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
