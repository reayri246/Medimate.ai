from django.shortcuts import get_object_or_404, render

from .forms import MedicineComparisonForm, MedicineSearchForm
from .models import Medicine
from .safety import compare_medicines, verified_medicines


def medicine_list(request):
    form = MedicineSearchForm(request.GET or None)
    query = request.GET.get('query', '').strip()
    medicines = Medicine.objects.all().prefetch_related('ingredients').order_by('name')
    if query:
        medicines = medicines.filter(
            name__icontains=query
        ) | medicines.filter(active_ingredient__icontains=query) | medicines.filter(
            ingredients__name__icontains=query
        ) | medicines.filter(
            ingredients__standard_name__icontains=query
        ) | medicines.filter(
            ingredients__aliases__icontains=query
        )
    return render(request, 'medicines/list.html', {'medicines': medicines.distinct(), 'form': form, 'query': query})


def medicine_detail(request, slug):
    medicine = get_object_or_404(Medicine, slug=slug)
    return render(request, 'medicines/detail.html', {'medicine': medicine})


def medicine_compare(request):
    result = None
    if request.method == 'POST':
        form = MedicineComparisonForm(request.POST)
        if form.is_valid():
            result = compare_medicines(form.cleaned_data['medicines'])
    else:
        form = MedicineComparisonForm()
    return render(
        request,
        'medicines/compare.html',
        {
            'form': form,
            'result': result,
            'verified_medicine_count': len(verified_medicines()),
        },
    )
