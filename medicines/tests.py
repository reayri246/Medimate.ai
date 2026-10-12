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
from medicines.safety import compare_medicines, verified_medicines


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
        self.assertContains(response, 'Compare medicines')

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

    def _create_verified_medicine(self, name, slug, ingredients):
        medicine = Medicine.objects.create(
            name=name,
            active_ingredient=', '.join(ingredient.name for ingredient, _ in ingredients),
            dosage_form='Tablet',
            category='demo',
            description='Test-only catalog entry.',
            source_name='Test source',
            source_url='https://example.test/medicine',
            last_verified='2026-01-01',
            safety_data_verified=True,
            slug=slug,
        )
        for ingredient, strength in ingredients:
            MedicineIngredient.objects.create(
                medicine=medicine,
                ingredient=ingredient,
                strength=strength,
                unit='mg',
            )
        return medicine

    def test_duplicate_ingredients_detected_using_verified_standard_name(self):
        paracetamol = ActiveIngredient.objects.create(
            name='Paracetamol',
            standard_name='Paracetamol',
            source_name='Test source',
            source_url='https://example.test/ingredient',
            last_verified='2026-01-01',
            information_verified=True,
        )
        ingredient_a = ActiveIngredient.objects.create(
            name='Combination one ingredient',
            standard_name='Combination one ingredient',
            source_name='Test source',
            source_url='https://example.test/ingredient-a',
            last_verified='2026-01-01',
            information_verified=True,
        )
        ingredient_b = ActiveIngredient.objects.create(
            name='Combination two ingredient',
            standard_name='Combination two ingredient',
            source_name='Test source',
            source_url='https://example.test/ingredient-b',
            last_verified='2026-01-01',
            information_verified=True,
        )
        first = self._create_verified_medicine(
            'Combination one',
            'combination-one',
            [(paracetamol, '325'), (ingredient_a, '10')],
        )
        second = self._create_verified_medicine(
            'Combination two',
            'combination-two',
            [(paracetamol, '325'), (ingredient_b, '10')],
        )

        result = compare_medicines([first, second])

        self.assertEqual(result['duplicate_ingredients'], ['Paracetamol'])
        self.assertIn('consult a pharmacist or doctor', result['duplicate_warning'])

    def test_aliases_are_only_used_when_admin_enters_them(self):
        generic = ActiveIngredient.objects.create(
            name='Example generic',
            standard_name='Example generic',
            aliases='example alternate',
            source_name='Test source',
            source_url='https://example.test/generic',
            last_verified='2026-01-01',
            information_verified=True,
        )
        brand_ingredient = ActiveIngredient.objects.create(
            name='Example alternate',
            standard_name='Example alternate',
            source_name='Test source',
            source_url='https://example.test/alternate',
            last_verified='2026-01-01',
            information_verified=True,
        )
        first = self._create_verified_medicine('Product A', 'product-a', [(generic, '1')])
        second = self._create_verified_medicine('Product B', 'product-b', [(brand_ingredient, '1')])

        result = compare_medicines([first, second])

        self.assertEqual(result['duplicate_ingredients'], ['Example generic'])

    def test_unverified_composition_is_excluded_from_comparison_catalog(self):
        self.assertNotIn(self.medicine, verified_medicines())

    def test_no_duplicate_does_not_claim_medicines_are_safe(self):
        ingredient_a = ActiveIngredient.objects.create(
            name='Test ingredient A',
            standard_name='Test ingredient A',
            source_name='Test source',
            source_url='https://example.test/a',
            last_verified='2026-01-01',
            information_verified=True,
        )
        ingredient_b = ActiveIngredient.objects.create(
            name='Test ingredient B',
            standard_name='Test ingredient B',
            source_name='Test source',
            source_url='https://example.test/b',
            last_verified='2026-01-01',
            information_verified=True,
        )
        first = self._create_verified_medicine('Product A', 'product-a', [(ingredient_a, '1')])
        second = self._create_verified_medicine('Product B', 'product-b', [(ingredient_b, '1')])

        result = compare_medicines([first, second])

        self.assertEqual(result['duplicate_ingredients'], [])
        self.assertIn('does not establish', result['disclaimer'])
        self.assertIn('could not be verified', result['interaction_warnings'][0])

    def test_comparison_page_displays_duplicate_warning(self):
        ingredient = ActiveIngredient.objects.create(
            name='Test shared ingredient',
            standard_name='Test shared ingredient',
            source_name='Test source',
            source_url='https://example.test/shared',
            last_verified='2026-01-01',
            information_verified=True,
        )
        first = self._create_verified_medicine('Product A', 'product-a', [(ingredient, '1')])
        second = self._create_verified_medicine('Product B', 'product-b', [(ingredient, '1')])

        response = self.client.post(
            reverse('medicine_compare'),
            {'medicines': [first.pk, second.pk]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Potential duplicate active ingredient detected')
        self.assertContains(response, 'Test shared ingredient')
        self.assertContains(response, 'This information is educational')

    def test_comparison_requires_two_to_four_medicines(self):
        ingredient = ActiveIngredient.objects.create(
            name='Single product ingredient',
            standard_name='Single product ingredient',
            source_name='Test source',
            source_url='https://example.test/single',
            last_verified='2026-01-01',
            information_verified=True,
        )
        medicine = self._create_verified_medicine(
            'Single product',
            'single-product',
            [(ingredient, '1')],
        )
        response = self.client.post(
            reverse('medicine_compare'),
            {'medicines': [medicine.pk]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select between two and four medicines.')

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
        self.assertEqual(Notification.objects.filter(user=demo_user, title__startswith='Sample ').count(), 3)
        self.assertEqual(MedicalRecord.objects.filter(user=demo_user).count(), 3)

    @override_settings(DEBUG=False)
    def test_demo_seed_command_refuses_production(self):
        with self.assertRaises(CommandError):
            call_command('seed_data')
