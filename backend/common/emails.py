"""Shared transactional email helpers (Epic 13: Notification Center - Email)."""

from django.conf import settings
from django.core.mail import send_mail


def send_client_welcome_email(user, plain_password):
    """Emails a newly created client their login credentials.

    fail_silently=True matches ForgotPasswordView's existing precedent: a
    broken SMTP config shouldn't block account creation - the account is
    still created and usable, the admin can share credentials manually if
    delivery fails.
    """
    login_url = f'{settings.FRONTEND_URL.rstrip("/")}/login'
    send_mail(
        subject='Your account is ready',
        message=(
            f'Hi {user.get_short_name()},\n\n'
            'An account has been created for you on the platform.\n\n'
            f'Email: {user.email}\n'
            f'Temporary password: {plain_password}\n\n'
            f'Log in here: {login_url}\n\n'
            'You can change your password after logging in.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


def send_notification_email(user, title, message='', url=''):
    """Mirrors an in-app Notification as an email, gated behind
    settings.SEND_NOTIFICATION_EMAILS (default off - see apps.notifications.services.notify).

    fail_silently=True for the same reason as send_client_welcome_email: a broken
    SMTP config must never block the in-app notification the caller already created.
    """
    body = message or title
    if url:
        link = f'{settings.FRONTEND_URL.rstrip("/")}{url if url.startswith("/") else f"/{url}"}'
        body = f'{body}\n\nView it here: {link}'

    send_mail(
        subject=title,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
