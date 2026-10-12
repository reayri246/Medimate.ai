import re

from medicines.models import Medicine


def _normalize_for_matching(value):
    return re.sub(r'[\W_]+', ' ', value.casefold()).strip()


def extract_medicine_names(document_text):
    """Match readable prescription text to medicine catalog names and ingredients."""
    normalized_text = _normalize_for_matching(document_text or '')
    if not normalized_text:
        return []

    detections = {}
    medicines = Medicine.objects.prefetch_related('ingredients').order_by('name')

    for medicine in medicines:
        candidates = [(medicine.name, 'medicine')]
        candidates.extend(
            (ingredient.name, 'active ingredient')
            for ingredient in medicine.ingredients.all()
        )
        candidates.extend(
            (ingredient.standard_name, 'active ingredient')
            for ingredient in medicine.ingredients.all()
        )

        for candidate, match_type in candidates:
            normalized_candidate = _normalize_for_matching(candidate)
            if not normalized_candidate:
                continue
            if re.search(
                rf'(?<!\w){re.escape(normalized_candidate)}(?!\w)',
                normalized_text,
            ):
                key = normalized_candidate
                detections.setdefault(key, {
                    'name': candidate,
                    'match_type': match_type,
                    'catalog_medicine': medicine.name,
                    'composition_verified': medicine.has_verified_composition,
                    'source_name': medicine.source_name if medicine.has_verified_composition else '',
                    'source_url': medicine.source_url if medicine.has_verified_composition else '',
                })

    return sorted(detections.values(), key=lambda item: item['name'].casefold())
