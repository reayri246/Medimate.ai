import re
import mimetypes
from uuid import NAMESPACE_URL, uuid5

from django.utils import timezone
from django.urls import reverse

from .medicine_extraction import extract_medicine_names


MAX_ANALYSIS_TEXT_LENGTH = 100_000
LAB_TEST_NAMES = (
    'hemoglobin', 'haemoglobin', 'hb', 'glucose', 'blood sugar', 'fasting sugar',
    'hba1c', 'wbc', 'white blood cell', 'rbc', 'red blood cell', 'platelet',
    'creatinine', 'urea', 'cholesterol', 'triglyceride', 'tsh', 'sodium', 'potassium',
)
LAB_VALUE_PATTERN = re.compile(
    r'(?i)(?P<name>' + '|'.join(re.escape(name) for name in LAB_TEST_NAMES) +
    r')\s*(?:[:=]\s*|\s+)(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>'
    r'mg/dl|mg/dL|g/dl|g/L|mmol/L|µmol/L|umol/L|mIU/L|%|10\^?\d*/?L|'
    r'cells/?[uμµ]L|[a-zA-Zμµ/]+)?'
)
REFERENCE_RANGE_PATTERN = re.compile(
    r'(?i)(?:reference\s+range|ref(?:erence)?\.?\s*range|normal\s+range)?'
    r'\s*[:=]?\s*[\[(]?\s*(?P<low>\d+(?:[.,]\d+)?)\s*'
    r'(?:-|–|to)\s*(?P<high>\d+(?:[.,]\d+)?)\s*[\])]?',
)
DATE_PATTERNS = (
    re.compile(r'(?<!\d)(?P<date>\d{4}[-/]\d{1,2}[-/]\d{1,2})(?!\d)'),
    re.compile(r'(?<!\d)(?P<date>\d{1,2}[-/]\d{1,2}[-/]\d{2,4})(?!\d)'),
    re.compile(
        r'(?i)(?<!\w)(?P<date>\d{1,2}\s+'
        r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|'
        r'Dec(?:ember)?)\s+\d{4})(?!\w)'
    ),
)
DIAGNOSIS_PATTERN = re.compile(
    r'(?im)^\s*(diagnosis|impression|assessment|final diagnosis)\s*[:\-]\s*(.+?)\s*$'
)
DOSAGE_PATTERN = re.compile(
    r'(?i)\b\d+(?:\.\d+)?\s?(?:mcg|μg|µg|mg|g|ml|mL|units?)\b'
)


def _extract_dates(text):
    dates = []
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group('date')
            if value not in dates:
                dates.append(value)
    return dates[:20]


def _extract_test_values(text):
    results = []
    seen = set()
    for match in LAB_VALUE_PATTERN.finditer(text):
        line_end = text.find('\n', match.end())
        if line_end < 0:
            line_end = len(text)
        same_line_tail = text[match.end():line_end]
        result = {
            'name': match.group('name'),
            'value': match.group('value').replace(',', '.'),
            'unit': (match.group('unit') or '').strip(),
            'source_text': match.group(0)[:200],
        }
        range_match = REFERENCE_RANGE_PATTERN.search(same_line_tail)
        if range_match:
            lower = range_match.group('low').replace(',', '.')
            upper = range_match.group('high').replace(',', '.')
            result['printed_reference_range'] = f'{lower}-{upper}'
            try:
                value_number = float(result['value'])
                lower_number = float(lower)
                upper_number = float(upper)
            except ValueError:
                pass
            else:
                if value_number < lower_number:
                    result['range_comparison'] = 'below'
                elif value_number > upper_number:
                    result['range_comparison'] = 'above'
                else:
                    result['range_comparison'] = 'within'
        key = (result['name'].casefold(), result['value'], result['unit'].casefold())
        if key not in seen:
            results.append(result)
            seen.add(key)
    return results[:50]


def _extract_dosage_mentions(text, medicines):
    if not medicines:
        return []

    catalog_names = set()
    for medicine in medicines:
        catalog_names.add(medicine['name'].casefold())
        catalog_names.add(medicine['catalog_medicine'].casefold())

    mentions = []
    for line in text.splitlines():
        if not DOSAGE_PATTERN.search(line):
            continue
        folded_line = line.casefold()
        matched_name = next((name for name in catalog_names if name and name in folded_line), None)
        if matched_name:
            mentions.append({
                'medicine': matched_name,
                'text': line.strip()[:240],
            })
    return mentions[:30]


