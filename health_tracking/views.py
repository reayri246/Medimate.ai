from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.shortcuts import get_object_or_404

from .forms import HealthMeasurementForm
from .models import HealthMeasurement


@login_required
def tracking_home(request):
    measurements = HealthMeasurement.objects.filter(user=request.user).order_by('-date')
    if request.method == 'POST':
        form = HealthMeasurementForm(request.POST)
        if form.is_valid():
            measurement = form.save(commit=False)
            measurement.user = request.user
            measurement.save()
            messages.success(request, 'Health measurement saved successfully.')
            return redirect('tracking_home')
    else:
        form = HealthMeasurementForm()
    return render(request, 'health_tracking/home.html', {'measurements': measurements, 'form': form})


@login_required
def measurement_detail(request, measurement_id):
    measurement = get_object_or_404(
        HealthMeasurement,
        pk=measurement_id,
        user=request.user,
    )
    return render(
        request,
        'health_tracking/detail.html',
        {'measurement': measurement},
    )
