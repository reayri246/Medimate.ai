from django.conf import settings
from django.db import models


class MedicalRecord(models.Model):
    RECORD_TYPES = [
        ('lab', 'Lab report'),
        ('visit', 'Clinic visit'),
        ('notes', 'Care notes'),
        ('summary', 'Medical summary'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES, default='notes')
    notes = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
