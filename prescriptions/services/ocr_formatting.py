import re


OCR_REVIEW_PREFIX = re.compile(
    r'^\s*\[(?:OCR text|PDF page \d+ - embedded text)[^\]]*\]\s*',
    re.IGNORECASE,
)
FIELD_BOUNDARIES = re.compile(
    r'(?i)(?<!\w)(?=(?:name|date|age|temp(?:erature)?|pulse|'
    r'patient|diagnosis|medicine|medication|prescription|rx|advice|'
    r'follow[- ]?up|morning|afternoon|evening)\s*[:#-]?\s)'
)
ITEM_SEPARATOR = re.compile(r'\s*(?:\r?\n+|[;|]+)\s*')
SENTENCE_SEPARATOR = re.compile(r'(?<=[.!?])\s+')


def _split_long_item(text, max_length=180):
    if len(text) <= max_length:
        return [text]
    chunks = []
    remaining = text
    while len(remaining) > max_length:
        split_at = remaining.rfind(' ', 0, max_length + 1)
        if split_at < max_length // 2:
            split_at = max_length
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def format_ocr_points(text):
    """Format OCR text for display without changing the stored transcription."""
    if not text:
        return []

    cleaned = OCR_REVIEW_PREFIX.sub('', text, count=1)
    cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\s*,\s*', ', ', cleaned)

    points = []
    for line in ITEM_SEPARATOR.split(cleaned):
        for sentence in SENTENCE_SEPARATOR.split(line):
            for item in FIELD_BOUNDARIES.split(sentence):
                item = re.sub(r'\s+', ' ', item).strip(' \t,;|')
                if item:
                    points.extend(_split_long_item(item))
    return points
