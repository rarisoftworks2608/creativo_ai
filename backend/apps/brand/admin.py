from django.contrib import admin

from .models import BrandAsset, BrandProfile


@admin.register(BrandProfile)
class BrandProfileAdmin(admin.ModelAdmin):
    list_display = ['company', 'created_at', 'updated_at']
    search_fields = ['company__name']
    autocomplete_fields = ['company']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(BrandAsset)
class BrandAssetAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'category', 'uploaded_by', 'created_at']
    list_filter = ['category']
    search_fields = ['name', 'company__name']
    autocomplete_fields = ['company']
    readonly_fields = ['created_at', 'updated_at']
