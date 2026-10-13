import re

from health_assistant.services.emergency import identify_emergency_phrase

IGNORED_SYMPTOM_WORDS = {
    'a', 'an', 'and', 'chronic', 'for', 'from', 'in', 'loss', 'of', 'or',
    'pain', 'severe', 'the', 'with',
}


def normalize_symptom_phrase(text):
    return ' '.join(re.findall(r'[a-z0-9]+', (text or '').casefold()))


def symptom_tokens(text):
    tokens = set()
    for token in normalize_symptom_phrase(text).split():
        if token in IGNORED_SYMPTOM_WORDS or len(token) < 4:
            continue
        tokens.add(token)
        if token.endswith('ies') and len(token) > 5:
            tokens.add(f'{token[:-3]}y')
        elif token.endswith('s') and not token.endswith(('ss', 'us', 'is')) and len(token) > 4:
            tokens.add(token[:-1])
    return tokens


def doctor_symptom_terms(doctor):
    return [
        normalized
        for term in re.split(r'[,\n;]+', doctor.treatable_symptoms or '')
        if (normalized := normalize_symptom_phrase(term))
    ]


def matched_doctor_symptoms(symptoms, doctor):
    patient_tokens = symptom_tokens(symptoms)
    return [
        term
        for term in doctor_symptom_terms(doctor)
        if symptom_tokens(term) & patient_tokens
    ]


def is_emergency_phrase(symptoms):
    return identify_emergency_phrase(symptoms) is not None
