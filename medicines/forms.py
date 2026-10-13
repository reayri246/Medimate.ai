from django import forms


class MedicineSearchForm(forms.Form):
    query = forms.CharField(
        label='Search medicines',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control medicine-search-input',
            'placeholder': 'Search by medicine or active ingredient',
            'autocomplete': 'off',
        }),
    )
