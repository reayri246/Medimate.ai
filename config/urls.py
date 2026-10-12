from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('medicines/', include('medicines.urls')),
    path('prescriptions/', include('prescriptions.urls')),
    path('guard/', include('mediguard.urls')),
    path('assistant/', include('health_assistant.urls')),
    path('records/', include('medical_records.urls')),
    path('tracking/', include('health_tracking.urls')),
    path('appointments/', include('appointments.urls')),
    path('notifications/', include('notifications.urls')),
    path('portal/', include('admin_portal.urls')),
    path('admin/', admin.site.urls),
]
