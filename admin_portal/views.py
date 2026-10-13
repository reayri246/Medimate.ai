from django.contrib.auth.decorators import login_required
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import User
from appointments.models import Appointment, AppointmentActivity
from health_tracking.models import HealthMeasurement
from notifications.models import Notification
from prescriptions.models import DocumentUpload, PrescriptionAuditLog
from .forms import AdminNotificationForm


@login_required
def portal_home(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden('Administrator access is required.')
    stats = {
        'users': User.objects.count(),
        'appointments': Appointment.objects.count(),
        'pending_appointments': Appointment.objects.filter(status=Appointment.STATUS_PENDING).count(),
        'measurements': HealthMeasurement.objects.count(),
        'documents': DocumentUpload.objects.count(),
    }
    activity = [
        {
            'actor': item.actor,
            'description': item.description,
            'created_at': item.created_at,
            'context': f'Appointment #{item.appointment_id}' if item.appointment_id else (
                f'Doctor: {item.doctor.name}' if item.doctor_id else 'Appointment administration'
            ),
        }
        for item in AppointmentActivity.objects.select_related('actor', 'appointment', 'doctor')[:30]
    ]
    activity.extend(
        {
            'actor': item.actor,
            'description': item.get_action_display(),
            'created_at': item.created_at,
            'context': f'Medical document #{item.document_id}',
        }
        for item in PrescriptionAuditLog.objects.select_related('actor').order_by('-created_at')[:30]
    )
    activity.extend(
        {
            'actor': item.user,
            'description': f'Admin {item.get_action_flag_display().lower()} a {item.content_type.name}.',
            'created_at': item.action_time,
            'context': f'Object #{item.object_id}',
        }
        for item in LogEntry.objects.select_related('user', 'content_type').order_by('-action_time')[:30]
    )
    activity.sort(key=lambda item: item['created_at'], reverse=True)
    return render(request, 'admin_portal/home.html', {
        'stats': stats,
        'recent_activity': activity[:50],
    })


@login_required
def send_notification(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden('Administrator access is required.')

    form = AdminNotificationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        notification_data = {
            'title': data['title'],
            'body': data['body'],
            'url': data['url'],
        }
        with transaction.atomic():
            if data['audience'] == AdminNotificationForm.AUDIENCE_SELECTED:
                recipients = data['recipients']
                recipient_count = recipients.count()
                Notification.objects.bulk_create([
                    Notification(user=user, **notification_data)
                    for user in recipients
                ])
                sent_notification = Notification.objects.filter(
                    user=recipients.first(),
                    title=data['title'],
                ).order_by('-pk').first()
            else:
                recipient_count = 0
                sent_notification = None
                batch = []
                for user in User.objects.filter(is_active=True).only('pk').iterator():
                    batch.append(Notification(user_id=user.pk, **notification_data))
                    if len(batch) == 500:
                        Notification.objects.bulk_create(batch)
                        if sent_notification is None:
                            sent_notification = batch[0]
                        recipient_count += len(batch)
                        batch = []
                if batch:
                    Notification.objects.bulk_create(batch)
                    if sent_notification is None:
                        sent_notification = batch[0]
                    recipient_count += len(batch)
            if sent_notification is not None:
                LogEntry.objects.create(
                    user=request.user,
                    content_type=ContentType.objects.get_for_model(Notification),
                    object_id=str(sent_notification.pk),
                    object_repr=f'Notification campaign: {data["title"]} ({recipient_count} recipient(s))',
                    action_flag=ADDITION,
                    change_message='Admin-created in-app notification; message body omitted from activity log.',
                )

        messages.success(request, f'Notification sent to {recipient_count} active user(s).')
        return redirect('admin_send_notification')

    return render(request, 'admin_portal/notifications.html', {'form': form})


@login_required
def document_detail(request, document_id):
    if not request.user.is_superuser:
        return HttpResponseForbidden('Administrator access is required.')
    document = get_object_or_404(
        DocumentUpload.objects.select_related('user'),
        pk=document_id,
    )
    PrescriptionAuditLog.objects.create(
        document=document,
        actor=request.user,
        action=PrescriptionAuditLog.ACTION_VIEWED,
        metadata={'access_method': 'administrator_record_view'},
    )
    response = render(request, 'admin_portal/document_detail.html', {
        'document': document,
        'download_url': reverse('admin_document_download', args=(document.pk,)),
    })
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def document_download(request, document_id):
    if not request.user.is_superuser:
        return HttpResponseForbidden('Administrator access is required.')
    document = get_object_or_404(DocumentUpload, pk=document_id)
    try:
        document.file.open('rb')
    except (FileNotFoundError, OSError) as exc:
        raise Http404('The requested document is unavailable.') from exc

    PrescriptionAuditLog.objects.create(
        document=document,
        actor=request.user,
        action=PrescriptionAuditLog.ACTION_DOWNLOADED,
        metadata={'access_method': 'administrator_record_download'},
    )
    response = FileResponse(
        document.file,
        as_attachment=True,
        filename=document.file.name.rsplit('/', 1)[-1],
        content_type='application/octet-stream',
    )
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
