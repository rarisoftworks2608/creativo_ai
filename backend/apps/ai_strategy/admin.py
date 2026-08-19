from django.contrib import admin

from .models import BrandContext, StrategyOutput


@admin.register(BrandContext)
class BrandContextAdmin(admin.ModelAdmin):
    list_display = ['company', 'model_used', 'generated_by', 'updated_at']
    search_fields = ['company__name']
    autocomplete_fields = ['company']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(StrategyOutput)
class StrategyOutputAdmin(admin.ModelAdmin):
    list_display = ['company', 'kind', 'model_used', 'created_by', 'created_at']
    list_filter = ['kind']
    search_fields = ['company__name']
    autocomplete_fields = ['company']
    readonly_fields = ['created_at']
