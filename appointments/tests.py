from datetime import timedelta
from io import BytesIO
import tempfile

from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import User
from notifications.models import Notification

from .forms import DoctorAvailabilityForm, DoctorWorkingDayForm
from .models import Appointment, AppointmentActivity, Doctor, DoctorAvailability, DoctorWorkingDay


class SymptomAppointmentTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='patient',
            email='patient@example.test',
            password='test-password-123',
        )
        self.staff = User.objects.create_user(
            username='reception',
            email='reception@example.test',
            password='test-password-123',
            is_staff=True,
        )
        self.doctor_user = User.objects.create_user(
            username='doctor',
            email='doctor@example.test',
            password='test-password-123',
        )
        self.requested_date = timezone.localdate() + timedelta(days=3)
        self.doctor = Doctor.objects.create(
            name='Dr. Skin',
            specialty='dermatology',
            qualifications='MD',
            treatable_symptoms='rash, itchy skin',
            consultation_office='North Clinic',
            reception_email='desk@example.test',
            account=self.doctor_user,
        )
        DoctorAvailability.objects.create(
            doctor=self.doctor,
            date=self.requested_date,
            is_on_duty=True,
        )
        self.client.force_login(self.patient)

    def find_doctors(self, symptoms='red itchy rash'):
        return self.client.post(reverse('appointment_request'), {
            'step': 'find',
            'symptoms': symptoms,
            'requested_date': self.requested_date.isoformat(),
        })

    def select_doctor(self, symptoms='red itchy rash'):
        return self.client.post(reverse('appointment_request'), {
            'step': 'choose',
            'symptoms': symptoms,
            'requested_date': self.requested_date.isoformat(),
            'doctor': self.doctor.pk,
        })

    def submit_request(self, symptoms='red itchy rash'):
        return self.client.post(reverse('appointment_request'), {
            'step': 'confirm',
            'symptoms': symptoms,
            'requested_date': self.requested_date.isoformat(),
            'doctor': self.doctor.pk,
            'consent': 'on',
        })

    def test_suggests_only_matching_doctors_on_duty_for_selected_date(self):
        off_duty = Doctor.objects.create(
            name='Dr. Off Duty',
            specialty='dermatology',
            consultation_office='North Clinic',
        )
        DoctorAvailability.objects.create(
            doctor=off_duty,
            date=self.requested_date,
            is_on_duty=False,
        )
        wrong_specialty = Doctor.objects.create(
            name='Dr. Heart',
            specialty='cardiology',
            consultation_office='Heart Clinic',
        )
        DoctorAvailability.objects.create(
            doctor=wrong_specialty,
            date=self.requested_date,
            is_on_duty=True,
        )
        unmatched_same_specialty = Doctor.objects.create(
            name='Dr. Acne Only',
            specialty='dermatology',
            treatable_symptoms='acne',
            consultation_office='North Clinic',
        )
        DoctorAvailability.objects.create(
            doctor=unmatched_same_specialty,
            date=self.requested_date,
            is_on_duty=True,
        )

        response = self.find_doctors()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dr. Skin')
        self.assertNotContains(response, 'Dr. Off Duty')
        self.assertNotContains(response, 'Dr. Heart')
        self.assertNotContains(response, 'Dr. Acne Only')
        self.assertContains(response, 'Matched consultation terms: rash')
        self.assertContains(response, 'Working hours:')
        self.assertContains(response, '9:00 AM–5:00 PM')
        self.assertContains(response, 'doctor-match-list')
        self.assertContains(response, 'doctor-match-card')
        self.assertEqual(Appointment.objects.count(), 0)

    def test_admin_configured_symptom_terms_are_used_as_match_source(self):
        self.doctor.treatable_symptoms = 'itchy skin; eczema flare'
        self.doctor.save(update_fields=('treatable_symptoms',))

        response = self.find_doctors('My itchy skin is bothering me')

        self.assertContains(response, 'Dr. Skin')
        self.assertContains(response, 'Matched consultation terms: itchy skin')

        response = self.find_doctors('I have a fever')
        self.assertNotContains(response, 'Dr. Skin')

    def test_compound_admin_symptom_term_matches_common_word_form(self):
        self.doctor.treatable_symptoms = 'chronic and severe headaches, memory loss, confusion'
        self.doctor.save(update_fields=('treatable_symptoms',))

        response = self.find_doctors('I have a headache')

        self.assertContains(response, 'Dr. Skin')
        self.assertContains(response, 'Matched consultation terms: chronic and severe headaches')

    def test_explains_when_no_doctor_has_on_duty_entry_for_date(self):
        DoctorAvailability.objects.filter(
            doctor=self.doctor,
            date=self.requested_date,
        ).delete()

        response = self.find_doctors()

        self.assertContains(response, 'No doctors are marked on duty for this date')
        self.assertContains(response, 'A doctor profile alone does not set a work schedule')

    def test_recurring_working_day_makes_matching_doctor_available(self):
        DoctorAvailability.objects.filter(
            doctor=self.doctor,
            date=self.requested_date,
        ).delete()
        DoctorWorkingDay.objects.create(
            doctor=self.doctor,
            weekday=self.requested_date.weekday(),
        )

        response = self.find_doctors()

        self.assertContains(response, 'Dr. Skin')
        self.assertContains(response, 'Matched consultation terms: rash')

    def test_date_specific_off_duty_overrides_recurring_workday(self):
        DoctorWorkingDay.objects.create(
            doctor=self.doctor,
            weekday=self.requested_date.weekday(),
        )
        DoctorAvailability.objects.update_or_create(
            doctor=self.doctor,
            date=self.requested_date,
            defaults={'is_on_duty': False},
        )

        response = self.find_doctors()

        self.assertNotContains(response, 'Dr. Skin')
        self.assertContains(response, 'No doctors are marked on duty for this date')

    @override_settings(DEBUG=True)
    def test_seed_data_creates_demo_doctors_for_every_specialty_with_workdays_idempotently(self):
        call_command('seed_data')
        initial_demo_doctor_count = Doctor.objects.filter(name__startswith='DEMO - Dr.').count()
        call_command('seed_data')

        demo_doctors = Doctor.objects.filter(name__startswith='DEMO - Dr.')
        self.assertEqual(initial_demo_doctor_count, len(Doctor.SPECIALTY_CHOICES))
        self.assertEqual(demo_doctors.count(), len(Doctor.SPECIALTY_CHOICES))
        self.assertEqual(
            set(demo_doctors.values_list('specialty', flat=True)),
            {specialty for specialty, _ in Doctor.SPECIALTY_CHOICES},
        )
        self.assertTrue(all(
            3 <= doctor.working_days.count() <= 6
            for doctor in demo_doctors
        ))
        neurologist = demo_doctors.get(specialty='neurology')
        self.assertEqual(neurologist.working_days.count(), 6)
        self.assertTrue(neurologist.working_days.filter(weekday=1).exists())

    def test_emergency_phrase_directs_user_to_emergency_care(self):
        response = self.find_doctors('I have severe chest pain')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'seek emergency care now')
        self.assertNotContains(response, 'Dr. Skin')
        self.assertEqual(Appointment.objects.count(), 0)

    def test_separate_consent_is_required_to_submit_request(self):
        response = self.find_doctors()
        self.assertContains(response, 'Dr. Skin')

        response = self.select_doctor()
        self.assertContains(response, 'I give permission to share these symptoms')

        response = self.client.post(reverse('appointment_request'), {
            'step': 'confirm',
            'symptoms': 'red itchy rash',
            'requested_date': self.requested_date.isoformat(),
            'doctor': self.doctor.pk,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This field is required.')
        self.assertEqual(Appointment.objects.count(), 0)

    def test_consented_request_is_sent_to_office_and_letter_is_private(self):
        response = self.submit_request()

        self.assertRedirects(response, reverse('appointment_list'))
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.user, self.patient)
        self.assertEqual(appointment.doctor, self.doctor)
        self.assertEqual(appointment.requested_date, self.requested_date)
        self.assertEqual(appointment.status, Appointment.STATUS_PENDING)
        self.assertTrue(appointment.patient_consent)
        self.assertEqual(appointment.symptoms, 'red itchy rash')
        self.assertEqual(AppointmentActivity.objects.filter(appointment=appointment).count(), 1)
        self.assertTrue(Notification.objects.filter(user=self.staff, url=reverse('staff_appointment_queue')).exists())
        self.assertTrue(Notification.objects.filter(user=self.doctor_user, url=reverse('staff_appointment_queue')).exists())
        self.assertTrue(Notification.objects.filter(user=self.patient, url=reverse(
            'appointment_letter', args=(appointment.pk,),
        )).exists())

        response = self.client.get(reverse('appointment_letter', args=(appointment.pk,)))
        self.assertContains(response, 'North Clinic')
        self.assertContains(response, 'red itchy rash')
        self.assertContains(response, 'Print / Save as PDF')

        other_patient = User.objects.create_user(username='other', password='test-password-123')
        self.client.force_login(other_patient)
        response = self.client.get(reverse('appointment_letter', args=(appointment.pk,)))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_accept_and_patient_gets_appointment_letter_notification(self):
        self.submit_request()
        appointment = Appointment.objects.get()
        self.client.force_login(self.staff)
        scheduled_at = (timezone.localtime() + timedelta(days=3)).replace(
            hour=10,
            minute=30,
            second=0,
            microsecond=0,
        )
        response = self.client.post(
            reverse('staff_appointment_decision', args=(appointment.pk,)),
            {
                'decision': Appointment.STATUS_ACCEPTED,
                'scheduled_at': scheduled_at.strftime('%Y-%m-%dT%H:%M'),
                'notes': 'Please arrive 10 minutes early.',
            },
        )

        self.assertRedirects(response, reverse('staff_appointment_queue'))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_ACCEPTED)
        self.assertEqual(appointment.scheduled_at, scheduled_at)
        notification = Notification.objects.get(
            user=self.patient,
            title='Appointment request accepted',
        )
        self.assertEqual(
            notification.url,
            reverse('appointment_letter', args=(appointment.pk,)),
        )
        self.assertIn('accepted appointment letter is ready', notification.body)
        self.client.force_login(self.patient)
        patient_notifications = self.client.get(reverse('notification_list'))
        self.assertContains(patient_notifications, 'Appointment request accepted')
        self.assertContains(patient_notifications, 'Open details')
        notification_open_url = reverse('notification_open', args=(notification.pk,))
        self.assertContains(patient_notifications, notification_open_url)
        response = self.client.get(notification_open_url)
        self.assertRedirects(response, notification.url)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertEqual(AppointmentActivity.objects.filter(appointment=appointment).count(), 2)

    def test_linked_doctor_can_accept_and_patient_gets_letter_notification(self):
        self.submit_request()
        appointment = Appointment.objects.get()
        self.client.force_login(self.doctor_user)
        scheduled_at = (timezone.localtime() + timedelta(days=3)).replace(
            hour=10,
            minute=30,
            second=0,
            microsecond=0,
        )

        response = self.client.post(
            reverse('staff_appointment_decision', args=(appointment.pk,)),
            {
                'decision': Appointment.STATUS_ACCEPTED,
                'scheduled_at': scheduled_at.strftime('%Y-%m-%dT%H:%M'),
            },
        )

        self.assertRedirects(response, reverse('staff_appointment_queue'))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_ACCEPTED)
        notification = Notification.objects.get(
            user=self.patient,
            title='Appointment request accepted',
        )
        self.assertEqual(notification.url, reverse('appointment_letter', args=(appointment.pk,)))

    def test_administrator_can_accept_and_patient_gets_letter_notification(self):
        self.submit_request()
        appointment = Appointment.objects.get()
        admin = User.objects.create_superuser(
            username='appointment-admin',
            email='admin@example.test',
            password='test-password-123',
        )
        self.client.force_login(admin)
        scheduled_at = (timezone.localtime() + timedelta(days=3)).replace(
            hour=10,
            minute=30,
            second=0,
            microsecond=0,
        )

        response = self.client.post(
            reverse('staff_appointment_decision', args=(appointment.pk,)),
            {
                'decision': Appointment.STATUS_ACCEPTED,
                'scheduled_at': scheduled_at.strftime('%Y-%m-%dT%H:%M'),
            },
        )

        self.assertRedirects(response, reverse('staff_appointment_queue'))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_ACCEPTED)
        notification = Notification.objects.get(
            user=self.patient,
            title='Appointment request accepted',
        )
        self.assertEqual(notification.url, reverse('appointment_letter', args=(appointment.pk,)))
        self.assertTrue(AppointmentActivity.objects.filter(
            appointment=appointment,
            actor=admin,
            description__startswith='Administrator accepted',
        ).exists())

    def test_staff_can_reject_and_notify_patient(self):
        self.submit_request()
        appointment = Appointment.objects.get()
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse('staff_appointment_decision', args=(appointment.pk,)),
            {'decision': Appointment.STATUS_REJECTED, 'notes': 'Please select another date.'},
        )

        self.assertRedirects(response, reverse('staff_appointment_queue'))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_REJECTED)
        self.assertTrue(Notification.objects.filter(
            user=self.patient,
            title='Appointment request rejected',
        ).exists())

    def test_linked_doctor_can_process_only_their_own_request(self):
        self.submit_request()
        appointment = Appointment.objects.get()
        self.client.force_login(self.doctor_user)

        self.assertEqual(self.client.get(reverse('staff_appointment_queue')).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('staff_appointment_decision', args=(appointment.pk,))).status_code,
            200,
        )

    def test_admin_can_manage_doctor_profiles_and_duty_dates(self):
        admin = User.objects.create_superuser(
            username='catalog-admin',
            email='admin@example.test',
            password='test-password-123',
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('admin:appointments_doctor_add'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Consultation office')
        self.assertContains(response, 'Specialty')
        self.assertContains(response, 'Treatable symptoms')
        self.assertIn('photo', response.context['adminform'].form.fields)
        self.assertIn(
            'separated by commas or new lines',
            response.context['adminform'].form.fields['treatable_symptoms'].help_text,
        )
        self.assertContains(response, 'Doctor working days')
        self.assertContains(response, 'Is on duty')
        self.assertContains(response, 'Start time')
        self.assertContains(response, 'End time')
        self.assertContains(response, '12-hour time with AM or PM')
        self.assertIn('AM', DoctorWorkingDayForm().fields['start_time'].widget.attrs['title'])
        self.assertIn('PM', DoctorWorkingDayForm().fields['start_time'].widget.attrs['title'])
        self.assertEqual(
            DoctorWorkingDayForm().fields['start_time'].clean('02:30 PM').hour,
            14,
        )
        self.assertEqual(
            DoctorAvailabilityForm().fields['end_time'].clean('05:45 AM').hour,
            5,
        )
        with self.assertRaises(ValidationError):
            DoctorWorkingDayForm().fields['start_time'].clean('14:30')

    def test_appointment_management_is_a_dedicated_admin_branch(self):
        admin = User.objects.create_superuser(
            username='appointment-admin',
            email='admin@example.test',
            password='test-password-123',
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('admin:appointments_appointmentmanagement_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Appointment management')

    def test_admin_acceptance_notifies_patient_with_appointment_letter(self):
        self.submit_request()
        appointment = Appointment.objects.get()
        admin = User.objects.create_superuser(
            username='appointment-admin',
            email='admin@example.test',
            password='test-password-123',
        )
        self.client.force_login(admin)
        scheduled_at = (timezone.localtime() + timedelta(days=3)).replace(
            hour=10,
            minute=30,
            second=0,
            microsecond=0,
        )

        response = self.client.post(
            reverse('admin:appointments_appointmentmanagement_change', args=(appointment.pk,)),
            {
                'status': Appointment.STATUS_ACCEPTED,
                'scheduled_at': scheduled_at.strftime('%Y-%m-%dT%H:%M'),
                'notes': 'Please arrive on time.',
                '_save': 'Save',
            },
        )

        self.assertEqual(
            response.status_code,
            302,
            getattr(response.context.get('adminform'), 'form', None).errors
            if response.context else None,
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_ACCEPTED)
        self.assertEqual(appointment.scheduled_at, scheduled_at)
        notification = Notification.objects.get(
            user=self.patient,
            title='Appointment request accepted',
        )
        self.assertEqual(notification.url, reverse('appointment_letter', args=(appointment.pk,)))
        self.assertTrue(AppointmentActivity.objects.filter(
            actor=admin,
            appointment=appointment,
            description__startswith='Administrator accepted',
        ).exists())

    def test_admin_rejection_notifies_patient_with_appointment_letter(self):
        self.submit_request()
        appointment = Appointment.objects.get()
        admin = User.objects.create_superuser(
            username='appointment-admin',
            email='admin@example.test',
            password='test-password-123',
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse('admin:appointments_appointmentmanagement_change', args=(appointment.pk,)),
            {
                'status': Appointment.STATUS_REJECTED,
                'scheduled_at': '',
                'notes': 'Please contact the office to choose another date.',
                '_save': 'Save',
            },
        )

        self.assertEqual(response.status_code, 302)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_REJECTED)
        notification = Notification.objects.get(
            user=self.patient,
            title='Appointment request rejected',
        )
        self.assertEqual(notification.url, reverse('appointment_letter', args=(appointment.pk,)))

    def test_doctor_photo_is_shown_in_matching_results(self):
        media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(media_directory.cleanup)
        image_buffer = BytesIO()
        Image.new('RGB', (8, 8), color='white').save(image_buffer, format='PNG')
        with override_settings(MEDIA_ROOT=media_directory.name):
            self.doctor.photo.save(
                'doctor.png',
                SimpleUploadedFile(
                    'doctor.png',
                    image_buffer.getvalue(),
                    content_type='image/png',
                ),
                save=True,
            )
            response = self.find_doctors()

        self.assertContains(response, f'src="{self.doctor.photo.url}"')
        self.assertContains(response, f'alt="Profile photo of {self.doctor.name}"')

    def test_accept_requires_availability_and_time_on_requested_date(self):
        self.submit_request()
        appointment = Appointment.objects.get()
        self.client.force_login(self.staff)
        another_day = (timezone.localtime() + timedelta(days=4)).replace(
            hour=10,
            minute=30,
            second=0,
            microsecond=0,
        )

        response = self.client.post(
            reverse('staff_appointment_decision', args=(appointment.pk,)),
            {
                'decision': Appointment.STATUS_ACCEPTED,
                'scheduled_at': another_day.strftime('%Y-%m-%dT%H:%M'),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'must be on the patient’s requested date')
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_PENDING)

    def test_appointment_acceptance_requires_duty_on_requested_day(self):
        self.submit_request()
        appointment = Appointment.objects.get()
        self.client.force_login(self.staff)
        DoctorAvailability.objects.filter(
            doctor=self.doctor,
            date=self.requested_date,
        ).update(is_on_duty=False)
        requested_day = (timezone.localtime() + timedelta(days=3)).replace(
            hour=10,
            minute=30,
            second=0,
            microsecond=0,
        )

        response = self.client.post(
            reverse('staff_appointment_decision', args=(appointment.pk,)),
            {
                'decision': Appointment.STATUS_ACCEPTED,
                'scheduled_at': requested_day.strftime('%Y-%m-%dT%H:%M'),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer marked on duty')
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_PENDING)

    def test_appointment_acceptance_must_be_within_doctor_working_hours(self):
        self.submit_request()
        appointment = Appointment.objects.get()
        self.client.force_login(self.staff)
        scheduled_at = (timezone.localtime() + timedelta(days=3)).replace(
            hour=18,
            minute=0,
            second=0,
            microsecond=0,
        )

        response = self.client.post(
            reverse('staff_appointment_decision', args=(appointment.pk,)),
            {
                'decision': Appointment.STATUS_ACCEPTED,
                'scheduled_at': scheduled_at.strftime('%Y-%m-%dT%H:%M'),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose a time within the doctor’s working hours')
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_PENDING)

    def test_reminder_command_notifies_confirmed_appointment_once(self):
        appointment_time = timezone.now() + timedelta(hours=2)
        appointment = Appointment.objects.create(
            user=self.patient,
            doctor=self.doctor,
            title='Consultation',
            requested_date=timezone.localdate() + timedelta(days=1),
            scheduled_at=appointment_time,
            status=Appointment.STATUS_ACCEPTED,
        )

        call_command('send_appointment_reminders')
        call_command('send_appointment_reminders')

        self.assertEqual(
            Notification.objects.filter(user=self.patient, title='Appointment reminder').count(),
            1,
        )
        appointment.refresh_from_db()
        self.assertIsNotNone(appointment.reminder_notified_at)
