from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from appointments.models import Appointment
from health_tracking.models import HealthMeasurement
from medical_records.models import MedicalRecord


class CoreViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='patient1', password='secret123', email='patient1@example.com')

    def test_home_page_renders(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your Personal AI Health Copilot')
        self.assertContains(response, 'sidebarNavigation')
        self.assertContains(response, 'Features')

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_user_can_access_dashboard(self):
        self.client.login(username='patient1', password='secret123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Medicine finder')
        self.assertContains(response, 'Symptom checker')
        self.assertContains(response, 'Appointments')
        self.assertNotContains(response, 'Quick links')
        self.assertContains(response, 'Health snapshot')

    def test_dashboard_renders_chart_data_from_user_measurements(self):
        self.client.login(username='patient1', password='secret123')
        HealthMeasurement.objects.create(
            user=self.user,
            date=timezone.localdate(),
            blood_pressure='120/80',
            heart_rate=72,
            weight_kg=68.5,
        )

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'measurement-chart-data')
        self.assertContains(response, '120')
        self.assertContains(response, '72')
        self.assertContains(response, '68.5')

    def test_health_profile_shows_owned_records_and_timeline(self):
        self.user.demo_abha_id = 'DEMO-ABHA-TEST'
        self.user.save(update_fields=['demo_abha_id'])
        HealthMeasurement.objects.create(
            user=self.user,
            date=timezone.localdate(),
            blood_pressure='120/80',
        )
        MedicalRecord.objects.create(
            user=self.user,
            title='Sample lab note',
            record_type='lab',
            notes='Illustrative test record.',
        )
        Appointment.objects.create(
            user=self.user,
            title='Sample clinic appointment',
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        self.client.login(username='patient1', password='secret123')

        response = self.client.get(reverse('health_profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unified health timeline')
        self.assertContains(response, 'DEMO-ABHA-TEST')
        self.assertContains(response, 'not a real ABHA ID')
        self.assertContains(response, 'Sample lab note')
        self.assertContains(response, 'Sample clinic appointment')

    def test_health_check_reports_database_status(self):
        response = self.client.get(reverse('health_check'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_registration_cannot_assign_admin_privileges(self):
        response = self.client.post(
            reverse('register'),
            {
                'username': 'newpatient',
                'email': 'newpatient@example.com',
                'first_name': 'New',
                'last_name': 'Patient',
                'password1': 'Strong-password-915!',
                'password2': 'Strong-password-915!',
                'role': 'admin',
                'is_staff': 'on',
                'is_superuser': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        registered_user = User.objects.get(username='newpatient')
        self.assertEqual(registered_user.role, User.ROLE_PATIENT)
        self.assertFalse(registered_user.is_staff)
        self.assertFalse(registered_user.is_superuser)
