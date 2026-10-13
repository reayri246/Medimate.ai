from django import forms
from django.utils import timezone

from .models import Appointment, Doctor, DoctorAvailability, DoctorWorkingDay


class TwelveHourScheduleForm(forms.ModelForm):
    start_time = forms.TimeField(
        input_formats=('%I:%M %p',),
        help_text='Use 12-hour time with AM or PM, for example 09:00 AM.',
        widget=forms.TimeInput(
            format='%I:%M %p',
            attrs={
                'type': 'text',
                'placeholder': '09:00 AM',
                'autocomplete': 'off',
                'pattern': r'(0[1-9]|1[0-2]):[0-5][0-9]\s?(AM|PM)',
                'title': 'Enter a time such as 09:00 AM or 02:30 PM.',
            },
        ),
    )
    end_time = forms.TimeField(
        input_formats=('%I:%M %p',),
        help_text='Use 12-hour time with AM or PM, for example 05:00 PM.',
        widget=forms.TimeInput(
            format='%I:%M %p',
            attrs={
                'type': 'text',
                'placeholder': '05:00 PM',
                'autocomplete': 'off',
                'pattern': r'(0[1-9]|1[0-2]):[0-5][0-9]\s?(AM|PM)',
                'title': 'Enter a time such as 09:00 AM or 02:30 PM.',
            },
        ),
    )


class DoctorWorkingDayForm(TwelveHourScheduleForm):
    class Meta:
        model = DoctorWorkingDay
        fields = '__all__'


class DoctorAvailabilityForm(TwelveHourScheduleForm):
    class Meta:
        model = DoctorAvailability
        fields = '__all__'


class SymptomRoutingForm(forms.Form):
    symptoms = forms.CharField(
        label='What symptoms would you like to discuss?',
        min_length=3,
        max_length=2000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Describe what you would like the doctor to discuss. This is not a diagnosis.',
        }),
    )
    requested_date = forms.DateField(
        label='Preferred appointment date',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['requested_date'].widget.attrs['min'] = timezone.localdate().isoformat()

    def clean_requested_date(self):
        requested_date = self.cleaned_data['requested_date']
        today = timezone.localdate()
        if requested_date < today:
            raise forms.ValidationError('Choose today or a future date.')
        if (requested_date - today).days > 365:
            raise forms.ValidationError('Choose a date within the next 12 months.')
        return requested_date


class DoctorSelectionForm(forms.Form):
    symptoms = forms.CharField(min_length=3, max_length=2000, widget=forms.HiddenInput)
    requested_date = forms.DateField(widget=forms.HiddenInput)
    doctor = forms.ModelChoiceField(queryset=Doctor.objects.none(), widget=forms.HiddenInput)

    def __init__(self, *args, doctors=None, **kwargs):
        super().__init__(*args, **kwargs)
        if doctors is not None:
            self.fields['doctor'].queryset = doctors


class AppointmentPermissionForm(forms.Form):
    symptoms = forms.CharField(min_length=3, max_length=2000, widget=forms.HiddenInput)
    requested_date = forms.DateField(widget=forms.HiddenInput)
    doctor = forms.ModelChoiceField(queryset=Doctor.objects.none(), widget=forms.HiddenInput)
    consent = forms.BooleanField(
        required=True,
        label='I give permission to share these symptoms and my preferred date with the selected doctor and the consultation office/reception desk to arrange this appointment.',
    )

    def __init__(self, *args, doctors=None, **kwargs):
        super().__init__(*args, **kwargs)
        if doctors is not None:
            self.fields['doctor'].queryset = doctors

    def clean_requested_date(self):
        requested_date = self.cleaned_data['requested_date']
        today = timezone.localdate()
        if requested_date < today or (requested_date - today).days > 365:
            raise forms.ValidationError('Choose today or a date within the next 12 months.')
        return requested_date


class AppointmentDecisionForm(forms.Form):
    decision = forms.ChoiceField(
        choices=((Appointment.STATUS_ACCEPTED, 'Accept'), (Appointment.STATUS_REJECTED, 'Reject')),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    scheduled_at = forms.DateTimeField(
        required=False,
        label='Appointment time (required when accepting)',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
    )
    notes = forms.CharField(
        required=False,
        max_length=1000,
        label='Message to the patient',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
    )

    def __init__(self, *args, appointment=None, **kwargs):
        self.appointment = appointment
        super().__init__(*args, **kwargs)

    def clean_notes(self):
        return self.cleaned_data['notes'].strip()

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('decision') == Appointment.STATUS_ACCEPTED:
            scheduled_at = cleaned_data.get('scheduled_at')
            if not scheduled_at:
                self.add_error('scheduled_at', 'Set the appointment time before accepting.')
            elif self.appointment and scheduled_at.date() != self.appointment.requested_date:
                self.add_error('scheduled_at', 'The confirmed time must be on the patient’s requested date.')
            elif scheduled_at <= timezone.localtime():
                self.add_error('scheduled_at', 'Choose a future appointment time.')
        return cleaned_data
