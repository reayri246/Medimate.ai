from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from accounts.models import User
from appointments.models import Appointment
from health_tracking.models import HealthMeasurement
from prescriptions.models import DocumentUpload


@staff_member_required
def portal_home(request):
    stats = {
        'users': User.objects.count(),
        'appointments': Appointment.objects.count(),
        'measurements': HealthMeasurement.objects.count(),
        'documents': DocumentUpload.objects.count(),
    }
    return render(request, 'admin_portal/home.html', {'stats': stats})
