from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from appointments.models import Appointment
from health_tracking.models import HealthMeasurement
from medical_records.models import MedicalRecord
from prescriptions.models import DocumentUpload


class CoreViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='patient1', password='secret123', email='patient1@example.com')

    def test_home_page_renders(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your Personal AI Health Copilot')
        self.assertContains(response, 'sidebarNavigation')
        self.assertContains(response, 'Features')
        self.assertNotContains(response, 'Symptom checker')
        self.assertNotContains(response, 'Safety checker')
        self.assertContains(response, 'ALTRIX LABS')
        self.assertContains(response, 'https://www.altrixlabs.ai/')
        self.assertContains(response, 'Developed by Aura 5')
        self.assertContains(response, reverse('terms'))
        self.assertContains(response, reverse('privacy_policy'))

    def test_terms_page_renders_professional_sections_and_privacy_link(self):
        response = self.client.get(reverse('terms'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Terms &amp; Conditions')
        self.assertContains(response, 'Not medical care or emergency support')
        self.assertContains(response, 'Limitation of responsibility')
        self.assertContains(response, reverse('privacy_policy'))
        self.assertContains(response, 'site-footer-legal')

    def test_privacy_policy_page_explains_health_data_and_access(self):
        response = self.client.get(reverse('privacy_policy'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Privacy Policy')
        self.assertContains(response, 'Health information')
        self.assertContains(response, 'Authorized administrators')
        self.assertContains(response, 'Retention and your choices')
        self.assertContains(response, 'site-footer-legal')

    def test_aura_five_team_page_shows_all_supplied_member_details(self):
        response = self.client.get(reverse('team'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aura 5')
        for name, role, roll_number in (
            ('Pranathi', 'Co-lead', '24D01A66u3'),
            ('Bhavani', 'Team partner', '24D01A66u4'),
            ('Ashmitha', 'Team partner', '24D01A66R5'),
            ('Mohammad Rehan', 'Team partner', '24D01A66T6'),
            ('Devashish', 'Team partner', '24D01A66T4'),
        ):
            with self.subTest(name=name):
                self.assertContains(response, name)
                self.assertContains(response, role)
                self.assertContains(response, roll_number)

    def test_unread_notification_count_is_available_in_topbar_across_pages(self):
        from notifications.models import Notification

        Notification.objects.create(
            user=self.user,
            title='Appointment accepted',
            body='Your appointment letter is ready.',
            url='/appointments/',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('notification_list'))

        self.assertContains(response, 'notification-dot')
        self.assertContains(response, 'You have 1 new notification')

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_user_can_access_dashboard(self):
        self.client.login(username='patient1', password='secret123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Medicine finder')
        self.assertContains(response, 'Health assistant')
        self.assertNotContains(response, 'Symptom checker')
        self.assertNotContains(response, 'Safety checker')
        self.assertContains(response, 'Appointments')
        self.assertNotContains(response, 'Quick links')
        self.assertContains(response, 'Health snapshot')

    def test_checker_routes_are_removed(self):
        self.assertEqual(self.client.get('/guard/').status_code, 404)
        self.assertEqual(self.client.get('/medicines/compare/').status_code, 404)

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
        DocumentUpload.objects.create(
            user=self.user,
            title='Sample blood report',
            file='documents/sample-report.txt',
            extracted_medicines=[{'name': 'Example medicine'}],
            extracted_details={
                'test_values': [{
                    'name': 'Hemoglobin',
                    'value': '10',
                    'unit': 'g/dL',
                }],
                'diagnosis_mentions': [{
                    'label': 'Impression',
                    'text': 'Example source wording',
                }],
                'dates': ['2026-10-13'],
            },
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
        self.assertContains(response, 'health-timeline-item')
        self.assertContains(response, 'DEMO-ABHA-TEST')
        self.assertContains(response, 'not a real ABHA ID')
        self.assertContains(response, 'Sample lab note')
        self.assertContains(response, 'Sample clinic appointment')
        self.assertContains(response, 'Medicines: Example medicine')
        self.assertContains(response, 'Hemoglobin: 10 g/dL')
        self.assertContains(response, 'Example source wording')

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
