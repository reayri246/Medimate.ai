import re

from medicines.models import ActiveIngredient, Medicine
from medicines.safety import verified_medicines
from mediguard.services.triage import assess_symptom_urgency


DISCLAIMER = (
    'Educational information only — this assistant cannot diagnose disease, predict an individual '
    'health outcome, or replace advice from a qualified healthcare professional.'
)


def _contains_term(text, terms):
    return any(re.search(rf'(?<!\w){re.escape(term)}(?!\w)', text) for term in terms)


def _verified_catalog_answer(question):
    medicines = verified_medicines()
    normalized_question = re.sub(r'[\W_]+', ' ', question.casefold()).strip()

    for medicine in medicines:
        medicine_names = [medicine.name]
        medicine_names.extend(
            ingredient.name for ingredient in medicine.ingredients.all()
        )
        medicine_names.extend(
            ingredient.standard_name for ingredient in medicine.ingredients.all()
        )
        for name in medicine_names:
            normalized_name = re.sub(r'[\W_]+', ' ', name.casefold()).strip()
            if normalized_name and _contains_term(normalized_question, [normalized_name]):
                ingredients = list(medicine.ingredients.all().order_by('standard_name'))
                return {
                    'heading': f'Verified catalog information: {medicine.name}',
                    'body': medicine.description,
                    'details': [
                        f'Active ingredient: {ingredient.name} '
                        f'(standard name: {ingredient.standard_name})'
                        for ingredient in ingredients
                    ],
                    'cautions': [
                        'This information does not confirm that this product is safe or suitable for you.',
                        medicine.warnings or 'Verified warning information unavailable.',
                        'Interaction information could not be verified. Please consult a pharmacist or doctor.',
                    ],
                    'sources': [{
                        'name': medicine.source_name,
                        'url': medicine.source_url,
                        'verified': medicine.last_verified,
                    }],
                }

    ingredients = ActiveIngredient.objects.filter(
        information_verified=True,
        source_name__gt='',
        source_url__gt='',
        last_verified__isnull=False,
    ).order_by('standard_name')
    for ingredient in ingredients:
        names = [ingredient.name, ingredient.standard_name]
        names.extend(ingredient.aliases.splitlines())
        for name in names:
            normalized_name = re.sub(r'[\W_]+', ' ', name.casefold()).strip()
            if normalized_name and _contains_term(normalized_question, [normalized_name]):
                return {
                    'heading': f'Verified ingredient information: {ingredient.name}',
                    'body': 'This ingredient is listed in the reviewed catalog. Product suitability and interactions depend on the specific product and individual circumstances.',
                    'details': [f'Standard name: {ingredient.standard_name}'],
                    'cautions': [
                        'This information does not confirm that a product containing this ingredient is safe or suitable for you.',
                        'No personalized treatment or medicine combination can be recommended here.',
                        'Interaction information could not be verified. Please consult a pharmacist or doctor.',
                    ],
                    'sources': [{
                        'name': ingredient.source_name,
                        'url': ingredient.source_url,
                        'verified': ingredient.last_verified,
                    }],
                }
    return None


