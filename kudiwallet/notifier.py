# kudiwallet/notifier.py
from django.conf import settings
from django.core.mail import send_mail

# Optional: Twilio SMS (uncomment if you add Twilio creds)
# from twilio.rest import Client

def send_email_notification(to_email: str, subject: str, body: str):
    if not to_email:
        return
    try:
        send_mail(
            subject,
            body,
            getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@kudiway.com"),
            [to_email],
            fail_silently=True,
        )
    except Exception:
        pass

def send_sms_notification(phone_e164: str, body: str):
    """
    phone_e164: +233XXXXXXXXX (E.164 format).
    Add TWILIO_ACCOUNT_SID & TWILIO_AUTH_TOKEN & TWILIO_FROM in settings to enable.
    """
    if not getattr(settings, "TWILIO_ACCOUNT_SID", None):
        return
    try:
        from twilio.rest import Client  # lazy import so library is optional
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            to=phone_e164,
            from_=settings.TWILIO_FROM,
            body=body,
        )
    except Exception:
        pass
