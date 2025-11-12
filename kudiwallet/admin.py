from django.contrib import admin
from .models import Wallet, Transaction, KYC

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "savings_balance", "credit_balance", "created_at")
    search_fields = ("user__username",)

# ✅ Enhanced KYC admin with approve/reject actions
@admin.register(KYC)
class KYCAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "id_type", "id_number", "status", "submitted_at")
    list_filter = ("status",)
    search_fields = ("user__username", "full_name", "id_number")

    actions = ["approve_kyc", "reject_kyc"]

    def approve_kyc(self, request, queryset):
        updated = queryset.update(status="Approved")
        self.message_user(request, f"{updated} KYC record(s) marked as Approved ✅")

    approve_kyc.short_description = "Approve selected KYC submissions"

    def reject_kyc(self, request, queryset):
        updated = queryset.update(status="Rejected")
        self.message_user(request, f"{updated} KYC record(s) marked as Rejected ❌")

    reject_kyc.short_description = "Reject selected KYC submissions"
from django.contrib import admin
from .models import MomoCallbackLog

@admin.register(MomoCallbackLog)
class MomoCallbackLogAdmin(admin.ModelAdmin):
    list_display = ("reference_id", "status", "amount", "payer_id", "created_at")
    search_fields = ("reference_id", "payer_id", "status")
    list_filter = ("status", "created_at")
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "transaction_type", "amount", "description", "timestamp")
    list_filter = ("transaction_type", "timestamp")
    search_fields = ("user__username", "description")
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "created_at", "delivered")
    search_fields = ("user__username", "title", "body")
    list_filter = ("delivered", "created_at")
