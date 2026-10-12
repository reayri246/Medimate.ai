from datetime import timedelta

from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from health_tracking.models import HealthMeasurement
from medical_records.models import MedicalRecord


class SeedPatientReportTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='devashish',
            password='unchanged-test-password',
            first_name='Devashish',
        )

    @override_settings(DEBUG=True)
    def test_adds_idempotent_sample_data_without_overwriting_existing_readings(self):
        today = timezone.localdate()
        existing = HealthMeasurement.objects.create(
            user=self.patient,
            date=today,
            blood_pressure='111/70',
            notes='Patient-entered reading; preserve it.',
        )

        call_command('seed_patient_report', username='devashish')
        call_command('seed_patient_report', username='devashish')

        self.assertEqual(HealthMeasurement.objects.filter(user=self.patient).count(), 30)
        sample_dates = set(
            HealthMeasurement.objects.filter(
                user=self.patient,
                notes__startswith='SAMPLE DATA ONLY',
            ).values_list('date', flat=True)
        )
        self.assertEqual(len(sample_dates), 29)
        self.assertIn(today, sample_dates | {existing.date})
        self.assertIn(today - timedelta(days=29), sample_dates)
        existing.refresh_from_db()
        self.assertEqual(existing.notes, 'Patient-entered reading; preserve it.')
        self.assertEqual(
            MedicalRecord.objects.filter(user=self.patient, title__startswith='SAMPLE ').count(),
            2,
        )
        self.assertTrue(self.patient.check_password('unchanged-test-password'))
        lab_report = MedicalRecord.objects.get(
            user=self.patient,
            title='SAMPLE health report - basic lab panel',
        )
        self.assertIn('SAMPLE DATA ONLY', lab_report.notes)
        self.assertIn('fictional values', lab_report.notes)

    @override_settings(DEBUG=False)
    def test_refuses_to_seed_patient_report_in_production(self):
        with self.assertRaises(CommandError):
            call_command('seed_patient_report', username='devashish')

    @override_settings(DEBUG=True)
    def test_refuses_unknown_username(self):
        with self.assertRaises(CommandError):
            call_command('seed_patient_report', username='unknown-user')
