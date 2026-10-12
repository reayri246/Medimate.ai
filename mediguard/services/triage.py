def assess_symptom_urgency(symptoms_text, age, severity='mild', trend='same'):
    symptoms = (symptoms_text or '').lower()

    emergency_markers = [
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
    ]
    urgent_markers = [
        'high fever',
        'severe abdominal pain',
        'severe dizziness',
        'allergic reaction',
        'anaphylaxis',
    ]

    if any(marker in symptoms for marker in emergency_markers):
        level = 'Emergency'
        recommendation = 'Call your local emergency number or go to emergency care now. Do not wait for an online assessment.'
    elif any(marker in symptoms for marker in urgent_markers):
        level = 'Urgent'
        recommendation = 'Contact a clinician or urgent care service promptly today. If symptoms become severe, seek emergency care.'
    elif severity == 'severe' or trend == 'worsening':
        level = 'Urgent'
        recommendation = (
            'Because you described severe or worsening symptoms, contact a clinician or urgent care '
            'service promptly today.'
        )
    elif age < 5:
        level = 'No emergency signs recognized'
        recommendation = (
            'This limited check cannot determine the cause or rule out a serious problem. For a child '
            'under 5, contact a pediatric clinician if you are concerned. Seek prompt care if symptoms '
            'worsen, there is trouble breathing, blue lips, or unusual difficulty waking.'
        )
    else:
        level = 'No emergency signs recognized'
        recommendation = (
            'This rule-based check cannot determine the cause or rule out a serious problem. '
            'For mild symptoms, rest and drink fluids if appropriate for you. Contact a clinician '
            'if symptoms persist, worsen, or concern you.'
        )

    return {
        'level': level,
        'recommendation': recommendation,
        'medicine_guidance': (
            'This checker does not diagnose or prescribe medicines or doses. It may show limited, '
            'non-personalized over-the-counter information for some adult symptoms. Treatment depends on '
            'the cause, age, allergies, pregnancy status, health conditions, and other medicines. Ask a '
            'pharmacist or clinician before starting a medicine, and do not use antibiotics unless prescribed.'
        ),
        'prevention': (
            'For general disease prevention, keep vaccinations up to date, wash hands, follow safe food '
            'and water practices, avoid tobacco, and attend recommended preventive checkups. A clinician '
            'can advise what is appropriate for you.'
        ),
    }
