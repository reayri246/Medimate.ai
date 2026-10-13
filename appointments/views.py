from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from notifications.models import Notification

from .forms import (
    AppointmentDecisionForm,
    AppointmentPermissionForm,
    DoctorSelectionForm,
    SymptomRoutingForm,
)
from .models import Appointment, AppointmentActivity, Doctor, DoctorAvailability, DoctorWorkingDay
from .routing import is_emergency_phrase, matched_doctor_symptoms


def _available_doctors(requested_date):
    return Doctor.objects.filter(
        is_active=True,
    ).filter(
        Q(working_days__weekday=requested_date.weekday())
        | Q(availability__date=requested_date, availability__is_on_duty=True)
    ).exclude(
        availability__date=requested_date,
        availability__is_on_duty=False,
    ).distinct().order_by('name')


def _doctor_schedule(doctor, requested_date):
    override = DoctorAvailability.objects.filter(
        doctor=doctor,
        date=requested_date,
    ).first()
    if override is not None:
        if not override.is_on_duty:
            return None
        return override.start_time, override.end_time
    working_day = DoctorWorkingDay.objects.filter(
        doctor=doctor,
        weekday=requested_date.weekday(),
    ).first()
    if not working_day:
        return None
    return working_day.start_time, working_day.end_time


def _doctor_is_on_duty(doctor, requested_date):
    return _doctor_schedule(doctor, requested_date) is not None


def _is_appointment_staff(user, appointment):
    if user.is_staff:
        return True
    return bool(
        appointment.doctor_id
        and appointment.doctor.account_id == user.pk
    )


@login_required
def appointment_list(request):
    appointments = Appointment.objects.filter(user=request.user).select_related(
        'doctor',
    ).order_by('-requested_date', '-scheduled_at', '-pk')
    return render(request, 'appointments/list.html', {'appointments': appointments})


