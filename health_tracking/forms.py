from django import forms

from .models import HealthMeasurement


class HealthMeasurementForm(forms.ModelForm):
    class Meta:
        model = HealthMeasurement
        fields = ['date', 'weight_kg', 'blood_pressure', 'heart_rate', 'temperature_c', 'glucose_mgdl', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'weight_kg': forms.NumberInput(attrs={'class': 'form-control'}),
            'blood_pressure': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '110/70'}),
            'heart_rate': forms.NumberInput(attrs={'class': 'form-control'}),
            'temperature_c': forms.NumberInput(attrs={'class': 'form-control'}),
            'glucose_mgdl': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
