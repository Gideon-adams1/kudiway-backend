from django.apps import AppConfig
import cloudinary


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders'

    def ready(self):
        # ✅ Cloudinary manual configuration (runs when app starts)
        cloudinary.config(
            cloud_name="dmpymbirt",
            api_key="356444953374757",
            api_secret="a2Yvr9WNswF28a9K46HUeDV6DTk",
        )
        print("✅ Cloudinary initialized successfully for: dmpymbirt")
