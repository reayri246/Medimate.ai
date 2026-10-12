from django import forms

from .models import Medicine
from .safety import verified_medicines


class MedicineSearchForm(forms.Form):
    query = forms.CharField(
        label='Search medicines',
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Search by medicine or ingredient'}),
    )


class MedicineComparisonForm(forms.Form):
    medicines = forms.ModelMultipleChoiceField(
        label='Select 2 to 4 verified medicines to compare',
        queryset=Medicine.objects.none(),
        required=True,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        self.verified_medicine_list = verified_medicines()
        super().__init__(*args, **kwargs)
        self.fields['medicines'].queryset = Medicine.objects.filter(
            pk__in=[medicine.pk for medicine in self.verified_medicine_list]
        )

    def clean_medicines(self):
        medicines = self.cleaned_data['medicines']
        if not 2 <= len(medicines) <= 4:
            raise forms.ValidationError('Select between two and four medicines.')
        return medicines
