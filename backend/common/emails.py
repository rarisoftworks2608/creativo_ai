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
