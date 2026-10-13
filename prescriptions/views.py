from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from .forms import MedicineReviewFormSet, UploadDocumentForm
from .models import DocumentUpload, PrescriptionAuditLog
from .services.ocr import extract_text_from_uploaded_file
from .services.ocr_formatting import format_ocr_points
from .services.lab_explanations import explain_lab_test
from .services.record_intelligence import (
    build_fhir_bundle,
    build_prescription_soft_copy,
    extract_record_details,
)
from medicines.models import Medicine


def _explained_test_values(document):
    details = document.extracted_details or {}
    values = []
    for value in details.get('test_values', []):
        explained_value = dict(value)
        explained_value.update(explain_lab_test(value))
        values.append(explained_value)
    return values


@login_required
def prescription_list(request):
    documents = Paginator(
        DocumentUpload.objects.filter(user=request.user).order_by('-created_at'),
        20,
    ).get_page(request.GET.get('page'))
    PrescriptionAuditLog.objects.bulk_create([
        PrescriptionAuditLog(
            document=document,
            actor=request.user,
            action=PrescriptionAuditLog.ACTION_VIEWED,
        )
        for document in documents.object_list
    ])
    for document in documents.object_list:
        document.explained_test_values = _explained_test_values(document)
    language = 'te' if request.GET.get('lang') == 'te' else 'en'
    return render(request, 'prescriptions/list.html', {
        'documents': documents,
        'summary_language': language,
    })


@login_required
def prescription_upload(request):
    if request.method == 'POST':
        form = UploadDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded = request.FILES['file']
            document = form.save(commit=False)
            document.user = request.user
            document.extracted_text = extract_text_from_uploaded_file(
                uploaded,
                language=form.cleaned_data['ocr_language'],
            )
            document.extracted_details = extract_record_details(document.extracted_text)
            document.extracted_medicines = document.extracted_details['medicines']
            with transaction.atomic():
                document.save()
                PrescriptionAuditLog.objects.create(
                    document=document,
                    actor=request.user,
                    action=PrescriptionAuditLog.ACTION_UPLOADED,
                    metadata={'document_type': document.document_type},
                )
            messages.success(
                request,
                'Upload complete. The document was processed locally. Compare the extracted text with the original document.',
            )
            return redirect('document_text', document_id=document.pk)
    else:
        form = UploadDocumentForm()
    return render(request, 'prescriptions/upload.html', {'form': form})


@login_required
def document_text(request, document_id):
    document = get_object_or_404(DocumentUpload, pk=document_id, user=request.user)
    image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}
    extension = '.' + document.file.name.rsplit('.', 1)[-1].lower() if '.' in document.file.name else ''
    if request.method == 'POST':
        if extension not in image_extensions | {'.pdf'}:
            raise Http404('OCR retry is not available for this file type.')
        document.extracted_text = extract_text_from_uploaded_file(
            document.file,
            language=document.ocr_language,
        )
        document.extracted_details = extract_record_details(document.extracted_text)
        document.extracted_medicines = document.extracted_details['medicines']
        document.save(update_fields=[
            'extracted_text',
            'extracted_details',
            'extracted_medicines',
        ])
        PrescriptionAuditLog.objects.create(
            document=document,
            actor=request.user,
            action=PrescriptionAuditLog.ACTION_VIEWED,
            metadata={'access_method': 'local_ocr_reprocessed'},
        )
        if 'Tesseract is not installed' in document.extracted_text or 'OCR is unavailable' in document.extracted_text:
            messages.warning(request, document.extracted_text)
        elif 'No text was detected' in document.extracted_text or 'no text detected' in document.extracted_text:
            messages.warning(request, 'OCR ran, but could not read text from this image. Try a clearer scan and check the original.')
        else:
            messages.success(request, 'Local OCR finished. Compare the extracted text with the original document.')
        return redirect('document_text', document_id=document.pk)

    PrescriptionAuditLog.objects.create(
        document=document,
        actor=request.user,
        action=PrescriptionAuditLog.ACTION_VIEWED,
        metadata={'access_method': 'extracted_text_page'},
    )
    response = render(request, 'prescriptions/document_text.html', {
        'document': document,
        'ocr_points': format_ocr_points(document.extracted_text),
        'explained_test_values': _explained_test_values(document),
        'show_image_preview': extension in image_extensions,
        'show_pdf_preview': extension == '.pdf',
        'can_retry_ocr': extension in image_extensions | {'.pdf'},
    })
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def document_image_preview(request, document_id):
    document = get_object_or_404(DocumentUpload, pk=document_id, user=request.user)
    extension = '.' + document.file.name.rsplit('.', 1)[-1].lower() if '.' in document.file.name else ''
    if extension not in {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}:
        raise Http404('An image preview is not available for this document.')
    try:
        document.file.open('rb')
        with document.file:
            with Image.open(document.file) as source_image:
                image = ImageOps.exif_transpose(source_image)
                image.load()
            image.thumbnail((2200, 2200))
            output = BytesIO()
            image.convert('RGB').save(output, format='JPEG', quality=90)
            output.seek(0)
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise Http404('The requested image preview is unavailable.') from exc
    response = FileResponse(
        BytesIO(output.getvalue()),
        content_type='image/jpeg',
        filename='document-preview.jpg',
    )
    response['Content-Disposition'] = 'inline; filename="document-preview.jpg"'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def document_review(request, document_id):
    document = get_object_or_404(DocumentUpload, pk=document_id, user=request.user)
    if document.reviewed_medicines:
        initial = [
            {
                'recognized_text': item.get('recognized_text', ''),
                'catalog_medicine': item.get('catalog_medicine_id'),
                'strength': item.get('strength_as_written', ''),
                'dosage_instructions': item.get('instructions_as_written', ''),
                'verification_status': item.get('verification_status', 'pending'),
            }
            for item in document.reviewed_medicines
        ]
    else:
        initial = []
        for detection in document.extracted_medicines:
            catalog_entry = Medicine.objects.filter(name=detection.get('catalog_medicine', '')).first()
            initial.append({
                'recognized_text': detection.get('name', ''),
                'catalog_medicine': catalog_entry.pk if catalog_entry else None,
                'verification_status': 'pending',
            })

    if request.method == 'POST':
        formset = MedicineReviewFormSet(request.POST, prefix='medicine')
        if formset.is_valid():
            reviewed_entries = []
            for form in formset:
                cleaned = form.cleaned_data
                if form.empty_permitted and not any(
                    cleaned.get(field_name)
                    for field_name in (
                        'recognized_text',
                        'catalog_medicine',
                        'strength',
                        'dosage_instructions',
                    )
                ):
                    continue
                selected_medicine = cleaned.get('catalog_medicine')
                reviewed_entries.append({
                    'recognized_text': cleaned.get('recognized_text', '').strip(),
                    'catalog_medicine_id': selected_medicine.pk if selected_medicine else None,
                    'catalog_medicine_name': selected_medicine.name if selected_medicine else '',
                    'strength_as_written': cleaned.get('strength', '').strip(),
                    'instructions_as_written': cleaned.get('dosage_instructions', '').strip(),
                    'verification_status': cleaned['verification_status'],
                    'verified_by': 'patient',
                })
            with transaction.atomic():
                document.reviewed_medicines = reviewed_entries
                document.review_status = DocumentUpload.REVIEWED
                document.reviewed_at = timezone.now()
                document.save(update_fields=[
                    'reviewed_medicines',
                    'review_status',
                    'reviewed_at',
                ])
                PrescriptionAuditLog.objects.create(
                    document=document,
                    actor=request.user,
                    action=PrescriptionAuditLog.ACTION_REVIEWED,
                    metadata={'entry_count': len(reviewed_entries)},
                )
            messages.success(
                request,
                'Your review was saved. Patient confirmation is not professional verification or prescribing advice.',
            )
            return redirect('prescription_list')
    else:
        formset = MedicineReviewFormSet(initial=initial, prefix='medicine')
    return render(request, 'prescriptions/review.html', {
        'document': document,
        'formset': formset,
    })


