import logging
from datetime import datetime, time

from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
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
        'description': 'Browse source-verified medicine information, including ingredients, side effects, and cautions.'
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


def team(request):
    return render(request, 'core/team.html', {
        'team_members': [
            {'name': 'Pranathi', 'role': 'Co-lead', 'roll_number': '24D01A66u3', 'icon': 'bi-person-workspace'},
            {'name': 'Bhavani', 'role': 'Team partner', 'roll_number': '24D01A66u4', 'icon': 'bi-person'},
            {'name': 'Ashmitha', 'role': 'Team partner', 'roll_number': '24D01A66R5', 'icon': 'bi-person'},
            {'name': 'Mohammad Rehan', 'role': 'Team partner', 'roll_number': '24D01A66T6', 'icon': 'bi-person'},
            {'name': 'Devashish', 'role': 'Team partner', 'roll_number': '24D01A66T4', 'icon': 'bi-person'},
        ],
    })


def terms(request):
    return render(request, 'core/terms.html')


def privacy_policy(request):
    return render(request, 'core/privacy.html')


@login_required
def dashboard(request):
    user = request.user
    all_measurements = list(HealthMeasurement.objects.filter(user=user).order_by('-date')[:7])
    measurements = all_measurements[:5]
    documents = DocumentUpload.objects.filter(user=user).order_by('-created_at')[:3]
    medical_records = MedicalRecord.objects.filter(user=user).order_by('-created_at')[:3]
    upcoming_appointments = Appointment.objects.filter(
        user=user,
        status__in=['scheduled', 'pending', 'accepted'],
    ).order_by('requested_date', 'scheduled_at')[:3]
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
            'url': reverse('measurement_detail', args=(measurement.pk,)),
        })
    for appointment in Appointment.objects.filter(user=user).order_by('-requested_date', '-scheduled_at')[:30]:
        timestamp = appointment.scheduled_at
        if timestamp is None and appointment.requested_date:
            timestamp = timezone.make_aware(
                datetime.combine(appointment.requested_date, time.min),
                timezone.get_current_timezone(),
            )
        if timestamp is None:
            continue
        timeline.append({
            'timestamp': timestamp,
            'kind': 'Appointment',
            'title': appointment.title,
            'detail': appointment.get_status_display(),
            'url': reverse('appointment_letter', args=(appointment.pk,)),
        })
    for record in MedicalRecord.objects.filter(user=user).order_by('-created_at')[:30]:
        timeline.append({
            'timestamp': record.created_at,
            'kind': 'Medical record',
            'title': record.title,
            'detail': record.get_record_type_display(),
            'url': reverse('medical_record_detail', args=(record.pk,)),
        })
    for document in DocumentUpload.objects.filter(user=user).order_by('-created_at')[:30]:
        details = document.extracted_details or {}
        finding_parts = [document.get_review_status_display()]
        medicine_names = [
            item.get('name', '')
            for item in document.extracted_medicines[:3]
            if item.get('name')
        ]
        if medicine_names:
            finding_parts.append('Medicines: ' + ', '.join(medicine_names))
        test_values = [
            f'{item.get("name", "Test")}: {item.get("value", "")} {item.get("unit", "")}'.strip()
            for item in details.get('test_values', [])[:3]
            if item.get('value')
        ]
        if test_values:
            finding_parts.append('Report values: ' + ', '.join(test_values))
        diagnoses = [
            item.get('text', '')
            for item in details.get('diagnosis_mentions', [])[:2]
            if item.get('text')
        ]
        if diagnoses:
            finding_parts.append('Text labeled diagnosis/impression: ' + '; '.join(diagnoses))
        report_dates = details.get('dates', [])[:3]
        if report_dates:
            finding_parts.append('Dates found: ' + ', '.join(report_dates))
        timeline.append({
            'timestamp': document.created_at,
            'kind': 'Uploaded document',
            'title': document.title,
            'detail': ' · '.join(finding_parts),
            'url': reverse('document_text', args=(document.pk,)),
        })
    for notification in Notification.objects.filter(user=user).order_by('-created_at')[:30]:
        timeline.append({
            'timestamp': notification.created_at,
            'kind': 'Activity',
            'title': notification.title,
            'detail': notification.body,
            'url': notification.url or reverse('notification_list'),
        })
    timeline.sort(key=lambda item: item['timestamp'], reverse=True)

    return render(request, 'core/health_profile.html', {
        'timeline': timeline[:100],
        'demo_abha_id': user.demo_abha_id,
        'counts': {
            'measurements': HealthMeasurement.objects.filter(user=user).count(),
            'records': MedicalRecord.objects.filter(user=user).count(),
            'documents': DocumentUpload.objects.filter(user=user).count(),
            'appointments': Appointment.objects.filter(user=user).count(),
        },
    })
