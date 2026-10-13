# Technical Requirements Document

## 1. System summary

MediMate AI is a server-rendered Django application with app-based modules, relational persistence, local filesystem media storage by default, and synchronous document extraction. In production, settings require PostgreSQL and explicit security configuration. Local document content is processed by the application; no external document AI service is used by the current upload flow.

## 2. Technology stack

- Python 3.12+
- Django 5.2
- PostgreSQL for all environments
- Django templates, Bootstrap 5.3, Bootstrap Icons, project CSS/JavaScript
- pypdf for embedded PDF text; PyMuPDF for rendering scanned PDF pages
- Pillow for image normalization; pytesseract/Tesseract for OCR
- WhiteNoise for static asset serving
- Waitress on Windows; Gunicorn on Linux/Render

## 3. Runtime components

### Web application

`config.wsgi:application` is the WSGI entry point. Root routing delegates to apps for accounts, core pages, medicines, prescriptions, assistant, personal records, health tracking, appointments, notifications, admin portal, and Django Admin.

### Document extraction

1. Authenticated user submits file and category through `prescriptions`.
2. Upload form validates file type and size.
3. Text PDF extraction uses pypdf. Pages with little/no embedded text may be rendered by PyMuPDF and OCRed by Tesseract.
4. Images are orientation-corrected, converted to grayscale/autocontrast, and processed in grayscale and thresholded variants; the OCR pass with best average word confidence is selected.
5. Extracted text is saved on `DocumentUpload`; deterministic extraction creates JSON fields for possible medicines, prescription items, dosage mentions, selected test values, diagnosis-label matches, and dates.
6. The owner sees original/document text and derived summary; patient corrections are stored separately.
7. Audit records capture upload, view, review, download, and export events.

Current bounds: 100,000 characters for structured record extraction; up to 20 pages for scanned-PDF OCR; OCR calls have a 15-second timeout per image. The full upload request is synchronous.

### Lab-context layer

`lab_explanations.py` maps known lab-name aliases to concise educational text. Context is added in the view at render time and does not mutate stored extraction data. A below/above association is shown only when the extracted test name is recognized and the extractor has compared a numeric value against an interval printed on the same line. The source link points to general MedlinePlus lab-test information; this is not a validated clinical knowledge base or AI model.

### Unified health profile

`core.health_profile` loads user-scoped measurements, appointments, personal records, uploads, and notifications, composes timeline items, sorts by timestamp, and returns up to 100 items. For uploads, the view includes a bounded set of detected medicines, values, diagnosis/impression text, dates, and review state.

## 4. Data model overview

| Entity | Purpose / key fields |
|---|---|
| `accounts.User` | Django user plus role, phone, emergency contact, DOB, fictional demo ABHA-style identifier |
| `prescriptions.DocumentUpload` | Owner, title, category, file, raw extracted text, JSON extracted fields, reviewed medicine JSON, OCR language, review status, timestamps |
| `prescriptions.PrescriptionAuditLog` | Document, actor, action, limited metadata, timestamp |
| `medical_records.MedicalRecord` | Owner, title, record type, note text, created timestamp |
| `health_tracking.HealthMeasurement` | Owner, date, weight, blood pressure, heart rate, temperature, glucose, notes |
| `appointments.Doctor` | Specialty, qualifications, matching terms, photo, active status, optional linked account |
| `appointments.DoctorWorkingDay` | Doctor, weekday, start and end time |
| `appointments.DoctorAvailability` | Doctor, date-specific on/off duty and hours override |
| `appointments.Appointment` | Patient, doctor, requested/scheduled date, symptoms, consent, status, notes, reminder marker |
| `appointments.AppointmentActivity` | Actor, appointment/doctor, action description and time |
| `notifications.Notification` | Owner, title/body, optional local URL, read state and timestamp |
| Medicines catalog | Medicine, active ingredients, source and verification fields used for exact name matches and reference display |

Extracted JSON is a prototype schema, not a normalized clinical terminology store. Patient-edited medicine fields are stored separately from OCR text.

