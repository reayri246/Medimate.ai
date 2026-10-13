from django.test import TestCase
from django.urls import reverse

from medicines.models import ActiveIngredient, Medicine, MedicineIngredient
from .services.retrieval import answer_health_question


class HealthAssistantTests(TestCase):
    def test_answers_general_fever_question_without_diagnosing(self):
        answer = answer_health_question('What general steps can help with a fever?')

        self.assertEqual(answer['kind'], 'general')
        self.assertIn('cannot identify the cause', answer['body'])
        self.assertIn('cannot diagnose disease', answer['disclaimer'])

    def test_detects_emergency_symptom(self):
        answer = answer_health_question('I am having trouble breathing')

        self.assertEqual(answer['kind'], 'emergency')
        self.assertIn('emergency', answer['body'].lower())

    def test_refuses_personal_health_prediction_and_diagnosis(self):
        for question in ('Predict my health', 'What disease do I have?', 'Do I have flu?'):
            with self.subTest(question=question):
                answer = answer_health_question(question)

                self.assertEqual(answer['kind'], 'boundary')
                self.assertIn('cannot be reliably determined', answer['body'])

    def test_does_not_recommend_medicine_for_symptoms(self):
        questions = (
            'What tablet should I take for a cold and fever?',
            'What do I take for cough?',
            'Can I take this medicine?',
        )
        for question in questions:
            with self.subTest(question=question):
                answer = answer_health_question(question)

                self.assertEqual(answer['kind'], 'medicine_boundary')
                self.assertIn('cannot select a medicine', answer['body'])

    def test_unknown_question_does_not_invent_answer(self):
        answer = answer_health_question('Tell me the cure for an unfamiliar condition')

        self.assertEqual(answer['kind'], 'general')
        self.assertIn('did not find a verified answer', answer['body'])
        self.assertEqual(answer['sources'], [])

    def test_local_assistant_answers_common_general_health_topics(self):
        examples = (
            ('How can I support better sleep?', 'consistent sleep and wake schedule'),
            ('What is general information about headaches?', 'Headaches can have many causes'),
            ('What helps prevent dehydration with diarrhea?', 'Vomiting or diarrhea can lead to dehydration'),
            ('What are the general benefits of physical activity?', 'Regular physical activity'),
            ('What is a balanced diet?', 'A varied eating pattern'),
        )
        for question, expected in examples:
            with self.subTest(question=question):
                answer = answer_health_question(question)
                self.assertIn(expected, answer['body'])

    def test_verified_catalog_information_includes_source_and_caution(self):
        ingredient = ActiveIngredient.objects.create(
            name='Example verified ingredient',
            standard_name='Example verified ingredient',
            source_name='Example source',
            source_url='https://example.test/ingredient',
            last_verified='2026-01-01',
            information_verified=True,
        )
        medicine = Medicine.objects.create(
            name='Example verified medicine',
            active_ingredient='Example verified ingredient',
            dosage_form='Tablet',
            category='example',
            description='Source-backed test description.',
            source_name='Example product source',
            source_url='https://example.test/product',
            last_verified='2026-01-01',
            safety_data_verified=True,
            slug='example-verified-medicine',
        )
        MedicineIngredient.objects.create(medicine=medicine, ingredient=ingredient)

        answer = answer_health_question('What is Example verified medicine?')

        self.assertEqual(answer['kind'], 'catalog')
        self.assertEqual(answer['sources'][0]['name'], 'Example product source')
        self.assertTrue(any('does not confirm' in caution for caution in answer['cautions']))

    def test_unverified_catalog_medicine_is_not_returned_as_verified(self):
        Medicine.objects.create(
            name='DEMO unverified medicine',
            active_ingredient='Unverified data',
            dosage_form='Demo',
            description='Not verified.',
            slug='demo-unverified-medicine',
        )

        answer = answer_health_question('What is DEMO unverified medicine?')

        self.assertNotEqual(answer['kind'], 'catalog')

    def test_assistant_page_displays_answer_and_boundaries(self):
        response = self.client.post(
            reverse('assistant_home'),
            {'question': 'What should I know about cold-like symptoms?'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'assistant cannot tell whether symptoms are a cold')
        self.assertContains(response, 'No diagnosis or prescriptions')
        self.assertContains(response, 'assistant-answer-side')
        self.assertContains(response, 'Try asking')

    def test_assistant_page_flags_emergency(self):
        response = self.client.post(
            reverse('assistant_home'),
            {'question': 'I have severe chest pain'},
        )

        self.assertContains(response, 'Seek emergency care now')
