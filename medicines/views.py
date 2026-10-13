from django.shortcuts import get_object_or_404, render

from .forms import MedicineSearchForm
from .models import Medicine


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
