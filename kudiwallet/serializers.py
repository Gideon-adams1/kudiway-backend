from rest_framework import serializers
from .models import Wallet, Transaction, KYC, CreditPurchase


# ✅ Wallet Serializer
class WalletSerializer(serializers.ModelSerializer):
    """Serialize wallet info for the current user."""
    class Meta:
        model = Wallet
        fields = ["id", "balance", "credit_balance", "credit_limit", "credit_score", "created_at"]
        read_only_fields = ["id", "created_at"]


# ✅ Transaction Serializer
class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["id", "transaction_type", "amount", "description", "timestamp"]


# ✅ KYC Serializer
class KYCSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYC
        fields = [
            "id",
            "full_name",
            "id_type",
            "id_number",
            "id_front",
            "id_back",
            "selfie",
            "status",
            "remarks",
            "submitted_at",
            "reviewed_at",
        ]
        read_only_fields = ["status", "remarks", "submitted_at", "reviewed_at"]


# 💳 NEW: Credit Purchase Serializer
class CreditPurchaseSerializer(serializers.ModelSerializer):
    """Serializer for Buy Now Pay Later purchases."""
    total_due = serializers.SerializerMethodField()

    class Meta:
        model = CreditPurchase
        fields = [
            "id",
            "user",
            "wallet",
            "total_amount",
            "down_payment",
            "credit_amount",
            "interest_rate",
            "penalty_rate",
            "due_date",
            "status",
            "total_due",
            "created_at",
        ]
        read_only_fields = ["id", "status", "total_due", "created_at", "user", "wallet"]

    def get_total_due(self, obj):
        """Calculate total amount owed (includes 5% interest and 1% penalty if overdue)."""
        return obj.total_due()
