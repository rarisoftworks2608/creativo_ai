from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """Platform user. Only two roles exist: Admin (internal team) and Client (business)."""

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        CLIENT = 'client', 'Client'

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CLIENT)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_users',
        help_text='Admin who created this account, if it was created by an admin (e.g. a client login).',
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    def get_full_name(self):
        full_name = f'{self.first_name} {self.last_name}'.strip()
        return full_name or self.email

    def get_short_name(self):
        return self.first_name or self.email

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_client(self):
        return self.role == self.Role.CLIENT


class LoginHistory(models.Model):
    """Audit trail of login attempts, per Epic 01 (Login history) and Epic 24 (Login monitoring)."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='login_history',
        null=True,
        blank=True,
        help_text='Null when the attempt used an email that does not match any account.',
    )
    email_attempted = models.EmailField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    was_successful = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Login history'

    def __str__(self):
        status = 'success' if self.was_successful else 'failed'
        return f'{self.email_attempted} - {status} - {self.created_at:%Y-%m-%d %H:%M}'
