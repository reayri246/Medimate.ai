EMERGENCY_MARKERS = (
    'chest pain',
    'shortness of breath',
    'trouble breathing',
    'difficulty breathing',
    'fainting',
    'unconscious',
    'severe bleeding',
    'vomiting blood',
    'confusion',
    'stroke',
    'face droop',
    'one-sided weakness',
    'slurred speech',
    'seizure',
    'swollen tongue',
    'swollen face',
    'throat closing',
    'blue lips',
    'severe dehydration',
    'unable to keep fluids down',
    'not urinating',
)


def identify_emergency_phrase(text):
    """Return emergency escalation text for a small set of explicit phrases."""
    normalized = (text or '').casefold()
    if any(marker in normalized for marker in EMERGENCY_MARKERS):
        return 'Call your local emergency number or go to emergency care now. Do not wait for an online assessment.'
    return None
