import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from accounts.models import User
from medicines.models import ActiveIngredient, Medicine, MedicineIngredient
from prescriptions.forms import UploadDocumentForm
from prescriptions.models import DocumentUpload, PrescriptionAuditLog
from prescriptions.services.medicine_extraction import extract_medicine_names
from prescriptions.services.record_intelligence import extract_record_details


class DocumentSecurityTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.owner = User.objects.create_user(username='owner', password='test-password')
        self.other_user = User.objects.create_user(username='other', password='test-password')

    def test_document_download_is_private_to_owner(self):
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Private record',
            file=SimpleUploadedFile('report.txt', b'Private health record'),
        )
        self.client.login(username='other', password='test-password')
        response = self.client.get(f'/prescriptions/{document.pk}/download/')
        self.assertEqual(response.status_code, 404)

    def test_document_owner_can_download_private_attachment(self):
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Private record',
            file=SimpleUploadedFile('report.txt', b'Private health record'),
        )
        self.client.login(username='owner', password='test-password')
        response = self.client.get(f'/prescriptions/{document.pk}/download/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="report.txt"')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(b''.join(response.streaming_content), b'Private health record')
        self.assertTrue(PrescriptionAuditLog.objects.filter(
            document=document,
            actor=self.owner,
            action=PrescriptionAuditLog.ACTION_DOWNLOADED,
        ).exists())

    def test_review_form_is_private_to_document_owner(self):
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Private record',
            file=SimpleUploadedFile('report.txt', b'Private health record'),
        )
        self.client.login(username='other', password='test-password')

        response = self.client.get(f'/prescriptions/{document.pk}/review/')

        self.assertEqual(response.status_code, 404)

    def test_owner_can_review_without_overwriting_ocr_text(self):
        medicine = Medicine.objects.create(
            name='Example medicine',
            active_ingredient='Example ingredient',
            dosage_form='Tablet',
            description='Test catalog entry.',
            slug='example-medicine-review',
        )
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Prescription',
            file=SimpleUploadedFile('prescription.txt', b'Example medicine 10 mg'),
            extracted_text='Example medicine 10 mg',
            extracted_medicines=[{'name': 'Example medicine', 'catalog_medicine': medicine.name}],
        )
        self.client.login(username='owner', password='test-password')
        review_page = self.client.get(f'/prescriptions/{document.pk}/review/')
        self.assertEqual(review_page.status_code, 200)
        self.assertContains(review_page, 'Original OCR text')
        self.assertContains(review_page, 'Do not infer a strength')

        response = self.client.post(
            f'/prescriptions/{document.pk}/review/',
            {
                'medicine-TOTAL_FORMS': '2',
                'medicine-INITIAL_FORMS': '1',
                'medicine-MIN_NUM_FORMS': '0',
                'medicine-MAX_NUM_FORMS': '51',
                'medicine-0-recognized_text': 'Example medicine',
                'medicine-0-catalog_medicine': str(medicine.pk),
                'medicine-0-strength': '10 mg',
                'medicine-0-dosage_instructions': 'as written on original',
                'medicine-0-verification_status': 'patient_confirmed',
            },
        )

        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual(document.extracted_text, 'Example medicine 10 mg')
        self.assertEqual(document.review_status, DocumentUpload.REVIEWED)
        self.assertEqual(document.reviewed_medicines[0]['strength_as_written'], '10 mg')
        self.assertEqual(document.reviewed_medicines[0]['verified_by'], 'patient')
        self.assertEqual(len(document.reviewed_medicines), 1)
        self.assertTrue(PrescriptionAuditLog.objects.filter(
            document=document,
            actor=self.owner,
            action=PrescriptionAuditLog.ACTION_REVIEWED,
        ).exists())

    def test_upload_rejects_unsupported_file_extensions(self):
        upload = SimpleUploadedFile('malware.html', b'<script>alert(1)</script>', content_type='text/html')
        form = UploadDocumentForm(data={'title': 'Unsupported'}, files={'file': upload})
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)

    def test_upload_rejects_files_over_ten_megabytes(self):
        upload = SimpleUploadedFile('large.txt', b'x' * (10 * 1024 * 1024 + 1), content_type='text/plain')
        form = UploadDocumentForm(data={'title': 'Large file'}, files={'file': upload})
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)

    def test_upload_rejects_corrupted_image(self):
        upload = SimpleUploadedFile('broken.png', b'not an image', content_type='image/png')
        form = UploadDocumentForm(
            data={'title': 'Broken image', 'document_type': 'prescription'},
            files={'file': upload},
        )

        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)

    def test_extraction_matches_catalog_medicine_name_without_dosing_advice(self):
        Medicine.objects.create(
            name='Example medicine',
            active_ingredient='Example ingredient',
            dosage_form='Tablet',
            description='Test catalog data only.',
            slug='example-medicine',
        )

        detected = extract_medicine_names(
            'Prescription: EXAMPLE medicine 10 mg. Take as directed by the prescriber.'
        )

        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0]['name'], 'Example medicine')
        self.assertFalse(detected[0]['composition_verified'])

    def test_extraction_matches_catalog_ingredient_and_includes_verified_source(self):
        ingredient = ActiveIngredient.objects.create(
            name='Example ingredient',
            standard_name='Example ingredient',
            source_name='Test source',
            source_url='https://example.test/ingredient',
            last_verified='2026-01-01',
            information_verified=True,
        )
        medicine = Medicine.objects.create(
            name='Example source-backed medicine',
            active_ingredient='Example ingredient',
            dosage_form='Tablet',
            description='Test catalog data.',
            source_name='Test source',
            source_url='https://example.test/medicine',
            last_verified='2026-01-01',
            safety_data_verified=True,
            slug='example-source-backed-medicine',
        )
        MedicineIngredient.objects.create(medicine=medicine, ingredient=ingredient)

        detected = extract_medicine_names('Rx: Example ingredient 5 mg')

        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0]['match_type'], 'active ingredient')
        self.assertTrue(detected[0]['composition_verified'])
        self.assertEqual(detected[0]['source_url'], 'https://example.test/medicine')

    def test_extraction_returns_empty_for_unrecognized_text(self):
        self.assertEqual(extract_medicine_names('Handwritten text was not readable'), [])

    def test_record_intelligence_extracts_candidates_without_interpreting_them(self):
        Medicine.objects.create(
            name='Example medicine',
            active_ingredient='Example ingredient',
            dosage_form='Tablet',
            description='Test catalog entry.',
            slug='example-medicine',
        )

        details = extract_record_details(
            'Date: 2026-10-12\n'
            'Example medicine 10 mg once daily\n'
            'Hemoglobin: 12.5 g/dL (13-16)\n'
            'Diagnosis: Example text from source'
        )

        self.assertEqual(details['medicines'][0]['name'], 'Example medicine')
        self.assertIn('10 mg', details['dosage_mentions'][0]['text'])
        self.assertEqual(details['test_values'][0]['value'], '12.5')
        self.assertEqual(details['test_values'][0]['printed_reference_range'], '13-16')
        self.assertEqual(details['test_values'][0]['range_comparison'], 'below')
        self.assertEqual(details['diagnosis_mentions'][0]['text'], 'Example text from source')
        self.assertEqual(details['dates'], ['2026-10-12'])
        self.assertNotIn('abnormal', str(details).lower())

    def test_upload_saves_and_displays_detected_medicine(self):
        Medicine.objects.create(
            name='Sample medicine',
            active_ingredient='Sample ingredient',
            dosage_form='Tablet',
            description='Test catalog entry.',
            slug='sample-medicine',
        )
        self.client.login(username='owner', password='test-password')

        with self.settings(MEDIA_ROOT=self.media_directory.name):
            response = self.client.post(
                '/prescriptions/upload/',
                {
                    'title': 'Prescription',
                    'document_type': 'prescription',
                    'ocr_language': 'en',
                    'file': SimpleUploadedFile(
                        'prescription.txt',
                        b'Rx: Sample medicine 10 mg',
                        content_type='text/plain',
                    ),
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        document = DocumentUpload.objects.get(user=self.owner, title='Prescription')
        self.assertEqual(document.document_type, DocumentUpload.TYPE_PRESCRIPTION)
        self.assertEqual(document.ocr_language, DocumentUpload.OCR_ENGLISH)
        self.assertEqual(document.extracted_medicines[0]['name'], 'Sample medicine')
        self.assertContains(response, 'Possible medicine names found in readable text')
        self.assertContains(response, 'Sample medicine')
        self.assertContains(response, 'Confirm every name against the original prescription')

    def test_fhir_export_is_authenticated_and_contains_fhir_shaped_reviewable_resources(self):
        self.owner.demo_abha_id = 'DEMO-ABHA-TEST'
        self.owner.save(update_fields=['demo_abha_id'])
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Sample lab report',
            file=SimpleUploadedFile('report.txt', b'Hemoglobin 12.5 g/dL'),
            extracted_details={
                'test_values': [{
                    'name': 'Hemoglobin',
                    'value': '12.5',
                    'unit': 'g/dL',
                    'printed_reference_range': '12-16',
                }],
            },
        )
        url = f'/prescriptions/{document.pk}/fhir.json'
        self.client.login(username='other', password='test-password')
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.login(username='owner', password='test-password')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        bundle = response.json()
        self.assertEqual(bundle['resourceType'], 'Bundle')
        self.assertTrue(all(entry['fullUrl'].startswith('urn:uuid:') for entry in bundle['entry']))
        resources = [entry['resource'] for entry in bundle['entry']]
        self.assertIn('DocumentReference', [resource['resourceType'] for resource in resources])
        patient = next(resource for resource in resources if resource['resourceType'] == 'Patient')
        self.assertEqual(patient['identifier'][0]['value'], 'DEMO-ABHA-TEST')
        observation = next(resource for resource in resources if resource['resourceType'] == 'Observation')
        self.assertEqual(observation['status'], 'preliminary')
        self.assertEqual(observation['referenceRange'][0]['low']['value'], 12.0)

    def test_json_api_is_authenticated_owner_scoped_and_not_cacheable(self):
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Private record',
            file=SimpleUploadedFile('report.txt', b'Private health record'),
        )
        url = f'/prescriptions/{document.pk}/api.json'
        self.client.login(username='other', password='test-password')
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.login(username='owner', password='test-password')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.json()['title'], 'Private record')
