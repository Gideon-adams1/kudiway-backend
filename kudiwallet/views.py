from decimal import Decimal, InvalidOperation
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import Wallet, Transaction, KYC, CreditPurchase
from .serializers import TransactionSerializer, KYCSerializer

# ✅ Import MoMo helper functions
from .momo import request_payment, check_payment_status
import uuid  # ✅ added for MoMo reference ID generation



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
    - Reduces wallet balance and credit_balance; updates credit score
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

            # Interest on current principal
            interest = (principal_due * Decimal("0.05")).quantize(Decimal("0.01"))

            # Penalty if overdue (per full week)
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
# 📦 GET ACTIVE CREDIT PURCHASES
# ============================================================
# ============================================================
# 💳 MAKE CREDIT PURCHASE (BNPL) + OPTIONAL GET SUMMARY
# ============================================================
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def make_credit_purchase(request):
    """
    BNPL rules:
    - Minimum 20% downpayment
    - Flat 5% interest applied on the financed portion at repayment time
    - 14-day due date

    GET  → return active credit purchases (for screen load)
    POST → create a new credit purchase
    """
    # ------------ HANDLE GET (screen loading) ------------
    if request.method == "GET":
        purchases = CreditPurchase.objects.filter(user=request.user, is_paid=False).order_by("due_date")
        today = timezone.now().date()
        results = []
        for p in purchases:
            overdue_days = (today - p.due_date).days
            overdue_weeks = max(0, overdue_days // 7)
            penalty_rate_multiplier = (Decimal("1.00") + (Decimal("0.01") * overdue_weeks))
            total_due_preview = (p.remaining_amount * penalty_rate_multiplier).quantize(Decimal("0.01"))
            results.append({
                "item_name": p.item_name,
                "remaining_amount": str(p.remaining_amount),
                "due_date": p.due_date.isoformat(),
                "overdue_weeks": overdue_weeks,
                "penalty_multiplier": str(penalty_rate_multiplier),
                "total_due_preview": str(total_due_preview),
                "is_paid": p.is_paid,
                "status": p.status,
            })
        return Response(results)

    # ------------ HANDLE POST (create BNPL) ------------
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

        # Deduct down payment and increase credit balance
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

        # Log transactions
        log_transaction(request.user, "credit_purchase", credit_principal, f"BNPL principal for {item_name}")
        log_transaction(request.user, "withdraw", down_payment, f"Down payment for {item_name}")

        # Preview interest
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

    purchases = CreditPurchase.objects.filter(user=request.user, is_paid=False)
    today = timezone.now().date()
    results = []
    for p in purchases:
        overdue_days = (today - p.due_date).days
        overdue_weeks = max(0, overdue_days // 7)
        penalty_rate_multiplier = (Decimal("1.00") + (Decimal("0.01") * overdue_weeks))
        total_due_preview = (p.remaining_amount * penalty_rate_multiplier).quantize(Decimal("0.01"))
        results.append({
            "item_name": p.item_name,
            "remaining_amount": str(p.remaining_amount),
            "due_date": p.due_date.isoformat(),
            "overdue_weeks": overdue_weeks,
            "penalty_multiplier": str(penalty_rate_multiplier),
            "total_due_preview": str(total_due_preview),
            "is_paid": p.is_paid,
            "status": p.status,
        })
    return Response(results)


# ============================================================
# 🧮 GET CREDIT SCORE + LIMIT
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_credit_score(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    return Response({
        "credit_score": wallet.credit_score,
        "credit_limit": str(wallet.credit_limit),
        "credit_balance": str(wallet.credit_balance),
    })


# ============================================================
# 🚀 REQUEST LIMIT INCREASE
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def request_limit_increase(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    if wallet.credit_score < 700:
        return Response(
            {"error": "Credit score too low for limit increase."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    wallet.credit_limit *= Decimal("1.2")
    wallet.save()
    log_transaction(request.user, "limit_increase", 0, f"Credit limit raised to ₵{wallet.credit_limit:.2f}")
    return Response({"message": f"🎉 Credit limit increased to ₵{wallet.credit_limit:.2f}!"}, status=200)


# ============================================================
# 📜 TRANSACTION HISTORY
# ============================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transaction_history(request):
    transactions = Transaction.objects.filter(user=request.user).order_by("-timestamp")[:30]
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data)


# ============================================================
# 🪪 KYC UPLOAD & STATUS
# ============================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_kyc(request):
    try:
        kyc, _ = KYC.objects.get_or_create(user=request.user)
        data = request.data
        kyc.full_name = data.get("full_name", kyc.full_name)
        kyc.id_type = data.get("id_type", kyc.id_type)
        kyc.id_number = data.get("id_number", kyc.id_number)
        for field in ["id_front", "id_back", "selfie"]:
            if field in request.FILES:
                setattr(kyc, field, request.FILES[field])
        kyc.status = "Pending"
        kyc.save()
        return Response({"message": "KYC submitted successfully.", "status": kyc.status})
    except Exception as e:
        return Response({"error": str(e)}, status=400)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_kyc_status(request):
    try:
        kyc = KYC.objects.get(user=request.user)
        serializer = KYCSerializer(kyc)
        return Response(serializer.data)
    except KYC.DoesNotExist:
        return Response({"status": "Not submitted"})


# ============================================================
# 🧑🏽‍💼 ADMIN KYC APPROVAL
# ============================================================
@api_view(["POST"])
@permission_classes([IsAdminUser])
def approve_kyc_admin(request, kyc_id):
    try:
        kyc = KYC.objects.get(id=kyc_id)
        kyc.status = "Approved"
        kyc.reviewed_at = timezone.now()
        kyc.save()
        return Response({"message": f"KYC for {kyc.user.username} approved."})
    except KYC.DoesNotExist:
        return Response({"error": "KYC not found."}, status=404)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def reject_kyc_admin(request, kyc_id):
    try:
        kyc = KYC.objects.get(id=kyc_id)
        kyc.status = "Rejected"
        kyc.remarks = request.data.get("remarks", "")
        kyc.reviewed_at = timezone.now()
        kyc.save()
        return Response({"message": f"KYC for {kyc.user.username} rejected."})
    except KYC.DoesNotExist:
        return Response({"error": "KYC not found."}, status=404)


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

        # ✅ Generate proper UUID reference string
        reference_id = str(uuid.uuid4())

        result = request_payment(amount, phone, reference_id=reference_id, api_key="85726dae4e4347ca8938faa71eacaa1d")

        if "error" in result:
            return Response(result, status=400)
        return Response({
            "message": "Payment request sent successfully.",
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
# ============================================================
# 📲 MOMO PAYMENT CALLBACK (Webhook)
# ============================================================
@api_view(["POST"])
@permission_classes([AllowAny])  # MTN will call this
def momo_callback(request):
    payload = request.data if hasattr(request, "data") else {}
    reference_id = payload.get("reference_id")
    status = payload.get("status")
    amount = payload.get("amount")
    payer = payload.get("payer", {})
    payer_id = payer.get("partyId")

    print(f"📩 MoMo Callback received for {reference_id}: {status}")

    # --- 1) Log the webhook ---
    from .models import MomoCallbackLog, Wallet, Notification
    MomoCallbackLog.objects.create(
        reference_id=reference_id or "",
        status=status or "",
        amount=amount or 0,
        payer_id=payer_id or "",
        raw=payload,
    )

    # --- 2) Credit wallet & log transaction when SUCCESSFUL ---
    if status == "SUCCESSFUL" and amount and payer_id:
        try:
            wallet = Wallet.objects.filter(phone_number=payer_id).first()
            if wallet:
                from decimal import Decimal
                wallet.balance += Decimal(str(amount))
                wallet.save()
                log_transaction(wallet.user, "deposit", Decimal(str(amount)), f"MoMo payment from {payer_id}")

                # 3) Create in-app Notification
                Notification.objects.create(
                    user=wallet.user,
                    title="MoMo Payment Received",
                    body=f"You just received ₵{amount} from {payer_id}.",
                    data={"reference_id": reference_id, "amount": amount, "payer_id": payer_id},
                )

                # 4) Email + SMS (best effort)
                send_email_notification(
                    getattr(wallet.user, "email", None),
                    "MoMo payment received",
                    f"Hi {wallet.user.username},\n\nWe received ₵{amount} from {payer_id}. Your new balance is ₵{wallet.balance}.\n\n— Kudiway"
                )
                # If you set TWILIO_* in settings and wallet.user.profile has e164 phone, call:
                # send_sms_notification(wallet.user.profile.phone_e164, f"Kudiway: Received ₵{amount}. Balance: ₵{wallet.balance}")

                return Response({"message": f"Wallet credited ₵{amount} for {payer_id}"})
            else:
                return Response({"error": f"No wallet found for payer {payer_id}"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    return Response({"message": "Callback received"})

from .models import Notification, MomoCallbackLog
from .serializers import NotificationSerializer
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from .notifier import send_email_notification, send_sms_notification

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    qs = Notification.objects.filter(user=request.user).order_by("-created_at")[:50]
    return Response(NotificationSerializer(qs, many=True).data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ack_notifications(request):
    """
    Body: {"ids": [1,2,3]}
    """
    ids = request.data.get("ids", [])
    if not isinstance(ids, list):
        return Response({"error": "ids must be a list"}, status=400)
    Notification.objects.filter(user=request.user, id__in=ids).update(delivered=True)
    return Response({"message": "Acknowledged"})
