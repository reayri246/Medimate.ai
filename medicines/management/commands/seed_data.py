from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify
from django.utils import timezone

from accounts.models import User
from appointments.models import Appointment, Doctor, DoctorWorkingDay
from health_tracking.models import HealthMeasurement
from medical_records.models import MedicalRecord
from medicines.models import Medicine
from notifications.models import Notification
from prescriptions.models import DocumentUpload


class Command(BaseCommand):
    help = 'Seed the project with sample healthcare data.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Sample healthcare data must not be seeded in production.')

        user, created = User.objects.get_or_create(
            username='demo_patient',
            defaults={'email': 'demo@example.com', 'first_name': 'Devashish', 'role': User.ROLE_PATIENT}
        )
        if created:
            user.first_name = 'Devashish'
            user.set_password('demo12345')
            user.save()
        elif user.first_name != 'Devashish':
            user.first_name = 'Devashish'
            user.save(update_fields=['first_name'])
        if not user.demo_abha_id:
            user.demo_abha_id = f'DEMO-ABHA-{user.pk:08d}'
            user.save(update_fields=['demo_abha_id'])

        sample_doctors = [
            ('general-practice', 'fever, cold, fatigue, body aches'),
            ('cardiology', 'palpitations, irregular heartbeat, blood pressure concerns'),
            ('dermatology', 'rash, itchy skin, acne, eczema'),
            ('ent', 'earache, sore throat, sinus congestion, hearing concerns'),
            ('gastroenterology', 'stomach pain, nausea, vomiting, diarrhea, constipation'),
            ('gynecology', 'menstrual concerns, pelvic pain, pregnancy questions'),
            ('neurology', 'headaches, migraine, memory loss, nerve pain, numbness, muscle weakness'),
            ('ophthalmology', 'eye pain, blurry vision, vision changes, red eyes'),
            ('orthopedics', 'joint pain, back pain, knee pain, bone injury'),
            ('pediatrics', 'child fever, child cough, infant feeding concerns'),
            ('psychiatry', 'anxiety, panic, depression, mood concerns'),
            ('pulmonology', 'persistent cough, wheezing, asthma, breathing concerns'),
        ]
        three_day_schedule = (0, 2, 4)
        six_day_schedule = (0, 1, 2, 3, 4, 5)
        for index, (specialty, treatable_symptoms) in enumerate(sample_doctors):
            specialty_label = dict(Doctor.SPECIALTY_CHOICES)[specialty]
            doctor, _ = Doctor.objects.get_or_create(
                name=f'DEMO - Dr. {specialty_label}',
                defaults={
                    'specialty': specialty,
                    'qualifications': 'Sample profile — not a real doctor',
                    'treatable_symptoms': treatable_symptoms,
                    'consultation_office': 'DEMO consultation office',
                    'is_active': True,
                },
            )
            workdays = six_day_schedule if index % 2 or specialty == 'neurology' else three_day_schedule
            for weekday in workdays:
                DoctorWorkingDay.objects.get_or_create(doctor=doctor, weekday=weekday)

        medicine_data = [
            {
                'name': 'DEMO - Paracetamol (unverified)',
                'active_ingredient': 'Unverified demo data - confirm in a trusted source',
                'dosage_form': 'Unverified demo data',
                'strength': '',
                'category': 'demo-unverified',
                'description': 'DEMO ONLY. This placeholder is not verified medical information.',
                'warnings': '',
                'side_effects': '',
                'interactions': '',
                'contraindications': '',
            },
            {
                'name': 'DEMO - Ibuprofen (unverified)',
                'active_ingredient': 'Unverified demo data - confirm in a trusted source',
                'dosage_form': 'Unverified demo data',
                'strength': '',
                'category': 'demo-unverified',
                'description': 'DEMO ONLY. This placeholder is not verified medical information.',
                'warnings': '',
                'side_effects': '',
                'interactions': '',
                'contraindications': '',
            },
            {
                'name': 'DEMO - Amoxicillin (unverified)',
                'active_ingredient': 'Unverified demo data - confirm in a trusted source',
                'dosage_form': 'Unverified demo data',
                'strength': '',
                'category': 'demo-unverified',
                'description': 'DEMO ONLY. This placeholder is not verified medical information.',
                'warnings': '',
                'side_effects': '',
                'interactions': '',
                'contraindications': '',
            },
        ]

        for item in medicine_data:
            Medicine.objects.get_or_create(
                slug=slugify(item['name']),
                defaults={
                    **item,
                    'source_name': '',
                    'source_url': '',
                    'safety_data_verified': False,
                },
            )

        measurement_samples = [
            (14, '69.1', '120/78', 74, '36.7', 94),
            (10, '68.9', '119/77', 73, '36.6', 95),
            (7, '68.8', '121/78', 75, '36.8', 97),
            (5, '68.7', '118/76', 72, '36.7', 96),
            (3, '68.6', '120/77', 74, '36.8', 95),
            (2, '68.5', '118/76', 72, '36.8', 96),
            (1, '68.5', '118/76', 72, '36.8', 96),
        ]
        for days_ago, weight, blood_pressure, heart_rate, temperature, glucose in measurement_samples:
            HealthMeasurement.objects.update_or_create(
                user=user,
                date=timezone.localdate() - timedelta(days=days_ago),
                defaults={
                    'weight_kg': weight,
                    'blood_pressure': blood_pressure,
                    'heart_rate': heart_rate,
                    'temperature_c': temperature,
                    'glucose_mgdl': glucose,
                    'notes': 'Illustrative sample only; replace with your own measurement.',
                },
            )

        appointment_samples = [
            ('Routine health check-in', 3, 'Review general wellness questions.'),
            ('Follow-up clinic review', 8, 'Discuss questions with your healthcare professional.'),
            ('Dental check-up', 21, 'Routine preventive visit.'),
        ]
        for title, days_ahead, notes in appointment_samples:
            Appointment.objects.update_or_create(
                user=user,
                title=title,
                defaults={
                    'scheduled_at': timezone.now() + timedelta(days=days_ahead),
                    'status': Appointment.STATUS_SCHEDULED,
                    'notes': f'SAMPLE APPOINTMENT. {notes}',
                },
            )

        activity_samples = [
            ('Sample health check-in', 'A sample measurement was added to your health tracking history.'),
            ('Sample appointment scheduled', 'A demonstration appointment was added to your calendar.'),
            ('Sample record added', 'An illustrative medical record was added for the demo profile.'),
            ('Sample appointment reminder', 'SAMPLE ONLY. This is a demonstration reminder; confirm actual appointment details with your care team.'),
            ('Sample report ready', 'SAMPLE ONLY. A demonstration report was added to the records page. Always check reports against the original document.'),
        ]
        for title, body in activity_samples:
            Notification.objects.update_or_create(
                user=user,
                title=title,
                defaults={'body': f'SAMPLE ACTIVITY. {body}', 'is_read': False},
            )

        medical_record_samples = [
            ('Sample wellness check-in', 'summary', 'Illustrative demo record only. No real examination or diagnosis is represented. Replace this with information provided by your clinician.'),
            ('Sample blood test note', 'lab', 'Illustrative demo record only. No real laboratory result is represented. Enter verified results from your healthcare provider.'),
            ('Sample clinic visit notes', 'visit', 'Illustrative demo record only. This is not a real visit summary or medical advice.'),
        ]
        for title, record_type, notes in medical_record_samples:
            MedicalRecord.objects.get_or_create(
                user=user,
                title=title,
                defaults={'record_type': record_type, 'notes': notes},
            )

        DocumentUpload.objects.update_or_create(
            user=user,
            title='Prescription summary',
            defaults={
                'file': 'documents/demo.txt',
                'extracted_text': 'Demonstration document content only. No real prescription instructions.',
                'review_status': DocumentUpload.REVIEW_PENDING,
            }
        )

        self.stdout.write(self.style.SUCCESS('Sample data created.'))
