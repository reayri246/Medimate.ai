# MediMate AI — Complete Project Explanation

## 1. What the project is

MediMate AI is a Django-based health organization and record-review prototype. Its central user journey is: sign in, upload a medical document, extract text locally, inspect possible structured fields, review the result against the original, and find the document again from a unified health profile.

The project name includes “AI,” but the current document pipeline is not generative AI. It combines standard OCR with deterministic patterns, catalog matching, and static general explanations. Do not describe its output as a diagnosis, verified prescription, or clinically validated interpretation.

## 2. Patient journey

1. A patient creates an account and signs in.
2. They upload a prescription, lab report, discharge summary, diagnostic record, or other document and choose OCR language.
3. The server preserves the original file and processes content locally.
4. The patient views the original image (or downloads the PDF) alongside extracted text.
5. The app presents possible medicines, recognized dosage/strength lines, selected lab values, explicitly labeled diagnosis/impression text, dates, and limited general lab context.
6. The patient can open the review flow to correct medicine fields. Corrections are kept separately from raw OCR.
7. The report appears in the patient’s health profile timeline, along with health measurements, appointments, personal notes, and notifications.

## 3. Document intelligence and OCR details

### Input and storage

`DocumentUpload` stores the account owner, title, category, original file reference, OCR text, JSON extraction results, reviewed medicine fields, language, status, and timestamps. Private views scope retrieval to the signed-in owner.

### Text acquisition

- Text-based PDF: extract embedded text with pypdf.
- Scanned PDF: render pages with PyMuPDF and use Tesseract OCR, up to 20 pages.
- Images: correct EXIF orientation, convert to grayscale/autocontrast, run grayscale and thresholded passes, then select the pass with the strongest average word confidence.
- Telugu+English: use `eng+tel` only when the Telugu Tesseract language data is installed; otherwise show a notice and fall back to English.

The confidence selection is a technical heuristic, not a medical accuracy score. OCR output remains provisional.

### Structured extraction

The local rules attempt to detect:

- Medicine names and active ingredients that exactly match catalog entries.
- Dosage/strength text near matched medicine names and limited explicit quantities.
- A defined list of laboratory test labels, numeric values, and units.
- Numeric intervals printed on the same line as a supported result.
- Date strings in supported formats.
- Text on lines explicitly labeled Diagnosis, Impression, Assessment, or Final diagnosis.

Extraction can miss relevant information or misread/misassociate it. Original text, source line, and manual review are important.

## 4. Plain-language report context

For a limited set of common test labels, a local rule library says what the test generally measures and provides cautious possible associations for values compared as above/below a same-line printed reference interval. The rendered output links to general MedlinePlus lab-test information.

This is **not** an AI explanation of a patient's health. It does not determine a cause, diagnose, assess urgency, or recommend treatment. The app does not explain unknown test labels. Printed reference ranges vary by lab and patient; extracted OCR values should be checked against the original.

## 5. Unified health profile

The health-profile view assembles entries from:

- Health measurements (blood pressure, heart rate, weight, temperature, glucose, notes).
- Appointments and status.
- Personal medical notes.
- Uploaded documents, status, and selected extracted findings.
- Notifications/activity.

Entries are sorted chronologically, linked to individual pages, and restricted to the signed-in account. Current implementation limits each source query and displays a bounded combined timeline; it is not an unlimited longitudinal analytics engine.

## 6. Other application capabilities

- **Health assistant:** deterministic responses for selected general health topics, emergency phrase detection, and source-backed catalog facts. It is not a generative model and does not diagnose or recommend treatment.
- **Medicine finder:** searches the administrator-maintained medicine and ingredient catalog. Source and verification metadata support careful display of selected facts.
- **Appointments:** local doctor matching from admin-entered concern terms, active doctors and duty schedules, appointment decisions, patient letters, activity and in-app notification flows.
- **Notifications:** patient notification list and unread count; administrator can compose notices for selected/all active users.
- **Personal records and tracking:** owner-scoped notes and wellness measurements.
- **FHIR-style export:** minimal Bundle/Patient/DocumentReference/Observation-shaped JSON for demonstration. It is not certified FHIR exchange or an ABDM connection.
- **Legal and team pages:** footer-linked terms/privacy information and Aura 5 page.

