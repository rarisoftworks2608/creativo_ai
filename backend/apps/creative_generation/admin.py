from django.contrib import admin

from .models import GenerationRequest, GenerationVariation


class GenerationVariationInline(admin.TabularInline):
    model = GenerationVariation
    extra = 0
    readonly_fields = ['variation_number', 'image', 'caption', 'headline', 'is_selected', 'created_at']


@admin.register(GenerationRequest)
class GenerationRequestAdmin(admin.ModelAdmin):
    list_display = ['company', 'creative_type', 'status', 'retry_count', 'model_used', 'cost_usd', 'created_at']
    list_filter = ['status', 'creative_type']
    search_fields = ['company__name']
    autocomplete_fields = ['company', 'content_calendar_item']
    readonly_fields = ['created_at', 'updated_at', 'celery_task_id']
    inlines = [GenerationVariationInline]
