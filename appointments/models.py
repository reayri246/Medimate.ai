from datetime import time

from django.conf import settings
from django.db import models


class Doctor(models.Model):
    SPECIALTY_CHOICES = [
        ('general-practice', 'General practice'),
        ('cardiology', 'Cardiology'),
        ('dermatology', 'Dermatology'),
        ('ent', 'Ear, nose and throat (ENT)'),
        ('gastroenterology', 'Gastroenterology'),
        ('gynecology', 'Gynecology'),
        ('neurology', 'Neurology'),
        ('ophthalmology', 'Ophthalmology'),
        ('orthopedics', 'Orthopedics'),
        ('pediatrics', 'Pediatrics'),
        ('psychiatry', 'Psychiatry'),
        ('pulmonology', 'Pulmonology'),
    ]

    name = models.CharField(max_length=200)
    specialty = models.CharField(max_length=40, choices=SPECIALTY_CHOICES)
    qualifications = models.CharField(max_length=200, blank=True)
    treatable_symptoms = models.TextField(
        blank=True,
        help_text='Administrator-maintained symptoms or concerns this doctor consults for, separated by commas or new lines. Used only for local appointment matching, not diagnosis.',
    )
    photo = models.ImageField(
        upload_to='doctor_profiles/',
        blank=True,
        help_text='Optional profile photo shown on patient appointment search.',
    )
    consultation_office = models.CharField(max_length=200)
    reception_email = models.EmailField(blank=True)
    account = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='doctor_profile',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return f'{self.name} — {self.get_specialty_display()}'


class DoctorAvailability(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='availability')
    date = models.DateField()
    is_on_duty = models.BooleanField(default=True)
    start_time = models.TimeField(default=time(9, 0))
    end_time = models.TimeField(default=time(17, 0))

    class Meta:
        ordering = ('date', 'doctor__name')
        constraints = [
            models.UniqueConstraint(fields=('doctor', 'date'), name='unique_doctor_availability_per_day'),
            models.CheckConstraint(condition=models.Q(start_time__lt=models.F('end_time')), name='doctor_date_hours_start_before_end'),
        ]

    def __str__(self):
        state = 'on duty' if self.is_on_duty else 'off duty'
        return f'{self.doctor} — {self.date} ({state})'


class DoctorWorkingDay(models.Model):
    WEEKDAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='working_days')
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField(default=time(9, 0))
    end_time = models.TimeField(default=time(17, 0))

    class Meta:
        ordering = ('weekday',)
        constraints = [
            models.UniqueConstraint(fields=('doctor', 'weekday'), name='unique_doctor_working_weekday'),
            models.CheckConstraint(condition=models.Q(weekday__gte=0, weekday__lte=6), name='doctor_weekday_in_range'),
            models.CheckConstraint(condition=models.Q(start_time__lt=models.F('end_time')), name='doctor_weekday_hours_start_before_end'),
        ]

    def __str__(self):
        return f'{self.doctor} — {self.get_weekday_display()}'


class Appointment(models.Model):
    STATUS_SCHEDULED = 'scheduled'
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    doctor = models.ForeignKey(Doctor, null=True, blank=True, on_delete=models.SET_NULL, related_name='appointments')
    requested_date = models.DateField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    symptoms = models.TextField(blank=True)
    patient_consent = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    notes = models.TextField(blank=True)
    reminder_notified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class AppointmentManagement(Appointment):
    class Meta:
        proxy = True
        verbose_name = 'Appointment management'
        verbose_name_plural = 'Appointment management'


class AppointmentActivity(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='appointment_activity',
    )
    appointment = models.ForeignKey(
        Appointment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='activity',
    )
    doctor = models.ForeignKey(
        Doctor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='activity',
    )
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return self.description
