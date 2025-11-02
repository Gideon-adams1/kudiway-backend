from django.core.management.base import BaseCommand
from kudiwallet.models import Wallet

class Command(BaseCommand):
    help = "Automatically updates all users’ credit scores (e.g., monthly)."

    def handle(self, *args, **options):
        wallets = Wallet.objects.all()
        for wallet in wallets:
            old_score = wallet.credit_score
            new_score = wallet.update_credit_score()  # uses your model method
            self.stdout.write(
                self.style.SUCCESS(
                    f"{wallet.user.username}: score {old_score} → {new_score}"
                )
            )
        self.stdout.write(self.style.SUCCESS("✅ All credit scores updated!"))
