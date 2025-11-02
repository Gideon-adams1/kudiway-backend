from django.apps import AppConfig

class KudiwalletConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kudiwallet'

    def ready(self):
        """Auto-schedule weekly credit score updates via Django-Q."""
        try:
            from django_q.tasks import schedule
            from django_q.models import Schedule

            # Avoid duplicate scheduling
            if not Schedule.objects.filter(
                func='django.core.management.call_command',
                args='update_credit_scores'
            ).exists():
                schedule(
                    'django.core.management.call_command',
                    'update_credit_scores',
                    schedule_type='W',  # ✅ 'W' = Weekly
                    repeats=-1,         # repeat indefinitely
                )
                print("✅ Scheduled weekly credit score updates successfully.")
        except Exception as e:
            # Avoid crashing if Django-Q or DB not ready
            print(f"⚠️ Django-Q scheduling skipped: {e}")
