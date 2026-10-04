from django.contrib import admin

from .models import PublishJob


@admin.register(PublishJob)
class PublishJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'platform', 'post_type', 'status', 'scheduled_at', 'published_at', 'attempts')
    list_filter = ('status', 'platform', 'post_type')
    search_fields = ('company__name', 'caption', 'external_post_id')
    raw_id_fields = ('content_calendar_item', 'social_account', 'created_by')
