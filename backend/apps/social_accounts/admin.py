from django.contrib import admin

from .models import SocialAccount


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    """access_token is intentionally excluded everywhere below - it must never
    be surfaced in Django admin, only ever written and used server-side.
    """

    list_display = ['company', 'platform', 'account_name', 'status', 'token_expires_at', 'connected_by', 'created_at']
    list_filter = ['platform', 'status']
    search_fields = ['company__name', 'account_name', 'account_id']
    autocomplete_fields = ['company', 'connected_by']
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'company', 'platform', 'account_name', 'account_id', 'token_expires_at',
        'status', 'notes', 'connected_by', 'created_at', 'updated_at',
    ]
