from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Notification


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return redirect('notification_list')
    return render(request, 'notifications/list.html', {'notifications': notifications})


@login_required
def notification_open(request, notification_id):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        user=request.user,
    )
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=('is_read',))

    destination = notification.url
    if destination and url_has_allowed_host_and_scheme(
        destination,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(destination)
    if destination:
        return redirect('notification_list')
    return redirect('notification_list')
