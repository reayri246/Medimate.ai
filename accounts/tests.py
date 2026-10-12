from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse


class UserAdminPasswordTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username='site-admin',
            email='admin@example.test',
            password='Initial-admin-password-123!',
        )
        self.patient = get_user_model().objects.create_user(
            username='patient',
            email='patient@example.test',
            password='Initial-patient-password-123!',
            first_name='Patient',
        )
        self.client.force_login(self.admin_user)

    def test_admin_user_change_page_has_password_change_link(self):
        response = self.client.get(reverse('admin:accounts_user_change', args=(self.patient.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('admin:auth_user_password_change', args=(self.patient.pk,)),
        )

    def test_admin_can_change_user_password(self):
        response = self.client.post(
            reverse('admin:auth_user_password_change', args=(self.patient.pk,)),
            {
                'password1': 'A-new-strong-password-458!',
                'password2': 'A-new-strong-password-458!',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.check_password('A-new-strong-password-458!'))
        self.assertFalse(self.patient.check_password('Initial-patient-password-123!'))
