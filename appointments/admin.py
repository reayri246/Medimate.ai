from django.contrib import admin
from django.urls import reverse
from django.utils import timezone

from notifications.models import Notification
from .admin_forms import AppointmentManagementForm
from .forms import DoctorAvailabilityForm, DoctorWorkingDayForm
from .models import (
    Appointment,
    AppointmentActivity,
    AppointmentManagement,
    Doctor,
    DoctorAvailability,
    DoctorWorkingDay,
)


class DoctorAvailabilityInline(admin.TabularInline):
    model = DoctorAvailability
    form = DoctorAvailabilityForm
    extra = 1


class DoctorWorkingDayInline(admin.TabularInline):
    model = DoctorWorkingDay
    form = DoctorWorkingDayForm
    extra = 1


@admin.register(AppointmentManagement)
class AppointmentManagementAdmin(admin.ModelAdmin):
    form = AppointmentManagementForm
    list_display = (
        'title',
        'user',
        'doctor',
        'requested_date',
        'scheduled_at',
        'status',
    )
    list_filter = ('status', 'requested_date', 'doctor__specialty')
    search_fields = ('title', 'user__username', 'user__first_name', 'user__last_name', 'doctor__name')
    fields = (
        'user',
        'doctor',
        'requested_date',
        'symptoms',
        'patient_consent',
        'status',
        'scheduled_at',
        'notes',
    )
    readonly_fields = ('user', 'doctor', 'requested_date', 'symptoms', 'patient_consent')
    date_hierarchy = 'requested_date'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change:
            previous_status = Appointment.objects.only('status').get(pk=obj.pk).status
        super().save_model(request, obj, form, change)

        if obj.status not in (Appointment.STATUS_ACCEPTED, Appointment.STATUS_REJECTED):
            return
        if previous_status == obj.status:
            return

        status_label = 'accepted' if obj.status == Appointment.STATUS_ACCEPTED else 'rejected'
        AppointmentActivity.objects.create(
            actor=request.user,
            appointment=obj,
            doctor=obj.doctor,
            description=f'Administrator {status_label} the consultation request.',
        )
        appointment_url = reverse('appointment_letter', args=(obj.pk,))
        body = f'Your request with {obj.doctor.name if obj.doctor else "the clinic"} was {status_label}.'
        if obj.scheduled_at:
            body += (
                f' Confirmed for '
                f'{timezone.localtime(obj.scheduled_at):%B %d, %Y at %I:%M %p}.'
            )
        body += ' Your appointment letter is ready to view.'
        Notification.objects.create(
            user=obj.user,
            title=f'Appointment request {status_label}',
            body=body,
            url=appointment_url,
        )


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'specialty', 'consultation_office', 'is_active', 'account')
    list_filter = ('specialty', 'is_active')
    search_fields = ('name', 'consultation_office', 'account__username', 'treatable_symptoms')
    fields = (
        'name',
        'specialty',
        'qualifications',
        'photo',
        'treatable_symptoms',
        'consultation_office',
        'reception_email',
        'account',
        'is_active',
    )
    inlines = (DoctorWorkingDayInline, DoctorAvailabilityInline)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        action = 'updated' if change else 'added'
        AppointmentActivity.objects.create(
            actor=request.user,
            doctor=obj,
            description=f'Administrator {action} a doctor profile.',
        )

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        if formset.model in (DoctorAvailability, DoctorWorkingDay):
            AppointmentActivity.objects.create(
                actor=request.user,
                doctor=form.instance,
                description='Administrator updated a doctor’s weekly work schedule or date-specific duty.',
            )


@admin.register(AppointmentActivity)
class AppointmentActivityAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'description', 'appointment', 'doctor')
    list_filter = ('created_at',)
    readonly_fields = ('actor', 'appointment', 'doctor', 'description', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
