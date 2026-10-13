from .models import Notification


def unread_notification_count(request):
    if not request.user.is_authenticated:
        return {'unread_notifications': 0}
    return {
        'unread_notifications': Notification.objects.filter(
            user=request.user,
            is_read=False,
        ).count(),
    }
