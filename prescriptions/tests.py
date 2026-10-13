from io import BytesIO
import json
import tempfile
from unittest import skip
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
import pymupdf

from accounts.models import User
from medicines.models import ActiveIngredient, Medicine, MedicineIngredient
from prescriptions.forms import UploadDocumentForm
from prescriptions.models import DocumentUpload, PrescriptionAuditLog
from prescriptions.services.medicine_extraction import extract_medicine_names
from prescriptions.services.ocr_formatting import format_ocr_points
from prescriptions.services.lab_explanations import (
    MEDLINEPLUS_LAB_TESTS_URL,
    explain_lab_test,
)
from prescriptions.services.record_intelligence import (
    build_prescription_soft_copy,
    extract_record_details,
)
from prescriptions.services.ocr import extract_text_from_uploaded_file


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

    def test_record_intelligence_extracts_additional_common_lab_results(self):
        details = extract_record_details(
            'eGFR: 72 mL/min\n'
            'ALT: 45 U/L\n'
            'Vitamin D: 22 ng/mL\n'
            'CRP: 4 mg/L'
        )

        self.assertEqual(
            [(item['name'].casefold(), item['value']) for item in details['test_values']],
            [('egfr', '72'), ('alt', '45'), ('vitamin d', '22'), ('crp', '4')],
        )
        self.assertIn('kidneys filter blood', explain_lab_test(details['test_values'][0])['what_it_measures'])
        self.assertIn('enzyme', explain_lab_test(details['test_values'][1])['what_it_measures'])

    def test_lab_explanations_are_source_linked_and_only_add_associations_outside_range(self):
        below_range = explain_lab_test({
            'name': 'Hemoglobin',
            'range_comparison': 'below',
        })
        within_range = explain_lab_test({
            'name': 'Hb',
            'range_comparison': 'within',
        })

        self.assertIn('carries oxygen', below_range['what_it_measures'])
        self.assertIn('anemia', below_range['out_of_range_context'])
        self.assertEqual(below_range['source_url'], MEDLINEPLUS_LAB_TESTS_URL)
        self.assertNotIn('out_of_range_context', within_range)
        self.assertEqual(explain_lab_test({'name': 'Unsupported test'}), {})

    def test_existing_report_summaries_show_general_context_without_changing_saved_data(self):
        test_values = [{
            'name': 'Creatinine',
            'value': '1.8',
            'unit': 'mg/dL',
            'printed_reference_range': '0.6-1.2',
            'range_comparison': 'above',
            'source_text': 'Creatinine 1.8 mg/dL',
        }]
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Sample lab report',
            file=SimpleUploadedFile('lab-report.txt', b'Creatinine 1.8 mg/dL'),
            extracted_details={'test_values': test_values},
        )
        self.client.login(username='owner', password='test-password')

        detail_response = self.client.get(reverse('document_text', args=(document.pk,)))
        list_response = self.client.get(reverse('prescription_list'))

        for response in (detail_response, list_response):
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Possible general associations')
            self.assertContains(response, 'MedlinePlus (U.S. National Library of Medicine)')
            self.assertContains(response, MEDLINEPLUS_LAB_TESTS_URL)

        document.refresh_from_db()
        self.assertEqual(document.extracted_details, {'test_values': test_values})

    def test_soft_copy_extracts_only_explicit_quantity_and_verbatim_dosage_line(self):
        Medicine.objects.create(
            name='Example medicine',
            active_ingredient='Example ingredient',
            dosage_form='Tablet',
            description='Test catalog entry.',
            slug='example-medicine-soft-copy',
        )
        document = DocumentUpload(
            user=self.owner,
            title='Prescription sample',
            file='documents/sample.txt',
            document_type=DocumentUpload.TYPE_PRESCRIPTION,
            extracted_text='Example medicine 250 mg — Qty: 10 tablets; take as written',
        )
        document.extracted_details = extract_record_details(document.extracted_text)

        soft_copy = build_prescription_soft_copy(document)

        self.assertEqual(len(soft_copy['items']), 1)
        item = soft_copy['items'][0]
        self.assertEqual(item['quantity_as_written'], '10')
        self.assertEqual(item['strength_mentions'], ['250 mg'])
        self.assertIn('take as written', item['dosage_instructions_as_written'])
        self.assertEqual(item['composition'], [])
        self.assertIn('not a new prescription', soft_copy['limitations'])

    def test_soft_copy_view_is_owner_scoped_and_private(self):
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Prescription',
            file=SimpleUploadedFile('prescription.txt', b'No readable text'),
            document_type=DocumentUpload.TYPE_PRESCRIPTION,
        )
        url = f'/prescriptions/{document.pk}/soft-copy/'
        self.client.login(username='other', password='test-password')
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.login(username='owner', password='test-password')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertContains(response, 'Print / Save as PDF')
        self.assertContains(response, 'No readable text was extracted.')
        self.assertTrue(PrescriptionAuditLog.objects.filter(
            document=document,
            actor=self.owner,
            action=PrescriptionAuditLog.ACTION_SOFT_COPY,
        ).exists())

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
        self.assertContains(response, 'Extracted text')
        self.assertContains(response, 'Sample medicine')
        self.assertContains(response, 'verify the name against the original')

    def test_image_or_pdf_upload_shows_original_and_full_extracted_text_immediately(self):
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text((72, 72), 'Laboratory report Hemoglobin 12.5 g/dL')
        pdf_data = pdf.tobytes()
        pdf.close()
        self.client.login(username='owner', password='test-password')

        with self.settings(MEDIA_ROOT=self.media_directory.name), patch(
            'prescriptions.views.extract_text_from_uploaded_file',
            return_value='[PDF page 1 - embedded text]\nHemoglobin 12.5 g/dL\nReference interval: 12-16 g/dL',
        ):
            response = self.client.post(
                '/prescriptions/upload/',
                {
                    'title': 'Lab report',
                    'document_type': DocumentUpload.TYPE_LAB,
                    'ocr_language': 'en',
                    'file': SimpleUploadedFile(
                        'lab-report.pdf',
                        pdf_data,
                        content_type='application/pdf',
                    ),
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        document = DocumentUpload.objects.get(user=self.owner, title='Lab report')
        self.assertEqual(response.request['PATH_INFO'], f'/prescriptions/{document.pk}/text/')
        self.assertContains(response, 'Hemoglobin 12.5 g/dL')
        self.assertContains(response, 'Reference interval: 12-16 g/dL')
        self.assertContains(response, 'Original PDF')
        self.assertContains(response, 'processed locally')

    def test_external_document_analysis_route_is_disabled(self):
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Local-only record',
            file=SimpleUploadedFile('report.txt', b'Local document contents'),
        )
        response = self.client.get(f'/prescriptions/{document.pk}/ai-analysis/')
        self.assertEqual(response.status_code, 404)

    def test_image_preview_is_owner_scoped_private_and_converted_to_jpeg(self):
        image_buffer = BytesIO()
        Image.new('RGB', (80, 60), color='white').save(image_buffer, format='PNG')
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Image report',
            document_type=DocumentUpload.TYPE_LAB,
            file=SimpleUploadedFile('report.png', image_buffer.getvalue(), content_type='image/png'),
            extracted_text='Detected report text',
        )
        url = f'/prescriptions/{document.pk}/image-preview/'
        self.client.login(username='other', password='test-password')
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.login(username='owner', password='test-password')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertIn(b'\xff\xd8', response.getvalue()[:3])

    def test_document_text_page_is_authenticated_owner_scoped_and_uncached(self):
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Report text',
            file=SimpleUploadedFile('report.txt', b'Result 12.5 g/dL'),
            extracted_text='Complete extracted report text\nResult 12.5 g/dL',
        )
        url = f'/prescriptions/{document.pk}/text/'
        self.client.login(username='other', password='test-password')
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.login(username='owner', password='test-password')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertContains(response, 'Complete extracted report text')
        self.assertContains(response, 'View original raw OCR text')

    def test_document_text_page_shows_extracted_core_fields_in_one_review_summary(self):
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Complete sample report',
            file=SimpleUploadedFile('report.txt', b'Sample extracted details'),
            extracted_text='Sample extracted details',
            extracted_medicines=[{
                'name': 'Example medicine',
                'match_type': 'medicine',
            }],
            extracted_details={
                'dosage_mentions': [{'medicine': 'example medicine', 'text': 'Example medicine 5 mg daily'}],
                'prescription_items': [{
                    'recognized_text': 'Example medicine',
                    'strength_mentions': ['5 mg'],
                    'quantity_as_written': '10',
                    'dosage_instructions_as_written': 'Example medicine 5 mg daily',
                }],
                'test_values': [{
                    'name': 'Hemoglobin',
                    'value': '10',
                    'unit': 'g/dL',
                    'printed_reference_range': '12-16',
                    'range_comparison': 'below',
                    'source_text': 'Hemoglobin 10 g/dL (12-16)',
                }],
                'diagnosis_mentions': [{'label': 'Diagnosis', 'text': 'Example source wording'}],
                'dates': ['2026-10-13'],
            },
        )
        self.client.login(username='owner', password='test-password')

        response = self.client.get(reverse('document_text', args=(document.pk,)))

        self.assertEqual(response.status_code, 200)
        for content in (
            'Extracted record summary',
            'Example medicine',
            'Strength and directions as read',
            'Quantity as written: 10',
            'Example medicine 5 mg daily',
            'Hemoglobin: 10 g/dL',
            'Possible general associations',
            'Example source wording',
            '2026-10-13',
            'Needs your review',
            'not an AI-generated clinical interpretation',
        ):
            with self.subTest(content=content):
                self.assertContains(response, content)
        document.refresh_from_db()
        self.assertEqual(document.extracted_medicines[0]['name'], 'Example medicine')

        document.review_status = DocumentUpload.REVIEWED
        document.save(update_fields=['review_status'])
        reviewed_response = self.client.get(reverse('document_text', args=(document.pk,)))
        self.assertContains(reviewed_response, 'Patient review complete')
        self.assertNotContains(reviewed_response, 'Needs your review')
        self.assertContains(reviewed_response, 'Patient review is not clinician verification')

    def test_ocr_text_is_rendered_as_readable_points_without_changing_raw_text(self):
        raw_text = (
            '[OCR text; verify against the original]\n'
            'MEDINOVA FIRST AID CENTER. Morning 10:30 AM to 3:00 PM; '
            'Evening 4:30 PM to 10:30 PM. Name: Patient A. Age & Sex: 24/F.'
        )
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Noisy OCR',
            file=SimpleUploadedFile('prescription.txt', raw_text.encode()),
            extracted_text=raw_text,
        )
        self.client.login(username='owner', password='test-password')

        response = self.client.get(f'/prescriptions/{document.pk}/text/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<ul', html=False)
        self.assertContains(response, 'MEDINOVA FIRST AID CENTER')
        self.assertContains(response, 'Morning 10:30 AM to 3:00 PM')
        self.assertContains(response, 'Evening 4:30 PM to 10:30 PM')
        self.assertContains(response, 'Name: Patient A')
        self.assertContains(response, 'View original raw OCR text')
        document.refresh_from_db()
        self.assertEqual(document.extracted_text, raw_text)

    def test_ocr_point_formatter_splits_fields_and_limits_overlong_points(self):
        points = format_ocr_points(
            '[OCR text; verify against the original] '
            'Name: Patient. Date: 13/10/26; '
            + ('unclear handwritten text ' * 20)
        )

        self.assertEqual(points[0], 'Name: Patient.')
        self.assertEqual(points[1], 'Date: 13/10/26')
        self.assertGreater(len(points), 3)
        self.assertTrue(all(len(point) <= 180 for point in points))

    def test_image_ocr_retry_updates_existing_upload_without_external_ai(self):
        image_buffer = BytesIO()
        Image.new('RGB', (80, 60), color='white').save(image_buffer, format='PNG')
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Retry OCR report',
            document_type=DocumentUpload.TYPE_LAB,
            file=SimpleUploadedFile('report.png', image_buffer.getvalue(), content_type='image/png'),
            extracted_text='OCR is unavailable on this server because Tesseract is not installed.',
        )
        self.client.login(username='owner', password='test-password')
        url = f'/prescriptions/{document.pk}/text/'

        with patch(
            'prescriptions.views.extract_text_from_uploaded_file',
            return_value='[OCR text; verify against the original]\nHemoglobin 12.5 g/dL',
        ) as extract:
            response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)
        extract.assert_called_once()
        document.refresh_from_db()
        self.assertIn('Hemoglobin 12.5 g/dL', document.extracted_text)
        self.assertContains(response, 'Hemoglobin 12.5 g/dL')
        self.assertTrue(PrescriptionAuditLog.objects.filter(
            document=document,
            actor=self.owner,
            metadata__access_method='local_ocr_reprocessed',
        ).exists())

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


