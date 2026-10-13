# MediMate AI — Workflows

## Medical document workflow

1. **Authenticate:** Patient signs in; the application associates the session with the patient account.
2. **Upload:** Patient selects category, OCR language, and file. Upload form validates supported format and size.
3. **Preserve source:** Original file is saved to configured media storage. It remains available for owner-only download or image preview.
4. **Extract text locally:**
   - Text PDF → embedded text extraction.
   - Scanned PDF → render up to 20 pages, OCR each supported page.
   - Image → normalize orientation/contrast and OCR grayscale plus thresholded variants.
   - OCR unavailable or unreadable → show explicit notice; retain source.
5. **Extract candidate fields:** Exact medicine-catalog matching, associated dosage/source lines, selected lab test names/values/units, same-line printed numeric intervals, recognizable dates, and explicitly labeled diagnosis/impression text.
6. **Persist provenance:** Save original OCR separately from JSON findings and patient-reviewed medicine corrections. Log activity without adding report text to audit metadata.
7. **Present for review:** Show original image beside readable OCR (or PDF download link), structured candidate fields, review status, source text, and cautious general context for supported lab names.
8. **Patient review:** Patient compares each candidate against the original and may correct supported medicine fields. Patient review is not clinician verification.
9. **Timeline:** Add the document to the owner’s health profile timeline with selected detected facts and link to the report page.
10. **Export (optional):** Owner requests a minimal FHIR-shaped JSON export. It remains preliminary demonstration data, not certified exchange.

## Appointment workflow

1. Admin creates doctor profile, specialties, concern terms, photo, active state, weekly hours, and date overrides.
2. Patient enters concern and requested date, reviews local doctor matches, and consents to sharing relevant details.
3. Appointment request is stored and in-app staff/doctor notifications are created as configured.
4. Authorized staff, linked doctor, or admin accepts/rejects; status, activity, and patient notification are recorded.
5. Appointment letter is available to the patient. Reminder command can generate in-app reminders when scheduled externally.

## Failure/exception behavior

| Condition | Expected behavior |
|---|---|
| Unsupported file or oversized upload | Form rejects with validation error; do not pretend extraction succeeded |
| Tesseract missing | Return an explicit OCR-unavailable message and retain original |
| Telugu data absent | Inform user; process with English and mark fallback |
| Scanned PDF over page cap | Process within page limit and append notice for remaining pages |
| No OCR text | Display no-text guidance; let user download/inspect source |
| Unrecognized medicine/test/date | Do not invent or infer; show no match detected |
| Wrong account requests document | Return not found/denied response; do not reveal record existence |
| Patient review complete | Display patient review state while stating that this is not clinician verification |

## Data provenance

`Original file` → `raw extracted text` → `candidate structured fields` → `patient-reviewed medicine entries` → `display-only general test context`.

Each stage must remain distinguishable. Patient corrections do not overwrite raw OCR. Display explanations do not mutate the stored source or convert a candidate into a verified clinical result.
