from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from appointments.models import AppointmentActivity
from notifications.models import Notification


class AdminPortalTests(TestCase):
    def test_only_superuser_can_view_activity_overview(self):
        staff = User.objects.create_user(
            username='reception',
            password='test-password-123',
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse('portal_home'))

        self.assertEqual(response.status_code, 403)

    def test_admin_sees_recent_appointment_activity_and_management_links(self):
        admin = User.objects.create_superuser(
            username='site-admin',
            email='admin@example.test',
            password='test-password-123',
        )
        AppointmentActivity.objects.create(
            actor=admin,
            description='Administrator added a doctor profile.',
        )
        LogEntry.objects.create(
            user=admin,
            content_type=ContentType.objects.get_for_model(User),
            object_id=str(admin.pk),
            object_repr=admin.username,
            action_flag=CHANGE,
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('portal_home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Administrator added a doctor profile.')
        self.assertContains(response, 'Manage doctors and duty schedule')
        self.assertContains(response, 'Open appointment desk')
        self.assertContains(response, 'Send user notification')

    def test_only_superuser_can_open_notification_composer(self):
        staff = User.objects.create_user(username='front-desk', is_staff=True)
        self.client.force_login(staff)

        response = self.client.get(reverse('admin_send_notification'))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_send_notification_to_one_selected_user(self):
        admin = User.objects.create_superuser(
            username='site-admin',
            email='admin@example.test',
            password='test-password-123',
        )
        patient = User.objects.create_user(username='patient')
        other_patient = User.objects.create_user(username='other-patient')
        self.client.force_login(admin)

        response = self.client.post(reverse('admin_send_notification'), {
            'audience': 'selected',
            'recipients': [patient.pk],
            'title': 'Clinic update',
            'body': 'Your clinic has updated its opening hours.',
            'url': '/appointments/',
        })

        self.assertRedirects(response, reverse('admin_send_notification'))
        self.assertTrue(Notification.objects.filter(
            user=patient,
            title='Clinic update',
            body='Your clinic has updated its opening hours.',
            url='/appointments/',
        ).exists())
        self.assertFalse(Notification.objects.filter(user=other_patient).exists())
        self.assertTrue(LogEntry.objects.filter(
            user=admin,
            action_flag=ADDITION,
            object_repr__contains='Clinic update',
        ).exists())

    def test_admin_can_send_notification_to_multiple_selected_users(self):
        admin = User.objects.create_superuser(
            username='site-admin',
            email='admin@example.test',
            password='test-password-123',
        )
        first_patient = User.objects.create_user(username='first-patient')
        second_patient = User.objects.create_user(username='second-patient')
        unselected_patient = User.objects.create_user(username='unselected-patient')
        self.client.force_login(admin)

        response = self.client.post(reverse('admin_send_notification'), {
            'audience': 'selected',
            'recipients': [first_patient.pk, second_patient.pk],
            'title': 'Clinic update',
            'body': 'The clinic has updated its opening hours.',
            'url': '/appointments/',
        })

        self.assertRedirects(response, reverse('admin_send_notification'))
        self.assertEqual(
            Notification.objects.filter(title='Clinic update').count(),
            2,
        )
        self.assertTrue(Notification.objects.filter(user=first_patient, title='Clinic update').exists())
        self.assertTrue(Notification.objects.filter(user=second_patient, title='Clinic update').exists())
        self.assertFalse(Notification.objects.filter(user=unselected_patient).exists())

    def test_admin_can_send_notification_to_all_active_users(self):
        admin = User.objects.create_superuser(
            username='site-admin',
            email='admin@example.test',
            password='test-password-123',
        )
        patient = User.objects.create_user(username='patient')
        inactive = User.objects.create_user(username='inactive', is_active=False)
        self.client.force_login(admin)

        response = self.client.post(reverse('admin_send_notification'), {
            'audience': 'all',
            'recipients': [],
            'title': 'Service notice',
            'body': 'A general service update.',
            'url': '',
        })

        self.assertRedirects(response, reverse('admin_send_notification'))
        self.assertEqual(
            Notification.objects.filter(title='Service notice').count(),
            2,
        )
        self.assertTrue(Notification.objects.filter(user=admin, title='Service notice').exists())
        self.assertTrue(Notification.objects.filter(user=patient, title='Service notice').exists())
        self.assertFalse(Notification.objects.filter(user=inactive, title='Service notice').exists())

    def test_admin_notification_rejects_external_redirect_url(self):
        admin = User.objects.create_superuser(
            username='site-admin',
            email='admin@example.test',
            password='test-password-123',
        )
        patient = User.objects.create_user(username='patient')
        self.client.force_login(admin)

        response = self.client.post(reverse('admin_send_notification'), {
            'audience': 'selected',
            'recipients': [patient.pk],
            'title': 'Unsafe link',
            'body': 'This should not be sent.',
            'url': '//outside.example/',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Notification.objects.filter(title='Unsafe link').exists())
        self.assertContains(response, 'single slash')
