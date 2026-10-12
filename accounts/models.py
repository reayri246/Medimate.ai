from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_PATIENT = 'patient'
    ROLE_ADMIN = 'admin'
    ROLE_CHOICES = [
        (ROLE_PATIENT, 'Patient'),
        (ROLE_ADMIN, 'Administrator'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_PATIENT)
    phone = models.CharField(max_length=30, blank=True, default='')
    emergency_contact = models.CharField(max_length=120, blank=True, default='')
    date_of_birth = models.DateField(null=True, blank=True)
    demo_abha_id = models.CharField(
        max_length=40,
        blank=True,
        help_text='Fictional demo identifier only. This is not an ABHA ID and is not connected to ABDM.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.get_full_name() or self.username
