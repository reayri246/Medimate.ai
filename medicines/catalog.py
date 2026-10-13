from .models import Medicine


def verified_medicines():
    candidates = Medicine.objects.filter(
        safety_data_verified=True,
        source_name__gt='',
        source_url__gt='',
        last_verified__isnull=False,
    ).prefetch_related('ingredients').order_by('name')
    return [medicine for medicine in candidates if medicine.has_verified_composition]
