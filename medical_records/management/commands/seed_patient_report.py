from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from health_tracking.models import HealthMeasurement
from medical_records.models import MedicalRecord


class Command(BaseCommand):
    help = 'Add clearly labeled sample health-report data for an existing patient.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            required=True,
            help='Username of the existing patient account to receive sample data.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Sample patient reports may only be seeded when DEBUG=True.')

        username = options['username']
        try:
            patient = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f'No existing user was found with username "{username}".') from exc

        sample_date = timezone.localdate()
        measurements = []
        for days_ago in range(30):
            measurements.append((
                days_ago,
                f'{68.4 + (days_ago % 7) * 0.1:.1f}',
                f'{118 + days_ago % 5}/{76 + days_ago % 4}',
                70 + days_ago % 8,
                f'{36.6 + (days_ago % 4) * 0.1:.1f}',
                92 + days_ago % 8,
            ))
        created_measurements = 0
        for days_ago, weight, blood_pressure, heart_rate, temperature, glucose in measurements:
            _, created = HealthMeasurement.objects.get_or_create(
                user=patient,
                date=sample_date - timedelta(days=days_ago),
                defaults={
                    'weight_kg': weight,
                    'blood_pressure': blood_pressure,
                    'heart_rate': heart_rate,
                    'temperature_c': temperature,
                    'glucose_mgdl': glucose,
                    'notes': 'SAMPLE DATA ONLY. Not a real patient measurement.',
                },
            )
            created_measurements += int(created)

        records = [
            (
                'SAMPLE health report - basic lab panel',
                'lab',
                (
                    'SAMPLE DATA ONLY — fictional values for demonstrating the health-record page. '
                    'These are not Devashish’s real test results and must not be used for medical decisions.\n\n'
                    f'Sample collection date: {sample_date:%Y-%m-%d}\n'
                    'Hemoglobin: 14.0 g/dL (illustrative report range: 12.0-16.0 g/dL)\n'
                    'Fasting glucose: 92 mg/dL (illustrative report range: 70-99 mg/dL)\n'
                    'Total cholesterol: 178 mg/dL (illustrative report range: 125-200 mg/dL)\n'
                    'Creatinine: 0.9 mg/dL (illustrative report range: 0.6-1.2 mg/dL)\n\n'
                    'Ranges are fictional examples and vary by laboratory and person. '
                    'No diagnosis or clinical interpretation is provided.'
                ),
            ),
            (
                'SAMPLE wellness measurements summary',
                'summary',
                (
                    'SAMPLE DATA ONLY — the following entries are generated for UI demonstration, '
                    'not from a real examination. Seven illustrative daily readings were added to '
                    'Health Tracking. Replace or delete them before using the account with real data.'
                ),
            ),
        ]
        created_records = 0
        for title, record_type, notes in records:
            _, created = MedicalRecord.objects.get_or_create(
                user=patient,
                title=title,
                defaults={'record_type': record_type, 'notes': notes},
            )
            created_records += int(created)

        self.stdout.write(self.style.SUCCESS(
            f'Added sample report data for {patient.username}: '
            f'{created_measurements} new measurements covering the last 30 days and '
            f'{created_records} new medical records. '
            'Existing measurements and account credentials were left unchanged.'
        ))
