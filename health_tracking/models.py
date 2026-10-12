from django.conf import settings
from django.db import models


class HealthMeasurement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    blood_pressure = models.CharField(max_length=20, blank=True)
    heart_rate = models.PositiveIntegerField(blank=True, null=True)
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    glucose_mgdl = models.PositiveIntegerField(blank=True, null=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f'{self.user} - {self.date}'
