from django.test import TestCase
from django.core.management import call_command, CommandError
from django.test import override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from appointments.models import Appointment
from health_tracking.models import HealthMeasurement
from medical_records.models import MedicalRecord
from medicines.models import ActiveIngredient, Medicine, MedicineIngredient
from notifications.models import Notification
from medicines.catalog import verified_medicines


class MedicineViewsTests(TestCase):
    def setUp(self):
        self.medicine = Medicine.objects.create(
            name='Paracetamol',
            active_ingredient='Acetaminophen',
            dosage_form='Tablet',
            strength='500 mg',
            category='pain-relief',
            description='Common pain and fever medicine.',
            warnings='Do not exceed the recommended dose.',
            side_effects='Nausea, dizziness',
            interactions='Avoid mixing with other products containing acetaminophen.',
            contraindications='Avoid liver disease or severe allergy.',
            slug='paracetamol',
        )

    def test_medicine_list_page_renders(self):
        response = self.client.get(reverse('medicine_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Paracetamol')
        self.assertContains(response, 'medicine-result-card')
        self.assertNotContains(response, 'Compare medicines')

    def test_medicine_search_finds_standardized_ingredient(self):
        ingredient = ActiveIngredient.objects.create(
            name='Searchable ingredient',
            standard_name='Searchable ingredient',
        )
        MedicineIngredient.objects.create(medicine=self.medicine, ingredient=ingredient)

        response = self.client.get(reverse('medicine_list'), {'query': 'Searchable ingredient'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Paracetamol')

    def test_medicine_detail_page_renders(self):
        response = self.client.get(reverse('medicine_detail', args=['paracetamol']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Paracetamol')

    def test_staff_can_manage_medicine_catalog_in_admin(self):
        admin_user = get_user_model().objects.create_superuser(
            username='catalog-admin',
            email='admin@example.test',
            password='test-password-123',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:medicines_medicine_add'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Active ingredient')
        self.assertContains(response, 'Safety data verified')
        self.assertContains(response, 'Source name')
        self.assertContains(response, 'Medicine ingredients')

    def test_unverified_composition_is_excluded_from_verified_catalog(self):
        self.assertNotIn(self.medicine, verified_medicines())

    @override_settings(DEBUG=True)
    def test_seed_command_adds_unverified_demo_medicines_idempotently(self):
        call_command('seed_data')
        call_command('seed_data')

        demo_medicines = Medicine.objects.filter(category='demo-unverified')
        self.assertEqual(demo_medicines.count(), 3)
        self.assertFalse(any(medicine.safety_data_verified for medicine in demo_medicines))
        self.assertFalse(any(medicine.ingredients.exists() for medicine in demo_medicines))
        self.assertTrue(all(medicine.name.startswith('DEMO - ') for medicine in demo_medicines))
        demo_user = get_user_model().objects.get(username='demo_patient')
        self.assertEqual(demo_user.first_name, 'Devashish')
        self.assertTrue(demo_user.check_password('demo12345'))
        self.assertEqual(HealthMeasurement.objects.filter(user=demo_user).count(), 7)
        self.assertEqual(Appointment.objects.filter(user=demo_user).count(), 3)
        self.assertEqual(Notification.objects.filter(user=demo_user, title__startswith='Sample ').count(), 5)
        self.assertEqual(MedicalRecord.objects.filter(user=demo_user).count(), 3)

    @override_settings(DEBUG=False)
    def test_demo_seed_command_refuses_production(self):
        with self.assertRaises(CommandError):
            call_command('seed_data')