@login_required
def appointment_request(request):
    if request.method == 'POST' and request.POST.get('step') == 'find':
        routing_form = SymptomRoutingForm(request.POST)
        if not routing_form.is_valid():
            return render(request, 'appointments/request.html', {'routing_form': routing_form})
        symptoms = routing_form.cleaned_data['symptoms'].strip()
        requested_date = routing_form.cleaned_data['requested_date']
        if is_emergency_phrase(symptoms):
            return render(request, 'appointments/request.html', {
                'routing_form': routing_form,
                'emergency_message': (
                    'These symptoms may need urgent assessment. Call your local emergency number '
                    'or seek emergency care now instead of waiting for a routine appointment.'
                ),
            })
        doctors_on_duty = list(_available_doctors(requested_date))
        matches = [
            {
                'doctor': doctor,
                'matched_symptoms': matched_doctor_symptoms(symptoms, doctor),
                'working_hours': _doctor_schedule(doctor, requested_date),
            }
            for doctor in doctors_on_duty
        ]
        matches = [match for match in matches if match['matched_symptoms']]
        return render(request, 'appointments/request.html', {
            'routing_form': routing_form,
            'doctor_matches': matches,
            'has_doctors_on_duty': bool(doctors_on_duty),
            'matched_terms': sorted({
                term for match in matches for term in match['matched_symptoms']
            }),
            'matching': True,
            'selected_symptoms': symptoms,
            'selected_date': requested_date,
        })

    if request.method == 'POST' and request.POST.get('step') == 'choose':
        symptoms = request.POST.get('symptoms', '').strip()
        requested_date_raw = request.POST.get('requested_date', '')
        try:
            requested_date = datetime.strptime(requested_date_raw, '%Y-%m-%d').date()
        except ValueError:
            requested_date = None
        eligible_doctors = _available_doctors(requested_date) if requested_date else Doctor.objects.none()
        eligible_doctors = [
            doctor for doctor in eligible_doctors
            if matched_doctor_symptoms(symptoms, doctor)
        ]
        selection_form = DoctorSelectionForm(
            request.POST,
            doctors=Doctor.objects.filter(pk__in=[doctor.pk for doctor in eligible_doctors]),
        )
        if selection_form.is_valid() and requested_date and requested_date >= timezone.localdate():
            doctor = selection_form.cleaned_data['doctor']
            permission_form = AppointmentPermissionForm(
                initial={
                    'symptoms': symptoms,
                    'requested_date': requested_date,
                    'doctor': doctor,
                },
                doctors=Doctor.objects.filter(pk=doctor.pk),
            )
            return render(request, 'appointments/request.html', {
                'permission_form': permission_form,
                'doctor': doctor,
                'selected_symptoms': symptoms,
                'selected_date': requested_date,
                'confirm_request': True,
            })
        messages.error(request, 'That doctor is no longer available for the selected date. Please search again.')

    if request.method == 'POST' and request.POST.get('step') == 'confirm':
        requested_date_raw = request.POST.get('requested_date', '')
        try:
            requested_date = datetime.strptime(requested_date_raw, '%Y-%m-%d').date()
        except ValueError:
            requested_date = None
        permission_form = AppointmentPermissionForm(
            request.POST,
            doctors=(
                _available_doctors(requested_date)
                if requested_date else Doctor.objects.none()
            ),
        )
        if not permission_form.is_valid() or not requested_date or requested_date < timezone.localdate():
            doctor = permission_form.fields['doctor'].queryset.filter(
                pk=request.POST.get('doctor'),
            ).first()
            return render(request, 'appointments/request.html', {
                'permission_form': permission_form,
                'doctor': doctor,
                'selected_symptoms': request.POST.get('symptoms', ''),
                'selected_date': requested_date,
                'confirm_request': doctor is not None,
                'routing_form': SymptomRoutingForm(),
            })
        else:
            doctor = permission_form.cleaned_data['doctor']
            symptoms = permission_form.cleaned_data['symptoms'].strip()
            if is_emergency_phrase(symptoms):
                return render(request, 'appointments/request.html', {
                    'routing_form': SymptomRoutingForm(),
                    'emergency_message': (
                        'These symptoms may need urgent assessment. Call your local emergency number '
                        'or seek emergency care now instead of waiting for a routine appointment.'
                    ),
                })
            if not matched_doctor_symptoms(symptoms, doctor):
                messages.error(request, 'The doctor no longer matches these symptoms. Please search again.')
            else:
                with transaction.atomic():
                    appointment = Appointment.objects.create(
                        user=request.user,
                        doctor=doctor,
                        requested_date=requested_date,
                        title=f'Consultation request — {doctor.get_specialty_display()}',
                        symptoms=symptoms,
                        patient_consent=True,
                        status=Appointment.STATUS_PENDING,
                    )
                    AppointmentActivity.objects.create(
                        actor=request.user,
                        appointment=appointment,
                        doctor=doctor,
                        description='Patient submitted a consultation request.',
                    )
                    letter_url = reverse('appointment_letter', args=(appointment.pk,))
                    recipients = set(User.objects.filter(is_staff=True).values_list('pk', flat=True))
                    if doctor.account_id:
                        recipients.add(doctor.account_id)
                    Notification.objects.bulk_create([
                        Notification(
                            user_id=user_id,
                            title='New consultation request for the office',
                            body=f'A patient requested {doctor.get_specialty_display()} on {requested_date}. Review the request and appointment letter.',
                            url=reverse('staff_appointment_queue'),
                        )
                        for user_id in recipients
                    ])
                    Notification.objects.create(
                        user=request.user,
                        title='Appointment request received',
                        body=f'Your request for {doctor.get_specialty_display()} on {requested_date} is awaiting office review. Your appointment letter is available.',
                        url=letter_url,
                    )
                messages.success(request, 'Your request and appointment letter were sent to the doctor’s office and reception desk for review.')
                return redirect('appointment_list')

    return render(request, 'appointments/request.html', {
        'routing_form': SymptomRoutingForm(initial={'requested_date': timezone.localdate()}),
    })


@login_required
def appointment_letter(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related('user', 'doctor', 'doctor__account'),
        pk=appointment_id,
    )
    if not (
        request.user.is_staff
        or appointment.user_id == request.user.pk
        or (appointment.doctor and appointment.doctor.account_id == request.user.pk)
    ):
        return HttpResponseForbidden('You do not have permission to view this appointment letter.')
    return render(request, 'appointments/letter.html', {
        'appointment': appointment,
        'working_hours': (
            _doctor_schedule(appointment.doctor, appointment.requested_date)
            if appointment.doctor and appointment.requested_date else None
        ),
    })


@login_required
def staff_appointment_queue(request):
    if request.user.is_staff:
        appointments = Appointment.objects.filter(status=Appointment.STATUS_PENDING)
    else:
        doctor = Doctor.objects.filter(account=request.user).first()
        if doctor is None:
            return HttpResponseForbidden('You do not have permission to view the appointment desk.')
        appointments = Appointment.objects.filter(
            status=Appointment.STATUS_PENDING,
            doctor=doctor,
        )
    appointments = appointments.filter(doctor__isnull=False).select_related(
        'user', 'doctor',
    ).order_by('requested_date', 'pk')
    for appointment in appointments:
        appointment.working_hours = (
            _doctor_schedule(appointment.doctor, appointment.requested_date)
            if appointment.requested_date else None
        )
    return render(request, 'appointments/staff_queue.html', {'appointments': appointments})


