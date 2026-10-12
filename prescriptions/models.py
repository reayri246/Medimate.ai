from django.conf import settings
from django.db import models


class DocumentUpload(models.Model):
    TYPE_PRESCRIPTION = 'prescription'
    TYPE_LAB = 'lab'
    TYPE_DISCHARGE = 'discharge'
    TYPE_DIAGNOSTIC = 'diagnostic'
    TYPE_OTHER = 'other'
    DOCUMENT_TYPE_CHOICES = [
        (TYPE_PRESCRIPTION, 'Prescription'),
        (TYPE_LAB, 'Lab report'),
        (TYPE_DISCHARGE, 'Discharge summary'),
        (TYPE_DIAGNOSTIC, 'Diagnostic record'),
        (TYPE_OTHER, 'Other medical record'),
    ]
    OCR_ENGLISH = 'en'
    OCR_TELUGU = 'te'
    OCR_LANGUAGE_CHOICES = [
        (OCR_ENGLISH, 'English'),
        (OCR_TELUGU, 'Telugu + English'),
    ]
    REVIEW_PENDING = 'pending'
    REVIEWED = 'reviewed'
    REVIEW_STATUS_CHOICES = [
        (REVIEW_PENDING, 'Pending review'),
        (REVIEWED, 'Patient review complete'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES, default=TYPE_OTHER)
    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    extracted_text = models.TextField(blank=True)
    extracted_medicines = models.JSONField(default=list, blank=True)
    extracted_details = models.JSONField(default=dict, blank=True)
    reviewed_medicines = models.JSONField(default=list, blank=True)
    ocr_language = models.CharField(max_length=2, choices=OCR_LANGUAGE_CHOICES, default=OCR_ENGLISH)
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default=REVIEW_PENDING)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class PrescriptionAuditLog(models.Model):
    ACTION_UPLOADED = 'uploaded'
    ACTION_VIEWED = 'viewed'
    ACTION_REVIEWED = 'patient_reviewed'
    ACTION_DOWNLOADED = 'downloaded'
    ACTION_EXPORTED = 'exported'
    ACTION_SOFT_COPY = 'soft_copy_viewed'
    ACTION_CHOICES = [
        (ACTION_UPLOADED, 'Uploaded'),
        (ACTION_VIEWED, 'Viewed'),
        (ACTION_REVIEWED, 'Patient reviewed'),
        (ACTION_DOWNLOADED, 'Downloaded'),
        (ACTION_EXPORTED, 'FHIR-style export'),
        (ACTION_SOFT_COPY, 'Printable soft copy viewed'),
    ]

    document = models.ForeignKey(DocumentUpload, on_delete=models.CASCADE, related_name='audit_events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.get_action_display()} · document {self.document_id}'
