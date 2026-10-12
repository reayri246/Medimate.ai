from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.urls import reverse
from django.utils.html import format_html

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Patient profile', {'fields': ('role', 'phone', 'emergency_contact', 'date_of_birth', 'demo_abha_id')}),
        ('Account metadata', {'fields': ('created_at',)}),
        ('Password management', {'fields': ('password_change_link',)}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ('Patient profile', {'fields': ('role', 'phone', 'emergency_contact', 'date_of_birth', 'demo_abha_id')}),
    )
    readonly_fields = DjangoUserAdmin.readonly_fields + ('created_at', 'password_change_link')
    list_display = DjangoUserAdmin.list_display + ('role',)
    list_filter = DjangoUserAdmin.list_filter + ('role',)

    @admin.display(description='Password')
    def password_change_link(self, obj):
        if obj is None:
            return 'Save the user before setting a password.'
        url = reverse('admin:auth_user_password_change', args=(obj.pk,))
        return format_html('<a href="{}">Change this user\'s password</a>', url)