def answer_health_question(question):
    """Return bounded general information and source-backed catalog facts only."""
    cleaned = re.sub(r'\s+', ' ', (question or '').strip().casefold())
    answer = {
        'heading': 'General health information',
        'body': '',
        'details': [],
        'cautions': [],
        'sources': [],
        'disclaimer': DISCLAIMER,
        'kind': 'general',
    }

    if not cleaned:
        answer['body'] = 'Enter a general health question or describe what information you are looking for.'
        return answer

    emergency_assessment = assess_symptom_urgency(cleaned, age=18)
    if emergency_assessment['level'] == 'Emergency':
        answer.update({
            'heading': 'Seek emergency care now',
            'body': emergency_assessment['recommendation'],
            'cautions': [
                'Do not wait for an online assistant. Contact your local emergency service now.',
            ],
            'kind': 'emergency',
        })
        return answer

    if (
        _contains_term(cleaned, (
            'predict my health',
            'predict my future',
            'will i get',
            'what disease do i have',
            'what do i have',
            'diagnose me',
            'am i having',
            'am i sick',
            'do i have',
            'what is wrong with me',
            'is this flu',
            'is this covid',
        ))
    ):
        answer['heading'] = 'An online assistant cannot predict or diagnose your health'
        answer['body'] = (
            'A health outcome or diagnosis cannot be reliably determined from a chat message. '
            'A clinician can assess your symptoms, history, examination, and tests where needed.'
        )
        answer['cautions'] = ['If you describe your symptoms and how long they have been present, this assistant can share general information and flag some warning signs.']
        answer['kind'] = 'boundary'
        return answer

    if _contains_term(cleaned, (
        'what medicine',
        'which medicine',
        'what tablet',
        'which tablet',
        'what should i take',
        'what do i take',
        'can i take',
        'medicine for',
        'tablet for',
        'recommend a medicine',
        'recommend a tablet',
        'prescribe',
        'dosage',
        'dose should',
    )):
        answer['heading'] = 'Medicine decisions need a pharmacist or clinician'
        answer['body'] = (
            'I cannot select a medicine, prescribe a treatment, or calculate a dose from symptoms. '
            'The right option depends on the cause, age, allergies, other medicines, pregnancy status, '
            'and health conditions.'
        )
        answer['details'] = [
            'For verified ingredient details, search the medicine catalog.',
            'Ask a pharmacist or clinician whether a product is appropriate for you.',
            'Do not start, stop, or combine medicines based on this assistant.',
        ]
        answer['kind'] = 'medicine_boundary'
        return answer

    catalog_answer = _verified_catalog_answer(cleaned)
    if catalog_answer:
        answer.update(catalog_answer)
        answer['disclaimer'] = DISCLAIMER
        answer['kind'] = 'catalog'
        return answer

    if _contains_term(cleaned, ('fever', 'temperature')):
        answer['heading'] = 'General information about fever'
        answer['body'] = (
            'Fever can have many causes, and this assistant cannot identify the cause. Rest, drink '
            'fluids if appropriate for you, and observe how symptoms change. Contact a healthcare '
            'professional if the fever persists, worsens, or you are concerned.'
        )
    elif _contains_term(cleaned, ('cold', 'cough', 'sore throat', 'runny nose', 'sneezing')):
        answer['heading'] = 'General information about cold-like symptoms'
        answer['body'] = (
            'Cold-like symptoms can have different causes. Rest and drink fluids if appropriate for '
            'you. This assistant cannot tell whether symptoms are a cold or another illness and will '
            'not choose a medicine based on symptoms.'
        )
        answer['details'] = [
            'Ask a pharmacist or clinician about treatments that may be appropriate for you.',
            'Seek professional advice if symptoms worsen, persist, or cause concern.',
        ]
    elif _contains_term(cleaned, ('blood pressure', 'hypertension')):
        answer['heading'] = 'General information about blood pressure'
        answer['body'] = (
            'Blood pressure readings should be interpreted in context and may need repeat measurement. '
            'Discuss repeated unusual readings with a healthcare professional. Chest pain, fainting, '
            'confusion, or breathing difficulty needs urgent assessment.'
        )
    elif _contains_term(cleaned, ('side effect', 'adverse reaction', 'reaction to medicine', 'medication')):
        answer['heading'] = 'Medicine safety information'
        answer['body'] = (
            'Possible side effects vary by product and person. Check the specific product leaflet and '
            'ask a pharmacist or clinician. Do not stop a prescribed medicine without professional advice '
            'unless you are experiencing a medical emergency.'
        )
        answer['details'] = [
            'For verified composition details, search the medicine catalog.',
            'Interaction information is not available unless it is explicitly shown with a verified source.',
        ]
    elif _contains_term(cleaned, ('sleep', 'insomnia')):
        answer['heading'] = 'General information about sleep'
        answer['body'] = (
            'A consistent sleep and wake schedule and a calm, comfortable sleep environment may support '
            'healthy sleep habits. Seek professional advice for persistent sleep problems or significant '
            'daytime impairment.'
        )
    elif _contains_term(cleaned, ('prevent disease', 'prevent illness', 'vaccination', 'vaccine', 'prevention')):
        answer['heading'] = 'General health prevention'
        answer['body'] = (
            'General prevention can include staying up to date with recommended vaccinations, hand '
            'hygiene, safe food and water practices, avoiding tobacco, and attending age-appropriate '
            'preventive checkups. Ask a healthcare professional which steps apply to you.'
        )
    else:
        answer['heading'] = 'I can share general health information'
        answer['body'] = (
            'I did not find a verified answer for that question in the local information available. '
            'Try asking about general fever care, cold-like symptoms, blood pressure, medicine safety, '
            'sleep, or prevention — or consult a qualified healthcare professional.'
        )

    answer['cautions'] = [
        'This assistant cannot diagnose disease, predict an individual health outcome, or recommend medicines based on symptoms.',
        'Seek medical care for severe, worsening, persistent, or concerning symptoms.',
    ]
    return answer
