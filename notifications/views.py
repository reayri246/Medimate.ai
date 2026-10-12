from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import Notification


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return redirect('notification_list')
    return render(request, 'notifications/list.html', {'notifications': notifications})
