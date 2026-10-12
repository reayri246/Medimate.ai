from django import forms
from django.forms import formset_factory
from PIL import Image
import io
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .models import DocumentUpload
from medicines.models import Medicine


MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.txt'}


class UploadDocumentForm(forms.ModelForm):
    document_type = forms.ChoiceField(
        choices=DocumentUpload.DOCUMENT_TYPE_CHOICES,
        label='Record type',
        initial=DocumentUpload.TYPE_OTHER,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    ocr_language = forms.ChoiceField(
        choices=DocumentUpload.OCR_LANGUAGE_CHOICES,
        label='Document language for OCR',
        help_text='Telugu OCR requires the Telugu language data pack to be installed with Tesseract.',
        required=False,
        initial=DocumentUpload.OCR_ENGLISH,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = DocumentUpload
        fields = ['title', 'document_type', 'file', 'ocr_language']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def clean_file(self):
        uploaded = self.cleaned_data['file']
        extension = '.' + uploaded.name.rsplit('.', 1)[-1].lower() if '.' in uploaded.name else ''
        if extension not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError('Upload a PDF, image, or plain-text file.')
        if uploaded.size > MAX_DOCUMENT_SIZE:
            raise forms.ValidationError('The maximum upload size is 10 MB.')
        try:
            if extension == '.pdf':
                uploaded.seek(0)
                reader = PdfReader(io.BytesIO(uploaded.read()), strict=True)
                if not reader.pages:
                    raise forms.ValidationError('The PDF does not contain any readable pages.')
            elif extension in {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}:
                uploaded.seek(0)
                with Image.open(uploaded) as image:
                    image.verify()
        except forms.ValidationError:
            raise
        except (OSError, ValueError, PdfReadError, Image.DecompressionBombError) as exc:
            raise forms.ValidationError('The uploaded image or PDF is corrupted or unreadable.') from exc
        finally:
            uploaded.seek(0)
        return uploaded

    def clean_ocr_language(self):
        return self.cleaned_data.get('ocr_language') or DocumentUpload.OCR_ENGLISH


class MedicineReviewForm(forms.Form):
    VERIFICATION_PENDING = 'pending'
    PATIENT_CONFIRMED = 'patient_confirmed'
    UNREADABLE = 'unreadable'
    VERIFICATION_CHOICES = [
        (VERIFICATION_PENDING, 'Needs verification'),
        (PATIENT_CONFIRMED, 'I confirmed the text against the original'),
        (UNREADABLE, 'Mark as unreadable'),
    ]

    recognized_text = forms.CharField(
        max_length=300,
        required=False,
        label='Text on prescription',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    catalog_medicine = forms.ModelChoiceField(
        queryset=Medicine.objects.none(),
        required=False,
        label='Exact catalog match (optional)',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    strength = forms.CharField(
        max_length=100,
        required=False,
        label='Strength exactly as written (optional)',
        help_text='Leave blank if unclear. Do not infer a strength.',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    dosage_instructions = forms.CharField(
        max_length=500,
        required=False,
        label='Instructions exactly as written (optional)',
        help_text='Enter only what you can read on the source. Do not add a frequency or duration.',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    verification_status = forms.ChoiceField(
        choices=VERIFICATION_CHOICES,
        initial=VERIFICATION_PENDING,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['catalog_medicine'].queryset = Medicine.objects.order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        verification_status = cleaned_data.get('verification_status') or self.VERIFICATION_PENDING
        cleaned_data['verification_status'] = verification_status
        catalog_medicine = cleaned_data.get('catalog_medicine')
        if verification_status == self.PATIENT_CONFIRMED and not (
            cleaned_data.get('recognized_text') or catalog_medicine
        ):
            raise forms.ValidationError('Enter the text you confirmed or select an exact catalog match.')
        if verification_status == self.UNREADABLE and (
            cleaned_data.get('recognized_text') or catalog_medicine or cleaned_data.get('strength')
            or cleaned_data.get('dosage_instructions')
        ):
            raise forms.ValidationError('Clear extracted fields when marking a medicine entry unreadable.')
        return cleaned_data


MedicineReviewFormSet = formset_factory(
    MedicineReviewForm,
    extra=1,
    max_num=51,
    validate_max=True,
)
