from django import forms
from django.utils import timezone

from .models import Appointment, AppointmentManagement
from .views import _doctor_is_on_duty, _doctor_schedule


class AppointmentManagementForm(forms.ModelForm):
    scheduled_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )

    class Meta:
        model = AppointmentManagement
        fields = ('status', 'scheduled_at', 'notes')
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('status') != Appointment.STATUS_ACCEPTED:
            return cleaned_data

        appointment = self.instance
        scheduled_at = cleaned_data.get('scheduled_at')
        if not appointment.doctor_id or not appointment.requested_date:
            raise forms.ValidationError(
                'An appointment must have a doctor and requested date before acceptance.'
            )
        if not scheduled_at:
            self.add_error('scheduled_at', 'Set the confirmed appointment date and time.')
            return cleaned_data
        if timezone.localtime(scheduled_at).date() != appointment.requested_date:
            self.add_error('scheduled_at', 'The confirmed time must be on the requested date.')
            return cleaned_data
        if scheduled_at <= timezone.localtime():
            self.add_error('scheduled_at', 'Choose a future appointment time.')
            return cleaned_data
        if (
            not appointment.doctor.is_active
            or not _doctor_is_on_duty(appointment.doctor, appointment.requested_date)
        ):
            raise forms.ValidationError(
                'This doctor is not active and on duty for the requested date.'
            )
        working_hours = _doctor_schedule(appointment.doctor, appointment.requested_date)
        appointment_time = timezone.localtime(scheduled_at).time()
        if not working_hours or not working_hours[0] <= appointment_time < working_hours[1]:
            self.add_error('scheduled_at', 'Choose a time within the doctor’s working hours.')
        return cleaned_data