@skip('External document analysis was removed; uploaded records must remain local.')
class PrescriptionAIAnalysisTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.owner = User.objects.create_user(username='owner', password='test-password')
        self.other_user = User.objects.create_user(username='other', password='test-password')
        self.document = DocumentUpload.objects.create(
            user=self.owner,
            title='Prescription',
            document_type=DocumentUpload.TYPE_PRESCRIPTION,
            file=SimpleUploadedFile('prescription.jpg', b'test image'),
            extracted_text='Original local OCR text',
            extracted_details={'medicines': [{'name': 'Original OCR medicine'}]},
        )
        self.url = f'/prescriptions/{self.document.pk}/ai-analysis/'
        self.analysis = {
            'provider': 'OpenAI API',
            'model': 'test-model',
            'created_at': '2026-10-12T10:00:00+00:00',
            'document': {
                'document_type': 'Prescription',
                'report_summary': 'Prescription document.',
                'transcription': 'Example medicine, as written',
                'diagnoses_as_written': [],
                'test_results': [],
                'medicines': [{
                    'name': 'Example medicine',
                    'strength': None,
                    'frequency': None,
                    'duration': None,
                    'instructions': None,
                    'needs_verification': True,
                }],
                'unclear_text': ['dose unclear'],
                'warnings': [],
            },
            'explanation': 'No verified catalog entry was available.',
            'references': [],
            'limitations': 'AI extraction is not medical advice.',
        }

    def test_ai_analysis_requires_login_and_is_owner_scoped(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.login(username='other', password='test-password')

        with patch('prescriptions.views.analyze_medical_document') as analyze:
            response = self.client.post(
                self.url,
                {'consent_to_external_processing': 'on'},
            )

        self.assertEqual(response.status_code, 404)
        analyze.assert_not_called()

    def test_ai_analysis_requires_explicit_consent(self):
        self.client.login(username='owner', password='test-password')
        with patch('prescriptions.views.analyze_medical_document') as analyze:
            response = self.client.post(self.url, {})

        self.assertRedirects(response, self.url)
        analyze.assert_not_called()
        self.assertFalse(PrescriptionAuditLog.objects.filter(
            document=self.document,
            metadata__external_processing_consented=True,
        ).exists())

    def test_ai_analysis_stores_results_separately_and_logs_consent(self):
        self.client.login(username='owner', password='test-password')
        with patch(
            'prescriptions.views.analyze_medical_document',
            return_value=self.analysis,
        ) as analyze:
            response = self.client.post(
                self.url,
                {'consent_to_external_processing': 'on'},
            )

        self.assertRedirects(response, self.url)
        analyze.assert_called_once_with(self.document)
        self.document.refresh_from_db()
        self.assertEqual(self.document.extracted_text, 'Original local OCR text')
        self.assertEqual(
            self.document.extracted_details['medicines'],
            [{'name': 'Original OCR medicine'}],
        )
        self.assertEqual(
            self.document.extracted_details['ai_assisted_analysis'],
            self.analysis,
        )
        event = PrescriptionAuditLog.objects.get(
            document=self.document,
            actor=self.owner,
            metadata__external_processing_consented=True,
        )
        self.assertEqual(event.metadata['access_method'], 'openai_medical_document_reading')

        result_page = self.client.get(self.url)
        self.assertEqual(result_page.status_code, 200)
        self.assertEqual(result_page['Cache-Control'], 'private, no-store')
        self.assertContains(result_page, 'Example medicine')
        self.assertContains(result_page, 'Needs manual verification')
        self.assertContains(result_page, 'sent to the OpenAI API')

    def test_vision_reading_and_explanation_use_verified_catalog_context(self):
        ingredient = ActiveIngredient.objects.create(
            name='Example active ingredient',
            standard_name='Example active ingredient',
            source_name='Ingredient source',
            source_url='https://example.test/ingredient',
            last_verified='2026-01-01',
            information_verified=True,
        )
        medicine = Medicine.objects.create(
            name='Verified example medicine',
            active_ingredient='Example active ingredient',
            dosage_form='Tablet',
            description='Source-verified catalog description.',
            source_name='Medicine source',
            source_url='https://example.test/medicine',
            last_verified='2026-01-01',
            safety_data_verified=True,
            slug='verified-example-medicine',
        )
        MedicineIngredient.objects.create(
            medicine=medicine,
            ingredient=ingredient,
            strength='250',
            unit='mg',
        )
        image_buffer = BytesIO()
        Image.new('RGB', (120, 80), color='white').save(image_buffer, format='JPEG')
        document = DocumentUpload.objects.create(
            user=self.owner,
            title='Vision test prescription',
            document_type=DocumentUpload.TYPE_PRESCRIPTION,
            file=SimpleUploadedFile('vision-test.jpg', image_buffer.getvalue(), content_type='image/jpeg'),
        )
        vision_result = json.dumps({
            'document_type': 'Prescription',
            'report_summary': 'Prescription with one medicine.',
            'transcription': 'Verified example medicine',
            'diagnoses_as_written': [],
            'test_results': [],
            'medicines': [{
                'name': 'Verified example medicine',
                'strength': None,
                'frequency': None,
                'duration': None,
                'instructions': None,
                'needs_verification': False,
            }],
            'unclear_text': [],
            'warnings': [],
        })
        with patch(
            'prescriptions.services.ai_analysis._openai_response',
            side_effect=[vision_result, 'Catalog facts only.'],
        ) as openai_response:
            result = analyze_medical_document(document)

        self.assertEqual(result['document']['medicines'][0]['name'], medicine.name)
        self.assertEqual(result['explanation'], 'Catalog facts only.')
        self.assertEqual(result['references'][0]['source_url'], medicine.source_url)
        self.assertEqual(result['references'][0]['composition'][0]['strength'], '250')
        self.assertEqual(openai_response.call_count, 2)
        explanation_prompt = openai_response.call_args_list[1].args[0][0]['text']
        self.assertIn('Source-verified catalog description.', explanation_prompt)
        self.assertIn('https://example.test/medicine', explanation_prompt)

    def test_pdf_image_payload_mime_matches_jpeg_encoding(self):
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text((72, 72), 'Example medical report')
        pdf_data = pdf.tobytes()
        pdf.close()

        payloads = _image_payloads(pdf_data, 'report.pdf')

        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0][0], 'image/jpeg')
        self.assertTrue(payloads[0][1].startswith(b'\xff\xd8'))

    def test_lab_report_ai_page_is_owner_scoped_and_displays_full_text_and_results(self):
        report = DocumentUpload.objects.create(
            user=self.owner,
            title='Lab report',
            document_type=DocumentUpload.TYPE_LAB,
            file=SimpleUploadedFile('report.pdf', b'fake pdf'),
        )
        report_url = f'/prescriptions/{report.pk}/ai-analysis/'
        self.client.login(username='owner', password='test-password')
        self.assertEqual(self.client.get(report_url).status_code, 200)

        lab_analysis = {
            **self.analysis,
            'document': {
                **self.analysis['document'],
                'document_type': 'Lab report',
                'report_summary': 'Laboratory report with one test result.',
                'transcription': 'Hemoglobin 12.5 g/dL\nReference interval: 12-16 g/dL',
                'diagnoses_as_written': ['Only present if printed: example note'],
                'test_results': [{
                    'name': 'Hemoglobin',
                    'value': '12.5',
                    'unit': 'g/dL',
                    'printed_reference_range': '12-16 g/dL',
                    'flag_as_written': None,
                }],
                'medicines': [],
            },
        }
        with patch(
            'prescriptions.views.analyze_medical_document',
            return_value=lab_analysis,
        ):
            response = self.client.post(
                report_url,
                {'consent_to_external_processing': 'on'},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Full extracted text')
        self.assertContains(response, 'Hemoglobin 12.5 g/dL')
        self.assertContains(response, '12-16 g/dL')


class OCRServiceTests(TestCase):
    def test_text_pdf_extracts_embedded_text(self):
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text((72, 72), 'Laboratory report Hemoglobin 12.5 g/dL')
        data = pdf.tobytes()
        pdf.close()
        upload = SimpleUploadedFile('report.pdf', data, content_type='application/pdf')

        result = extract_text_from_uploaded_file(upload)

        self.assertIn('embedded text', result)
        self.assertIn('Hemoglobin 12.5 g/dL', result)

    @patch('prescriptions.services.ocr._ocr_image', return_value='Lab value 12.5 g/dL')
    @patch('prescriptions.services.ocr.shutil.which', return_value='tesseract')
    def test_scanned_pdf_page_is_rendered_and_ocrd(self, _which, ocr_image):
        image_buffer = BytesIO()
        Image.new('RGB', (80, 60), color='white').save(image_buffer, format='PNG')
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_image(page.rect, stream=image_buffer.getvalue())
        data = pdf.tobytes()
        pdf.close()
        upload = SimpleUploadedFile('scan.pdf', data, content_type='application/pdf')

        result = extract_text_from_uploaded_file(upload)

        self.assertIn('PDF page 1 - OCR; verify against original', result)
        self.assertIn('Lab value 12.5 g/dL', result)
        ocr_image.assert_called_once()

    @patch('prescriptions.services.ocr.pytesseract.image_to_data')
    @patch('prescriptions.services.ocr.shutil.which', return_value='tesseract')
    def test_image_ocr_selects_variant_with_highest_word_confidence(self, _which, image_to_data):
        image_buffer = BytesIO()
        Image.new('RGB', (80, 60), color='white').save(image_buffer, format='PNG')
        image_to_data.side_effect = [
            {'text': ['low', 'quality'], 'conf': ['20', '20']},
            {'text': ['Clear', 'report'], 'conf': ['90', '95']},
        ]
        upload = SimpleUploadedFile(
            'report.png',
            image_buffer.getvalue(),
            content_type='image/png',
        )

        result = extract_text_from_uploaded_file(upload)

        self.assertIn('[OCR text; verify against the original]', result)
        self.assertIn('Clear report', result)
        self.assertNotIn('low quality', result)
        self.assertEqual(image_to_data.call_count, 2)

    @patch('prescriptions.services.ocr._tesseract_available', return_value=False)
    def test_image_ocr_explicitly_reports_missing_tesseract(self, _available):
        image_buffer = BytesIO()
        Image.new('RGB', (80, 60), color='white').save(image_buffer, format='PNG')
        upload = SimpleUploadedFile(
            'report.png',
            image_buffer.getvalue(),
            content_type='image/png',
        )

        result = extract_text_from_uploaded_file(upload)

        self.assertIn('Tesseract is not installed', result)
