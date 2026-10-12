from django.test import TestCase
from django.urls import reverse

from medicines.models import ActiveIngredient, Medicine, MedicineIngredient

from .services.triage import assess_symptom_urgency


class SymptomGuideTests(TestCase):
    def create_verified_otc_medicine(self):
        ingredient = ActiveIngredient.objects.create(
            name='Verified demo ingredient',
            standard_name='Verified demo ingredient',
            source_name='Test catalog source',
            source_url='https://example.test/ingredient',
            last_verified='2026-01-01',
            information_verified=True,
        )
        medicine = Medicine.objects.create(
            name='Verified demo OTC item',
            active_ingredient=ingredient.name,
            dosage_form='Reference entry',
            strength='Catalog-only',
            category='test',
            description='Test-only catalog record.',
            source_name='Test catalog source',
            source_url='https://example.test/medicine',
            last_verified='2026-01-01',
            safety_data_verified=True,
            is_non_prescription=True,
            slug='verified-demo-otc-item',
        )
        MedicineIngredient.objects.create(
            medicine=medicine,
            ingredient=ingredient,
        )
        return medicine

    def post_symptoms(self, age=35, symptoms='A mild cough', severity='mild'):
        return self.client.post(reverse('guard_home'), {
            'age': age,
            'duration': 'since yesterday',
            'trend': 'same',
            'severity': severity,
            'symptoms': symptoms,
        })

    def test_emergency_symptom_escalates(self):
        result = assess_symptom_urgency('I have chest pain', 35)

        self.assertEqual(result['level'], 'Emergency')
        self.assertIn('emergency', result['recommendation'].lower())

    def test_worsening_symptoms_escalate(self):
        result = assess_symptom_urgency('A mild headache', 35, trend='worsening')

        self.assertEqual(result['level'], 'Urgent')

    def test_severe_symptoms_escalate(self):
        result = assess_symptom_urgency('A headache', 35, severity='severe')

        self.assertEqual(result['level'], 'Urgent')

    def test_young_child_gets_age_appropriate_caution(self):
        result = assess_symptom_urgency('A mild cough', 3)

        self.assertIn('child under 5', result['recommendation'])

    def test_no_diagnosis_or_medicine_recommendation(self):
        result = assess_symptom_urgency('A mild cough', 35)

        self.assertIn('cannot determine the cause', result['recommendation'])
        self.assertIn('does not diagnose or prescribe medicines or doses', result['medicine_guidance'])
        self.assertIn('vaccinations', result['prevention'])

    def test_guide_accepts_symptom_intake_and_returns_guidance(self):
        response = self.client.post(reverse('guard_home'), {
            'age': 35,
            'duration': 'since yesterday',
            'trend': 'same',
            'severity': 'mild',
            'symptoms': 'A mild cough',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No emergency signs recognized')
        self.assertContains(response, 'does not diagnose or prescribe medicines or doses')
        self.assertContains(response, 'Disease prevention')

    def test_symptoms_do_not_recommend_medicines(self):
        response = self.client.post(reverse('guard_home'), {
            'age': 35,
            'duration': 'since yesterday',
            'trend': 'same',
            'severity': 'mild',
            'medications': '',
            'allergies': '',
            'symptoms': 'cold and fever',
        })

        self.assertContains(response, 'Symptoms are not used to select or recommend a medicine')
        self.assertNotContains(response, 'Possible over-the-counter options')

    def test_adult_mild_result_only_shows_verified_otc_catalog_facts(self):
        medicine = self.create_verified_otc_medicine()
        Medicine.objects.create(
            name='Unverified demo medicine',
            active_ingredient='Unverified',
            dosage_form='Unknown',
            description='Not verified.',
            slug='unverified-demo-medicine',
            is_non_prescription=True,
        )

        response = self.post_symptoms()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, medicine.name)
        self.assertContains(response, 'not a recommendation for your symptoms')
        self.assertContains(response, medicine.source_name)
        self.assertNotContains(response, 'Unverified demo medicine')

    def test_minor_or_urgent_result_does_not_show_medicine_catalog_entries(self):
        medicine = self.create_verified_otc_medicine()

        minor_response = self.post_symptoms(age=12, symptoms='cold and fever')
        urgent_response = self.post_symptoms(symptoms='A mild cough', severity='severe')

        self.assertContains(minor_response, 'No medicine suggestions are shown for people under 18')
        self.assertNotContains(minor_response, medicine.name)
        self.assertContains(urgent_response, 'medicine catalog information is not shown')
        self.assertNotContains(urgent_response, medicine.name)