## 5. Interfaces and routes

| Route prefix | Module | Typical purpose |
|---|---|---|
| `/` | Core | Public landing page |
| `/accounts/` | Accounts | Register, sign in/out, profile |
| `/health-profile/` | Core | Patient's unified profile/timeline |
| `/prescriptions/` | Prescriptions | Upload, list, detail, review, download, JSON and FHIR-shaped export |
| `/records/` | Medical records | Personal notes and report list/details |
| `/tracking/` | Health tracking | Wellness measurements |
| `/assistant/` | Health assistant | Bounded deterministic general info and verified catalog lookup |
| `/medicines/` | Medicines | Medicine/ingredient search and detail |
| `/appointments/` | Appointments | Request, queue/desk, status and patient letter |
| `/notifications/` | Notifications | Patient in-app notifications |
| `/portal/` | Admin portal | Staff/admin overview and notifications |
| `/admin/` | Django Admin | Operational and catalog administration |
| `/healthz/` | Core | Database connectivity health check |

## 6. Security and privacy requirements

- Authenticate access to private record views and query records using both object ID and current user.
- Return sensitive document responses with `Cache-Control: private, no-store`; set `X-Content-Type-Options: nosniff` where appropriate.
- Serve downloads as attachments and do not expose media as public static content.
- Keep audit metadata free of extracted medical text.
- Use CSRF protection, Django password validators, secure cookies, HTTPS redirects, HSTS configuration, explicit hosts, and production secrets.
- Configure production PostgreSQL and persistent private object/file storage. Standard Render web filesystem is not persistent for media; production document retention needs a configured private persistent volume or private object storage.
- Apply file size/upload count bounds and safe file types. Malware scanning and content-disarm are not currently indicated in the implementation and should be evaluated for production.
- Define access/retention policy, backups, incident response, and legal/privacy review per deployment.

## 7. Deployment requirements

### Development

- Python 3.12+, requirements installation, migrations.
- Tesseract executable required for image and scanned-PDF OCR.
- `tel.traineddata` required for Telugu OCR; otherwise explicit English OCR fallback.
- PostgreSQL is required in development and production.

### Production

- `DEBUG=False`, unique secret key, explicit `ALLOWED_HOSTS`.
- PostgreSQL configured via `DATABASE_URL` or required DB settings.
- HTTPS, CSRF trusted origins, secure cookie/HSTS review.
- Persistent private document storage with backups and retention configuration.
- Linux/Gunicorn or Windows/Waitress; health monitoring at `/healthz/`.
- Run `manage.py check --deploy`, migrations, and `collectstatic`.
- Do not use sample/seed data in live environment.

## 8. Operational and quality requirements

- Keep OCR and extraction bounded and synchronous for current prototype; monitor request latency and errors.
- For scale, move OCR to a job queue with status, retry, and failure reporting; preserve uploaded source.
- Test parser output with a versioned, manually labeled dataset; report field-level precision/recall and OCR character error rate before claiming accuracy.
- Regression-test ownership boundaries, upload validation, OCR error paths, extraction correctness, summary rendering, review data separation, and timeline links.
- Add accessibility/responsive checks to user-facing pages.

## 9. Current technical limitations

- OCR uses Tesseract and can fail on handwriting, skew, low resolution, stamps, columns, and ambiguous notation.
- Experimental CRNN line recognizer is disconnected from the upload flow and not validated for clinical use.
- The pattern extractor only recognizes a defined subset and may miss or mis-associate values, units, and ranges.
- Many medication instructions are not fully parsed; exact catalog matching can miss non-catalog names and should not imply prescription verification.
- Lab context is deterministic/static and general, not patient-specific, not generated by AI, and not a clinician-reviewed diagnostic engine.
- Telugu UI coverage is incomplete; Telugu OCR depends on installed data.
- FHIR-shaped export is minimal and not standards validated or ABDM-connected.
- File extraction runs inline, not asynchronously; deployment capacity and large-document behavior need load testing.
