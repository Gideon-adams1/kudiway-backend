from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Wallet


# ✅ Wallet Summary
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_summary(request):
    """Return wallet + savings balances for the logged-in user"""
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    return Response({
        "username": request.user.username,
        "balance": wallet.balance,
        "savings_balance": wallet.savings_balance
    }, status=status.HTTP_200_OK)


# ✅ New: Deposit (choose wallet or savings)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deposit(request):
    """Deposit new money into wallet or savings"""
    try:
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        amount = request.data.get("amount")
        target = request.data.get("target", "wallet").lower()

        # --- Validate amount ---
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return Response({"error": "Invalid amount."},
                            status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({"error": "Amount must be greater than zero."},
                            status=status.HTTP_400_BAD_REQUEST)

        # --- Deposit logic ---
        if target == "savings":
            wallet.savings_balance += amount
            message = f"₵{amount:.2f} deposited into savings."
        else:
            wallet.balance += amount
            message = f"₵{amount:.2f} deposited into wallet."

        wallet.save()

        return Response({
            "message": message,
            "wallet_balance": wallet.balance,
            "savings_balance": wallet.savings_balance
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ✅ Deposit from Wallet → Savings (Internal Transfer)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deposit_to_savings(request):
    """Move funds from wallet to savings"""
    try:
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        amount = request.data.get("amount")

        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return Response({"error": "Invalid amount."},
                            status=status.HTTP_400_BAD_REQUEST)

        if wallet.balance < amount or amount <= 0:
            return Response({"error": "Insufficient funds or invalid amount."},
                            status=status.HTTP_400_BAD_REQUEST)

        wallet.balance -= amount
        wallet.savings_balance += amount
        wallet.save()

        return Response({
            "message": f"₵{amount:.2f} moved to savings.",
            "wallet_balance": wallet.balance,
            "savings_balance": wallet.savings_balance
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ✅ Withdraw from Savings → Wallet (Internal Transfer)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def withdraw_from_savings(request):
    """Move funds from savings to wallet"""
    try:
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        amount = request.data.get("amount")

        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return Response({"error": "Invalid amount."},
                            status=status.HTTP_400_BAD_REQUEST)

        if wallet.savings_balance < amount or amount <= 0:
            return Response({"error": "Insufficient savings or invalid amount."},
                            status=status.HTTP_400_BAD_REQUEST)

        wallet.savings_balance -= amount
        wallet.balance += amount
        wallet.save()

        return Response({
            "message": f"₵{amount:.2f} withdrawn from savings.",
            "wallet_balance": wallet.balance,
            "savings_balance": wallet.savings_balance
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
