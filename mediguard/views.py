from django.shortcuts import render

from medicines.safety import verified_medicines

from .forms import SafetyCheckForm
from .services.triage import assess_symptom_urgency


def guard_home(request):
    result = None
    medicine_references = []
    if request.method == 'POST':
        form = SafetyCheckForm(request.POST)
        if form.is_valid():
            symptoms = form.cleaned_data['symptoms']
            triage = assess_symptom_urgency(
                symptoms,
                form.cleaned_data['age'],
                form.cleaned_data['severity'],
                form.cleaned_data['trend'],
            )
            result = {
                'triage': triage,
            }
            result['intake'] = {
                'age': form.cleaned_data['age'],
                'symptoms': symptoms,
                'duration': form.cleaned_data['duration'],
                'severity': form.cleaned_data['severity'],
                'trend': form.cleaned_data['trend'],
            }
            if (
                form.cleaned_data['age'] >= 18
                and triage['level'] == 'No emergency signs recognized'
            ):
                medicine_references = [
                    {
                        'medicine': medicine,
                        'ingredients': medicine.ingredients.all(),
                    }
                    for medicine in verified_medicines()
                    if medicine.is_non_prescription
                ]
    else:
        form = SafetyCheckForm()
    return render(request, 'mediguard/home.html', {
        'form': form,
        'result': result,
        'medicine_references': medicine_references,
    })
