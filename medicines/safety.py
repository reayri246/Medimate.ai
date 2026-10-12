import re

from .models import Medicine


def _normalized_name(value):
    return re.sub(r'[\W_]+', ' ', value.casefold()).strip()


def _ingredient_keys(ingredient):
    names = [ingredient.name, ingredient.standard_name]
    names.extend(ingredient.aliases.splitlines())
    return {
        normalized
        for name in names
        if (normalized := _normalized_name(name.strip()))
    }


def verified_medicines():
    candidates = Medicine.objects.filter(
        safety_data_verified=True,
        source_name__gt='',
        source_url__gt='',
        last_verified__isnull=False,
    ).prefetch_related('ingredients').order_by('name')
    return [medicine for medicine in candidates if medicine.has_verified_composition]


def compare_medicines(medicines):
    medicine_ingredients = []
    ingredient_keys_by_medicine = []

    for medicine in medicines:
        ingredient_rows = []
        ingredient_keys = {}
        for ingredient in medicine.ingredients.all().order_by('standard_name'):
            composition = medicine.medicineingredient_set.get(ingredient=ingredient)
            ingredient_rows.append({
                'name': ingredient.name,
                'standard_name': ingredient.standard_name,
                'strength': f'{composition.strength} {composition.unit}'.strip(),
                'source_name': ingredient.source_name,
                'source_url': ingredient.source_url,
                'last_verified': ingredient.last_verified,
            })
            for key in _ingredient_keys(ingredient):
                ingredient_keys[key] = ingredient
        medicine_ingredients.append({
            'medicine': medicine,
            'ingredients': ingredient_rows,
        })
        ingredient_keys_by_medicine.append(ingredient_keys)

    duplicate_keys = set()
    for index, first in enumerate(ingredient_keys_by_medicine):
        for second in ingredient_keys_by_medicine[index + 1:]:
            duplicate_keys.update(first.keys() & second.keys())

    duplicates = []
    seen_standard_names = set()
    for key in sorted(duplicate_keys):
        matching = [
            keys[key]
            for keys in ingredient_keys_by_medicine
            if key in keys
        ]
        canonical_name = matching[0].standard_name
        if canonical_name not in seen_standard_names:
            duplicates.append(canonical_name)
            seen_standard_names.add(canonical_name)

    pair_count = (len(medicines) * (len(medicines) - 1)) // 2
    return {
        'medicines': medicine_ingredients,
        'duplicate_ingredients': duplicates,
        'duplicate_warning': (
            'Both selected products contain the same active ingredient. Using multiple products '
            'containing the same active ingredient can increase exposure. Verify the labels and '
            'consult a pharmacist or doctor before combining them.'
            if duplicates else ''
        ),
        'interaction_warnings': [
            'Interaction information could not be verified. Please consult a pharmacist or doctor.'
            for _ in range(pair_count)
        ],
        'sources': [
            {
                'medicine': medicine.name,
                'source_name': medicine.source_name,
                'source_url': medicine.source_url,
                'last_verified': medicine.last_verified,
            }
            for medicine in medicines
        ],
        'disclaimer': (
            'This information is educational and does not replace professional medical advice. '
            'No detected duplicate ingredient does not establish that combining medicines is safe. '
            'Do not use this result to decide to start, stop, or combine medicines.'
        ),
    }
