import logging
from datetime import datetime, time

from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from appointments.models import Appointment
from health_tracking.models import HealthMeasurement
from medical_records.models import MedicalRecord
from medicines.models import Medicine
from notifications.models import Notification
from prescriptions.models import DocumentUpload


FEATURES = [
    {
        'title': 'Prescription Review',
        'icon': 'bi-file-earmark-text',
        'description': 'Upload prescriptions and reports, then review extracted text for key medication and instruction details.'
    },
    {
        'title': 'Medicine Database',
        'icon': 'bi-capsule',
        'description': 'Search curated medicine information, side effects, and known cautions before starting a new treatment.'
    },
    {
        'title': 'MediGuard AI',
        'icon': 'bi-shield-check',
        'description': 'Get cautious, deterministic checks for medication risk and symptom urgency using rule-based guidance.'
    },
    {
        'title': 'Health Tracking',
        'icon': 'bi-heart-pulse',
        'description': 'Track blood pressure, weight, glucose, heart rate, and other daily health markers in one place.'
    },
    {
        'title': 'Appointments',
        'icon': 'bi-calendar2-check',
        'description': 'View upcoming care visits, medication reviews, and health follow-ups without leaving the dashboard.'
    },
    {
        'title': 'Records Privacy',
        'icon': 'bi-lock',
        'description': 'Keep your personal care history, notes, and records in a privately managed environment.'
    },
]
logger = logging.getLogger(__name__)


def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except DatabaseError:
        logger.exception('Health check failed because the database is unavailable.')
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok'})


def home(request):
    return render(request, 'core/home.html', {'features': FEATURES})


@login_required
def dashboard(request):
    user = request.user
    all_measurements = list(HealthMeasurement.objects.filter(user=user).order_by('-date')[:7])
    measurements = all_measurements[:5]
    documents = DocumentUpload.objects.filter(user=user).order_by('-created_at')[:3]
    medical_records = MedicalRecord.objects.filter(user=user).order_by('-created_at')[:3]
    upcoming_appointments = Appointment.objects.filter(user=user, status__in=['scheduled', 'pending']).order_by('scheduled_at')[:3]
    notifications = Notification.objects.filter(user=user).order_by('-created_at')[:5]
    unread_notifications = Notification.objects.filter(user=user, is_read=False).count()
    total_medicines = Medicine.objects.count()
    total_measurements = HealthMeasurement.objects.filter(user=user).count()
    total_documents = DocumentUpload.objects.filter(user=user).count()
    total_medical_records = MedicalRecord.objects.filter(user=user).count()
    total_appointments = Appointment.objects.filter(user=user).count()
    recent_measurement = all_measurements[0] if all_measurements else None
    chart_measurements = list(reversed(all_measurements))
    chart_data = {
        'labels': [f'{measurement.date:%b} {measurement.date.day}' for measurement in chart_measurements],
        'systolic': [
            int(measurement.blood_pressure.split('/')[0])
            if measurement.blood_pressure and measurement.blood_pressure.split('/')[0].isdigit()
            else None
            for measurement in chart_measurements
        ],
        'heart_rate': [measurement.heart_rate for measurement in chart_measurements],
        'weight': [
            float(measurement.weight_kg) if measurement.weight_kg is not None else None
            for measurement in chart_measurements
        ],
    }

    return render(
        request,
        'core/dashboard.html',
        {
            'measurements': measurements,
            'documents': documents,
            'medical_records': medical_records,
            'upcoming_appointments': upcoming_appointments,
            'notifications': notifications,
            'total_medicines': total_medicines,
            'total_measurements': total_measurements,
            'total_documents': total_documents,
            'total_medical_records': total_medical_records,
            'total_appointments': total_appointments,
            'recent_measurement': recent_measurement,
            'unread_notifications': unread_notifications,
            'chart_data': chart_data,
        },
    )


@login_required
def health_profile(request):
    user = request.user
    timeline = []
    for measurement in HealthMeasurement.objects.filter(user=user).order_by('-date')[:30]:
        timestamp = timezone.make_aware(
            datetime.combine(measurement.date, time.min),
            timezone.get_current_timezone(),
        )
        detail_parts = []
        if measurement.blood_pressure:
            detail_parts.append(f'BP {measurement.blood_pressure}')
        if measurement.heart_rate:
            detail_parts.append(f'{measurement.heart_rate} bpm')
        if measurement.weight_kg is not None:
            detail_parts.append(f'{measurement.weight_kg} kg')
        timeline.append({
            'timestamp': timestamp,
            'kind': 'Measurement',
            'title': 'Health measurement',
            'detail': ' · '.join(detail_parts) or measurement.notes,
        })
    for appointment in Appointment.objects.filter(user=user).order_by('-scheduled_at')[:30]:
        timeline.append({
            'timestamp': appointment.scheduled_at,
            'kind': 'Appointment',
            'title': appointment.title,
            'detail': appointment.get_status_display(),
        })
    for record in MedicalRecord.objects.filter(user=user).order_by('-created_at')[:30]:
        timeline.append({
            'timestamp': record.created_at,
            'kind': 'Medical record',
            'title': record.title,
            'detail': record.get_record_type_display(),
        })
    for document in DocumentUpload.objects.filter(user=user).order_by('-created_at')[:30]:
        timeline.append({
            'timestamp': document.created_at,
            'kind': 'Uploaded document',
            'title': document.title,
            'detail': document.get_review_status_display(),
        })
    for notification in Notification.objects.filter(user=user).order_by('-created_at')[:30]:
        timeline.append({
            'timestamp': notification.created_at,
            'kind': 'Activity',
            'title': notification.title,
            'detail': notification.body,
        })
    timeline.sort(key=lambda item: item['timestamp'], reverse=True)

    return render(request, 'core/health_profile.html', {
        'timeline': timeline[:100],
        'demo_abha_id': user.demo_abha_id,
    })
