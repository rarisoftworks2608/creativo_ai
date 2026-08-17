from django.contrib import admin

from .models import ClientProfile, Company


class ClientProfileInline(admin.TabularInline):
    model = ClientProfile
    extra = 0
    autocomplete_fields = ['user']


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'industry', 'status', 'client_count', 'created_by', 'created_at']
    list_filter = ['status', 'industry']
    search_fields = ['name', 'industry', 'contact_email']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ClientProfileInline]

    @admin.display(description='Clients')
    def client_count(self, obj):
        return obj.clients.count()


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'designation', 'is_primary_contact', 'created_at']
    list_filter = ['is_primary_contact']
    search_fields = ['user__email', 'company__name']
    autocomplete_fields = ['user', 'company']
