from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import DocumentUpload, PrescriptionAuditLog


@admin.register(DocumentUpload)
class DocumentUploadAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'user',
        'document_type',
        'review_status',
        'created_at',
        'private_record_link',
    )
    list_filter = ('document_type', 'review_status', 'created_at')
    search_fields = ('title', 'user__username', 'user__email')
    readonly_fields = (
        'user',
        'title',
        'document_type',
        'stored_file_name',
        'extracted_text',
        'extracted_medicines',
        'extracted_details',
        'reviewed_medicines',
        'ocr_language',
        'review_status',
        'reviewed_at',
        'created_at',
    )
    fields = readonly_fields

    @admin.display(description='Private record')
    def private_record_link(self, obj):
        url = reverse('admin_document_detail', args=(obj.pk,))
        return format_html('<a href="{}">View securely</a>', url)

    @admin.display(description='Stored file')
    def stored_file_name(self, obj):
        return obj.file.name

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PrescriptionAuditLog)
class PrescriptionAuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'document', 'actor', 'action')
    list_filter = ('action', 'created_at')
    search_fields = ('document__title', 'actor__username')
    readonly_fields = ('document', 'actor', 'action', 'metadata', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
