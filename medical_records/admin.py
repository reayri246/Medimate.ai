from django.contrib import admin

from .models import MedicalRecord


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'record_type', 'created_at')
    list_filter = ('record_type', 'created_at')
    search_fields = ('title', 'user__username', 'user__email')
    readonly_fields = ('user', 'title', 'record_type', 'notes', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