@login_required
def staff_appointment_decision(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related('doctor', 'doctor__account', 'user'),
        pk=appointment_id,
        status=Appointment.STATUS_PENDING,
        doctor__isnull=False,
    )
    if not _is_appointment_staff(request.user, appointment):
        return HttpResponseForbidden('You do not have permission to process this appointment.')
    if request.method == 'POST':
        form = AppointmentDecisionForm(request.POST, appointment=appointment)
        if form.is_valid():
            decision = form.cleaned_data['decision']
            scheduled_at = form.cleaned_data['scheduled_at']
            with transaction.atomic():
                appointment = Appointment.objects.select_for_update().select_related(
                    'doctor', 'doctor__account', 'user',
                ).get(pk=appointment.pk)
                if appointment.status != Appointment.STATUS_PENDING:
                    messages.error(request, 'This request has already been reviewed.')
                    return redirect('staff_appointment_queue')
                if decision == Appointment.STATUS_ACCEPTED and (
                    not appointment.doctor.is_active
                    or not appointment.requested_date
                    or not _doctor_is_on_duty(appointment.doctor, appointment.requested_date)
                ):
                    form.add_error(None, 'This doctor is no longer marked on duty for the requested date.')
                    return render(request, 'appointments/decision.html', {
                        'appointment': appointment,
                        'form': form,
                    })
                if decision == Appointment.STATUS_ACCEPTED:
                    working_hours = _doctor_schedule(appointment.doctor, appointment.requested_date)
                    appointment_time = timezone.localtime(scheduled_at).time()
                    if not working_hours or not (
                        working_hours[0] <= appointment_time < working_hours[1]
                    ):
                        form.add_error(
                            'scheduled_at',
                            'Choose a time within the doctor’s working hours.',
                        )
                        return render(request, 'appointments/decision.html', {
                            'appointment': appointment,
                            'form': form,
                            'working_hours': working_hours,
                        })
                appointment.status = decision
                appointment.scheduled_at = scheduled_at if decision == Appointment.STATUS_ACCEPTED else None
                appointment.notes = form.cleaned_data['notes']
                appointment.save(update_fields=('status', 'scheduled_at', 'notes'))
                actor_label = (
                    'Administrator' if request.user.is_superuser else 'Office staff'
                ) if request.user.is_staff else 'Assigned doctor'
                AppointmentActivity.objects.create(
                    actor=request.user,
                    appointment=appointment,
                    doctor=appointment.doctor,
                    description=f'{actor_label} {decision} the consultation request.',
                )
                status_label = 'accepted' if decision == Appointment.STATUS_ACCEPTED else 'rejected'
                Notification.objects.create(
                    user=appointment.user,
                    title=f'Appointment request {status_label}',
                    body=(
                        f'Your request with {appointment.doctor.name} was {status_label}. '
                        + (f'Confirmed for {scheduled_at:%B %d, %Y at %I:%M %p}.' if scheduled_at else '')
                        + (f' Office message: {appointment.notes}' if appointment.notes else '')
                        + (
                            ' Your accepted appointment letter is ready to view.'
                            if decision == Appointment.STATUS_ACCEPTED else
                            ' Open your appointment letter for the request details.'
                        )
                    ),
                    url=reverse('appointment_letter', args=(appointment.pk,)),
                )
                if appointment.doctor.account_id and appointment.doctor.account_id != appointment.user_id:
                    Notification.objects.create(
                        user=appointment.doctor.account,
                        title=f'Appointment request {status_label}',
                        body=f'The consultation request for {appointment.requested_date} was {status_label} by the office.',
                        url=reverse('appointment_letter', args=(appointment.pk,)),
                    )
            messages.success(request, f'Appointment request {status_label}. The patient has been notified.')
            return redirect('staff_appointment_queue')
    else:
        form = AppointmentDecisionForm(appointment=appointment)
    return render(request, 'appointments/decision.html', {
        'appointment': appointment,
        'form': form,
        'working_hours': (
            _doctor_schedule(appointment.doctor, appointment.requested_date)
            if appointment.requested_date else None
        ),
    })
