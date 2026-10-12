from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import AppointmentForm
from .models import Appointment


@login_required
def appointment_list(request):
    appointments = Appointment.objects.filter(user=request.user).order_by('scheduled_at')
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.user = request.user
            appointment.save()
            messages.success(request, 'Appointment saved successfully.')
            return redirect('appointment_list')
    else:
        form = AppointmentForm()
    return render(request, 'appointments/list.html', {'appointments': appointments, 'form': form})
