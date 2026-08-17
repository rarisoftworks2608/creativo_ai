from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import LoginHistory, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ['-created_at']
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff', 'created_at']
    list_filter = ['role', 'is_active', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name', 'phone_number']
    readonly_fields = ['created_at', 'updated_at', 'last_login']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Role & status', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'created_by')}),
        ('Permissions', {'fields': ('groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'is_staff', 'is_superuser'),
        }),
    )


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ['email_attempted', 'user', 'was_successful', 'ip_address', 'created_at']
    list_filter = ['was_successful', 'created_at']
    search_fields = ['email_attempted', 'ip_address']
    readonly_fields = [f.name for f in LoginHistory._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