@login_required
def prescription_soft_copy(request, document_id):
    document = get_object_or_404(
        DocumentUpload,
        pk=document_id,
        user=request.user,
        document_type=DocumentUpload.TYPE_PRESCRIPTION,
    )
    PrescriptionAuditLog.objects.create(
        document=document,
        actor=request.user,
        action=PrescriptionAuditLog.ACTION_SOFT_COPY,
    )
    response = render(
        request,
        'prescriptions/soft_copy.html',
        build_prescription_soft_copy(document),
    )
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def document_api(request, document_id):
    document = get_object_or_404(DocumentUpload, pk=document_id, user=request.user)
    PrescriptionAuditLog.objects.create(
        document=document,
        actor=request.user,
        action=PrescriptionAuditLog.ACTION_VIEWED,
        metadata={'access_method': 'json_api'},
    )
    response = JsonResponse({
        'id': document.pk,
        'title': document.title,
        'document_type': document.document_type,
        'processing_mode': 'synchronous_local_ocr_and_rules',
        'review_status': document.review_status,
        'extracted_text': document.extracted_text,
        'extracted_medicines': document.extracted_medicines,
        'extracted_details': document.extracted_details,
        'patient_reviewed_medicines': document.reviewed_medicines,
        'created_at': document.created_at.isoformat(),
    })
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def document_fhir_export(request, document_id):
    document = get_object_or_404(DocumentUpload, pk=document_id, user=request.user)
    download_url = request.build_absolute_uri(
        reverse('document_download', args=(document.pk,))
    )
    response = JsonResponse(build_fhir_bundle(document, download_url))
    response['Content-Disposition'] = f'attachment; filename="document-{document.pk}-fhir.json"'
    response['Cache-Control'] = 'private, no-store'
    PrescriptionAuditLog.objects.create(
        document=document,
        actor=request.user,
        action=PrescriptionAuditLog.ACTION_EXPORTED,
    )
    return response


@login_required
def document_download(request, document_id):
    document = get_object_or_404(DocumentUpload, pk=document_id, user=request.user)
    try:
        document.file.open('rb')
    except (FileNotFoundError, OSError) as exc:
        raise Http404('The requested document is unavailable.') from exc

    PrescriptionAuditLog.objects.create(
        document=document,
        actor=request.user,
        action=PrescriptionAuditLog.ACTION_DOWNLOADED,
    )
    response = FileResponse(
        document.file,
        as_attachment=True,
        filename=document.file.name.rsplit('/', 1)[-1],
        content_type='application/octet-stream',
    )
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response
