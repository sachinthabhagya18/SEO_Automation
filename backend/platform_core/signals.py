from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import AuditEvent

@receiver(user_logged_in)
def login_event(sender, request, user, **kwargs):
    AuditEvent.objects.create(actor=user, action='login.success')

@receiver(user_logged_out)
def logout_event(sender, request, user, **kwargs):
    AuditEvent.objects.create(actor=user, action='logout')

@receiver(user_login_failed)
def failed_event(sender, credentials, request, **kwargs):
    # Deliberately store neither credentials nor untrusted usernames.
    AuditEvent.objects.create(action='login.failed')
