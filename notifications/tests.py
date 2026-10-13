from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Notification


class NotificationOpenTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='test-password')
        self.other_user = User.objects.create_user(username='other', password='test-password')
        self.notification = Notification.objects.create(
            user=self.owner,
            title='Appointment accepted',
            body='Your consultation has been accepted.',
            url='/appointments/',
        )

    def test_open_marks_notification_read_and_redirects_to_its_local_destination(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('notification_open', args=(self.notification.pk,)))

        self.assertRedirects(response, '/appointments/')
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_open_is_owner_scoped(self):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('notification_open', args=(self.notification.pk,)))

        self.assertEqual(response.status_code, 404)
        self.notification.refresh_from_db()
        self.assertFalse(self.notification.is_read)

    def test_external_destination_falls_back_to_notifications_page(self):
        self.notification.url = 'https://example.com/'
        self.notification.save(update_fields=('url',))
        self.client.force_login(self.owner)

        response = self.client.get(reverse('notification_open', args=(self.notification.pk,)))

        self.assertRedirects(response, reverse('notification_list'))
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)


class NotificationAdminTests(TestCase):
    def test_admin_notification_list_has_send_notifications_action(self):
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.test',
            password='test-password',
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('admin:notifications_notification_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('admin:notifications_notification_send'))

    def test_admin_panel_sends_a_notification_to_multiple_selected_users(self):
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.test',
            password='test-password',
        )
        first_user = User.objects.create_user(username='first')
        second_user = User.objects.create_user(username='second')
        unselected_user = User.objects.create_user(username='unselected')
        self.client.force_login(admin)

        response = self.client.post(reverse('admin:notifications_notification_send'), {
            'audience': 'selected',
            'recipients': [first_user.pk, second_user.pk],
            'title': 'System update',
            'body': 'A service message.',
            'url': '/notifications/',
        })

        self.assertRedirects(response, reverse('admin:notifications_notification_changelist'))
        self.assertEqual(Notification.objects.filter(title='System update').count(), 2)
        self.assertTrue(Notification.objects.filter(user=first_user, title='System update').exists())
        self.assertTrue(Notification.objects.filter(user=second_user, title='System update').exists())
        self.assertFalse(Notification.objects.filter(user=unselected_user).exists())

    def test_admin_notification_sender_rejects_non_admin_staff(self):
        staff = User.objects.create_user(username='staff', is_staff=True)
        self.client.force_login(staff)

        response = self.client.get(reverse('admin:notifications_notification_send'))

        self.assertEqual(response.status_code, 403)