## 7. Application structure

| Directory | Responsibility |
|---|---|
| `config/` | Django settings, URL composition, WSGI/ASGI |
| `accounts/` | Custom user, authentication, profile |
| `core/` | Landing, dashboard, health profile/timeline, team and legal pages |
| `prescriptions/` | Upload, OCR, extraction, review, export, audit logging |
| `medical_records/` | Patient notes and report listing/detail |
| `health_tracking/` | Wellness readings |
| `health_assistant/` | Bounded local information responses |
| `medicines/` | Medicine and active-ingredient catalog |
| `appointments/` | Doctor profiles, schedules, requests, decision flow |
| `notifications/` | In-app notifications and admin delivery |
| `admin_portal/` | Staff/admin overview and notification tools |
| `templates/`, app template folders | Server-rendered HTML |
| `static/` | Shared CSS, JavaScript, icons |

## 8. Data flow and trust boundaries

Uploaded files are untrusted input. The application validates allowed file types and size, stores originals, and processes supported content locally. Extracted text and all derived fields are untrusted until the patient compares them with the source. The application database stores user-linked health information. Admin access is a separate trust boundary and should be minimized and documented in deployment policy. Production storage must be private and persistent.

## 9. Privacy and security controls

Implemented controls include Django authentication, user-scoped record retrieval, CSRF middleware, upload bounds, owner-only document pages, private/no-store response headers on sensitive views, attachment download behavior, and access audit events that avoid copying extracted text into log metadata.

Production still requires deployment-specific configuration: HTTPS, PostgreSQL, secure secrets/cookies, private persistent file storage, access review, backups, retention/deletion policy, monitoring, incident response, and privacy/legal review. Local filesystem storage is a development default and should not be assumed durable/private in every host environment.

## 10. How to run locally

From the repository root on Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
py manage.py migrate
py manage.py seed_data
py manage.py runserver
```

Image/scanned-PDF OCR additionally requires Tesseract on PATH. Telugu OCR requires its trained data. Seed data is illustrative only and must not be used for patient decisions or seeded into production.

## 11. Testing and verification

The project uses Django app tests. Important test areas include upload validation, owner isolation, OCR behavior, extraction patterns, review separation, FHIR-shaped export, timeline display, appointments, notifications, and admin authorization. The tests validate code behavior, not clinical correctness. Medical extraction requires a separate representative, clinician-reviewed accuracy study before real clinical use.

Typical checks:

```powershell
py manage.py check
py manage.py makemigrations --check --dry-run
py manage.py test prescriptions core
```

## 12. Known gaps and roadmap

1. Create a manually transcribed representative OCR dataset and measure character/field accuracy.
2. Expand extraction through a versioned parser with provenance and confidence; avoid hidden heuristic claims.
3. Add patient review for all extracted fields, not only medicines, and maintain an explicit provenance/status per value.
4. Validate lab-context content with qualified clinical reviewers; distinguish source interval from general reference knowledge.
5. If true AI summarization is required, decide local versus external processing, consent, model governance, clinical review, auditability, and safe fallbacks before implementation. Keep generated content separate from source facts and never diagnose.
6. Add production-grade private object storage, malware scanning evaluation, retention controls, monitoring, and load-tested asynchronous document jobs.
7. Validate FHIR resources against a selected implementation guide and pursue ABDM integration only after requirements, consent flows, and certification planning.
8. Complete accessibility and regional localization.

## 13. Demo script (3–4 minutes)

1. Introduce the fragmentation problem and MediMate’s privacy-first prototype.
2. Sign in as a demo patient and open Health Profile.
3. Upload an explicitly fictional sample lab report; show local OCR and retained source.
4. Review possible values, print-range comparison, source-linked general context, and limitations.
5. Open extracted fields/review and show patient corrections remain distinct from raw OCR.
6. Return to the unified timeline and open the report.
7. End by stating: rule-based prototype; no diagnosis; no clinical accuracy claim; fictional ABHA-style ID; FHIR-shaped export only; no ABDM integration.

Use synthetic demo records only. Do not project real patient data.
