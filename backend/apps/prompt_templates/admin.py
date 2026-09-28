from django.contrib import admin

from .models import PromptTemplate


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'category', 'version', 'is_active', 'platform', 'creative_type', 'created_at']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'slug', 'body']
    autocomplete_fields = ['created_by']
    readonly_fields = ['created_at', 'updated_at']