def extract_record_details(document_text):
    """Extract reviewable text matches; never interpret clinical significance."""
    text = (document_text or '')[:MAX_ANALYSIS_TEXT_LENGTH]
    medicines = extract_medicine_names(text)
    diagnoses = [
        {'label': match.group(1), 'text': match.group(2).strip()[:240]}
        for match in DIAGNOSIS_PATTERN.finditer(text)
    ][:30]
    return {
        'medicines': medicines,
        'dosage_mentions': _extract_dosage_mentions(text, medicines),
        'test_values': _extract_test_values(text),
        'diagnosis_mentions': diagnoses,
        'dates': _extract_dates(text),
    }


def build_fhir_bundle(document, download_url):
    """Create a minimal FHIR R4-shaped bundle for demonstration and export."""
    user = document.user
    patient_full_url = f'urn:uuid:{uuid5(NAMESPACE_URL, f"medimate:patient:{user.pk}")}'
    document_full_url = f'urn:uuid:{uuid5(NAMESPACE_URL, f"medimate:document:{document.pk}")}'
    patient = {
        'resourceType': 'Patient',
        'id': f'patient-{user.pk}',
        'identifier': [],
    }
    if user.demo_abha_id:
        patient['identifier'].append({
            'system': 'urn:medimate:fictional-demo-abha',
            'value': user.demo_abha_id,
        })
    if user.get_full_name():
        patient['name'] = [{'text': user.get_full_name()}]
    if user.date_of_birth:
        patient['birthDate'] = user.date_of_birth.isoformat()

    document_reference = {
        'resourceType': 'DocumentReference',
        'id': f'document-{document.pk}',
        'status': 'current',
        'docStatus': 'preliminary',
        'type': {
            'coding': [{
                'system': 'urn:medimate:document-type',
                'code': document.document_type,
                'display': document.get_document_type_display(),
            }],
            'text': document.get_document_type_display(),
        },
        'subject': {'reference': f'Patient/{patient["id"]}'},
        'date': document.created_at.isoformat() if document.created_at else timezone.now().isoformat(),
        'description': document.title,
        'content': [{
            'attachment': {
                'contentType': mimetypes.guess_type(document.file.name)[0] or 'application/octet-stream',
                'url': download_url,
                'title': document.title,
            },
        }],
    }
    entries = [
        {'fullUrl': patient_full_url, 'resource': patient},
        {'fullUrl': document_full_url, 'resource': document_reference},
    ]

    for index, result in enumerate(document.extracted_details.get('test_values', []), start=1):
        try:
            value = float(result['value'])
        except (KeyError, TypeError, ValueError):
            continue
        observation = {
            'resourceType': 'Observation',
            'id': f'observation-{document.pk}-{index}',
            'status': 'preliminary',
            'code': {'text': result.get('name', 'Unlabeled extracted value')},
            'subject': {'reference': f'Patient/{patient["id"]}'},
            'valueQuantity': {'value': value},
            'note': [{
                'text': 'Possible OCR/text extraction only; verify against the original report. No clinical interpretation provided.',
            }],
        }
        if result.get('unit'):
            observation['valueQuantity']['unit'] = result['unit']
        if result.get('printed_reference_range'):
            try:
                lower, upper = (
                    float(value)
                    for value in result['printed_reference_range'].split('-', 1)
                )
            except (TypeError, ValueError):
                pass
            else:
                observation['referenceRange'] = [{
                    'low': {
                        'value': lower,
                        **({'unit': result['unit']} if result.get('unit') else {}),
                    },
                    'high': {
                        'value': upper,
                        **({'unit': result['unit']} if result.get('unit') else {}),
                    },
                }]
        entries.append({
            'fullUrl': f'urn:uuid:{uuid5(NAMESPACE_URL, f"medimate:observation:{document.pk}:{index}")}',
            'resource': observation,
        })

    return {
        'resourceType': 'Bundle',
        'type': 'collection',
        'timestamp': timezone.now().isoformat(),
        'entry': entries,
    }
