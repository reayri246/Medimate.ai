from django.contrib import admin, messages
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import path, reverse

from accounts.models import User
from admin_portal.forms import AdminNotificationForm
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('title', 'body', 'user__username', 'user__email')
    readonly_fields = ('user', 'title', 'body', 'url', 'is_read', 'created_at')
    change_list_template = 'admin/notifications/notification/change_list.html'

    def get_urls(self):
        custom_urls = [
            path(
                'send/',
                self.admin_site.admin_view(self.send_notifications),
                name='notifications_notification_send',
            ),
        ]
        return custom_urls + super().get_urls()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def send_notifications(self, request):
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
                    recipients = list(data['recipients'])
                else:
                    recipients = None

                if recipients is None:
                    batch = []
                    recipient_count = 0
                    first_notification = None
                    for user in User.objects.filter(is_active=True).only('pk').iterator():
                        batch.append(Notification(user_id=user.pk, **notification_data))
                        if len(batch) >= 500:
                            Notification.objects.bulk_create(batch)
                            if first_notification is None:
                                first_notification = batch[0]
                            recipient_count += len(batch)
                            batch = []
                    if batch:
                        Notification.objects.bulk_create(batch)
                        if first_notification is None:
                            first_notification = batch[0]
                        recipient_count += len(batch)
                else:
                    recipient_count = len(recipients)
                    notices = [
                        Notification(user=user, **notification_data)
                        for user in recipients
                    ]
                    Notification.objects.bulk_create(notices)
                    first_notification = notices[0] if notices else None

                if first_notification:
                    LogEntry.objects.create(
                        user=request.user,
                        content_type=ContentType.objects.get_for_model(Notification),
                        object_id=str(first_notification.pk),
                        object_repr=(
                            f'Notification campaign: {data["title"]} '
                            f'({recipient_count} recipient(s))'
                        ),
                        action_flag=ADDITION,
                        change_message=(
                            'Admin-created in-app notification; message body omitted from activity log.'
                        ),
                    )

            messages.success(
                request,
                f'Notification sent to {recipient_count} active user(s).',
            )
            return redirect('admin:notifications_notification_changelist')

        context = {
            **self.admin_site.each_context(request),
            'title': 'Send notifications',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/notifications/notification/send.html', context)
