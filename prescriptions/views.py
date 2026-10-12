import mimetypes

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import MedicineReviewFormSet, UploadDocumentForm
from .models import DocumentUpload, PrescriptionAuditLog
from .services.ocr import extract_text_from_uploaded_file
from .services.record_intelligence import build_fhir_bundle, extract_record_details
from medicines.models import Medicine


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
            if document.extracted_details['medicines'] or document.extracted_details['test_values']:
                messages.success(
                    request,
                    'Upload complete. Possible details were extracted from readable text. Review every item against the original document.',
                )
            else:
                messages.info(
                    request,
                    'Upload complete. No supported medicine names or lab values were recognized in readable text. Check the original document; OCR may not read scans or handwriting clearly.',
                )
            return redirect('prescription_list')
    else:
        form = UploadDocumentForm()
    return render(request, 'prescriptions/upload.html', {'form': form})


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
