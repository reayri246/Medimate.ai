from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import MedicalRecordForm
from .models import MedicalRecord


@login_required
def record_list(request):
    records = MedicalRecord.objects.filter(user=request.user).order_by('-created_at')
    if request.method == 'POST':
        form = MedicalRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.user = request.user
            record.save()
            messages.success(request, 'Medical record saved successfully.')
            return redirect('record_list')
    else:
        form = MedicalRecordForm()
    return render(request, 'medical_records/list.html', {'records': records, 'form': form})
