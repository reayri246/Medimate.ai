from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment
from notifications.models import Notification


class Command(BaseCommand):
    help = 'Create one in-app reminder for each confirmed appointment within the next day.'

    def handle(self, *args, **options):
        now = timezone.now()
        cutoff = now + timedelta(hours=24)
        due_ids = list(
            Appointment.objects.filter(
                status__in=(Appointment.STATUS_ACCEPTED, Appointment.STATUS_SCHEDULED),
                scheduled_at__gt=now,
                scheduled_at__lte=cutoff,
                reminder_notified_at__isnull=True,
            ).values_list('pk', flat=True)
        )

        reminders_created = 0
        for appointment_id in due_ids:
            with transaction.atomic():
                appointment = Appointment.objects.select_for_update().select_related(
                    'user',
                    'doctor',
                ).filter(
                    pk=appointment_id,
                    status__in=(Appointment.STATUS_ACCEPTED, Appointment.STATUS_SCHEDULED),
                    scheduled_at__gt=now,
                    scheduled_at__lte=cutoff,
                    reminder_notified_at__isnull=True,
                ).first()
                if appointment is None:
                    continue

                doctor_name = appointment.doctor.name if appointment.doctor else 'your clinic'
                Notification.objects.create(
                    user=appointment.user,
                    title='Appointment reminder',
                    body=(
                        f'Reminder: your appointment with {doctor_name} is scheduled for '
                        f'{timezone.localtime(appointment.scheduled_at):%B %d, %Y at %I:%M %p}.'
                    ),
                    url=reverse('appointment_letter', args=(appointment.pk,)),
                )
                appointment.reminder_notified_at = now
                appointment.save(update_fields=('reminder_notified_at',))
                reminders_created += 1

        self.stdout.write(self.style.SUCCESS(f'Created {reminders_created} appointment reminder(s).'))
