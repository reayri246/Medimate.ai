import re


MEDLINEPLUS_LAB_TESTS_URL = 'https://medlineplus.gov/lab-tests/'

_LAB_CONTEXT = {
    'hemoglobin': {
        'aliases': ('hemoglobin', 'haemoglobin', 'hb'),
        'measures': 'Hemoglobin is a protein in red blood cells that carries oxygen.',
        'below': 'A lower result can be associated with anemia, among other causes.',
        'above': 'A higher result can have several causes, including dehydration; this test alone cannot identify the cause.',
    },
    'red blood cells': {
        'aliases': ('rbc', 'red blood cell'),
        'measures': 'This count measures red blood cells, which carry oxygen through the body.',
        'below': 'A lower count can be associated with anemia or other conditions.',
        'above': 'A higher count can have several causes and needs to be interpreted with other blood counts and your health history.',
    },
    'white blood cells': {
        'aliases': ('wbc', 'white blood cell'),
        'measures': 'This count measures white blood cells, which are part of the body’s immune system.',
        'below': 'A lower count can have several causes, including some infections, medicines, or other conditions.',
        'above': 'A higher count can have several causes, including infection, inflammation, medicines, or other conditions.',
    },
    'platelets': {
        'aliases': ('platelet',),
        'measures': 'Platelets are blood cells that help the blood clot.',
        'below': 'A lower count can affect clotting; a clinician can assess the result and any bleeding symptoms.',
        'above': 'A higher count can have several causes and should be interpreted with the rest of the blood count and your health history.',
    },
    'glucose': {
        'aliases': ('glucose', 'blood sugar', 'fasting sugar'),
        'measures': 'A glucose test measures the amount of sugar in the blood; meal timing and whether the test was fasting matter.',
        'below': 'A lower result can be related to fasting, medicines, or other causes.',
        'above': 'A higher result can be associated with diabetes, but meal timing, illness, medicines, and other factors matter; one result alone does not diagnose diabetes.',
    },
    'hba1c': {
        'aliases': ('hba1c',),
        'measures': 'A1C reflects average blood sugar over roughly the past two to three months.',
        'below': 'A lower result needs context; some blood conditions can affect how A1C is interpreted.',
        'above': 'A higher result can be associated with increased average blood sugar, including diabetes; a clinician must interpret it using appropriate criteria and your health history.',
    },
    'creatinine': {
        'aliases': ('creatinine',),
        'measures': 'Creatinine is a waste product measured to help assess kidney function.',
        'below': 'A lower result can be affected by muscle mass and other factors.',
        'above': 'A higher result can be associated with reduced kidney filtering, but muscle mass, hydration, medicines, and other factors can also affect it.',
    },
    'urea': {
        'aliases': ('urea',),
        'measures': 'Urea is a waste product; blood levels are interpreted with other information, including kidney function and hydration.',
        'below': 'A lower result can have several causes and needs context from other tests and your health history.',
        'above': 'A higher result can be associated with kidney function or hydration changes, among other causes.',
    },
    'cholesterol': {
        'aliases': ('cholesterol',),
        'measures': 'Cholesterol is a blood fat; interpretation depends on the full lipid profile and personal risk factors.',
        'below': 'A lower result should be interpreted alongside the full lipid profile and your health history.',
        'above': 'A higher result may affect cardiovascular risk, but risk depends on the full lipid profile and other personal factors.',
    },
    'triglycerides': {
        'aliases': ('triglyceride',),
        'measures': 'Triglycerides are a type of fat in the blood, usually reviewed as part of a lipid profile.',
        'below': 'Interpretation depends on the full lipid profile and personal health context.',
        'above': 'A higher result may affect cardiovascular or metabolic risk; recent food intake and other factors can also matter.',
    },
    'tsh': {
        'aliases': ('tsh',),
        'measures': 'TSH is a hormone used with other tests, such as free T4, to assess thyroid function.',
        'below': 'A lower result can be associated with different thyroid patterns; other thyroid tests and clinical context are needed.',
        'above': 'A higher result can be associated with different thyroid patterns; other thyroid tests and clinical context are needed.',
    },
    'sodium': {
        'aliases': ('sodium',),
        'measures': 'Sodium is an electrolyte involved in fluid balance and normal nerve and muscle function.',
        'below': 'A result outside the report’s range can have several causes, including fluid balance, medicines, or health conditions.',
        'above': 'A result outside the report’s range can have several causes, including fluid balance, medicines, or health conditions.',
    },
    'potassium': {
        'aliases': ('potassium',),
        'measures': 'Potassium is an electrolyte important for normal nerve, muscle, and heart function.',
        'below': 'A result outside the report’s range can have several causes, including medicines, fluid balance, or health conditions.',
        'above': 'A result outside the report’s range can have several causes, including medicines, fluid balance, or health conditions.',
    },
    'egfr': {
        'aliases': ('egfr', 'estimated glomerular filtration rate'),
        'measures': 'eGFR is an estimate of how well the kidneys filter blood; it is interpreted with other results and health information.',
        'below': 'A lower estimate can be associated with reduced kidney filtering, but one result alone does not establish a diagnosis.',
        'above': 'A higher estimate is not usually interpreted alone; the result and calculation should be reviewed with a clinician.',
    },
    'alanine aminotransferase': {
        'aliases': ('alt', 'alanine aminotransferase'),
        'measures': 'ALT is an enzyme found mainly in the liver; it is considered with other liver tests and health information.',
        'below': 'A lower result is generally interpreted with the full panel and clinical context.',
        'above': 'A higher result can have several causes, including medicines or liver irritation; this result alone does not identify a cause.',
    },
    'aspartate aminotransferase': {
        'aliases': ('ast', 'aspartate aminotransferase'),
        'measures': 'AST is an enzyme found in the liver and other tissues; it is interpreted with other tests and health information.',
        'below': 'A lower result is generally interpreted with the full panel and clinical context.',
        'above': 'A higher result can have several causes and does not by itself identify where the change came from.',
    },
    'bilirubin': {
        'aliases': ('bilirubin',),
        'measures': 'Bilirubin is a substance formed as red blood cells are broken down and is processed by the liver.',
        'below': 'A lower result is generally interpreted with the complete liver panel and clinical context.',
        'above': 'A higher result can have several causes involving red blood cell breakdown, the liver, or bile flow.',
    },
    'albumin': {
        'aliases': ('albumin',),
        'measures': 'Albumin is a protein made by the liver; levels can be affected by several health and nutrition factors.',
        'below': 'A lower result can have several causes and should be considered alongside other tests and health information.',
        'above': 'A higher result can be associated with dehydration, among other factors.',
    },
    'calcium': {
        'aliases': ('calcium',),
        'measures': 'Calcium is a mineral important for bones, nerves, and muscles; blood levels are interpreted with related tests.',
        'below': 'A lower result can have several causes and may need review with related tests and clinical context.',
        'above': 'A higher result can have several causes and should be interpreted with related tests and clinical context.',
    },
    'hematocrit': {
        'aliases': ('hematocrit', 'haematocrit'),
        'measures': 'Hematocrit is the proportion of blood made up of red blood cells.',
        'below': 'A lower result can be associated with anemia or other causes and is interpreted with the rest of a blood count.',
        'above': 'A higher result can be associated with dehydration or other causes and is interpreted with the rest of a blood count.',
    },
    'mcv': {
        'aliases': ('mcv',),
        'measures': 'MCV describes the average size of red blood cells and is interpreted with other blood-count results.',
        'below': 'A lower result describes smaller-than-expected red cells relative to the report range; it does not identify a cause.',
        'above': 'A higher result describes larger-than-expected red cells relative to the report range; it does not identify a cause.',
    },
    'ferritin': {
        'aliases': ('ferritin',),
        'measures': 'Ferritin is a protein that stores iron; the result is interpreted with other iron tests and health information.',
        'below': 'A lower result can be associated with low iron stores, but a clinician should interpret it with other information.',
        'above': 'A higher result can have several causes, including inflammation or liver conditions; it does not identify a cause on its own.',
    },
    'c reactive protein': {
        'aliases': ('crp', 'c reactive protein'),
        'measures': 'CRP is a protein that can increase with inflammation in the body.',
        'below': 'A lower result is interpreted in context and does not rule out every health condition.',
        'above': 'A higher result can indicate inflammation but does not identify its cause or location.',
    },
}


def _normalize_name(value):
    return re.sub(r'[\W_]+', ' ', (value or '').casefold()).strip()


def explain_lab_test(result):
    """Return general, source-linked context without diagnosing a patient."""
    normalized_name = _normalize_name(result.get('name'))
    normalized_name = re.sub(r'\s+', ' ', normalized_name)

    for context in _LAB_CONTEXT.values():
        if any(
            normalized_name == _normalize_name(alias)
            for alias in context['aliases']
        ):
            explanation = {'what_it_measures': context['measures']}
            comparison = result.get('range_comparison')
            if comparison in ('below', 'above'):
                explanation['out_of_range_context'] = context[comparison]
            explanation['source_name'] = 'MedlinePlus (U.S. National Library of Medicine)'
            explanation['source_url'] = MEDLINEPLUS_LAB_TESTS_URL
            return explanation
    return {}
