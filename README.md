# MediMate AI

MediMate AI is a Django application for organizing health records, tracking measurements and appointments, browsing medicine reference content, and reviewing uploaded medical documents. It is not a medical device or replacement for a licensed professional.

> **Educational project only:** MediMate AI is a prototype created for learning and demonstration purposes. It is not a real-time healthcare application, and its information or features must not be used to make medical decisions or guide treatment.

Public **Terms & Conditions** (`/terms/`) and **Privacy Policy** (`/privacy/`) pages are linked from the site footer. Their descriptions of hosting, administrator access, retention, and applicable rights should be reviewed and adapted by the administrator for each deployment before production use.

Symptom checking and medicine-comparison features have been removed. The local health assistant answers a small set of general health questions, flags selected emergency phrases, and can display source-backed details for verified medicine catalog entries. It does not diagnose, predict health outcomes, or recommend medicines based on symptoms. For treatment specific to you, consult a qualified clinician or pharmacist. Emergency guidance and reference content require clinical review before real-world use.

Signed-in users can request a consultation at `/appointments/request/`. Doctor suggestions are matched locally against administrator-entered symptoms/concerns on each doctor profile and are limited to doctors marked active and on duty for the selected date. Matching allows simple singular/plural word forms and ignores common descriptive words; it does not send text to a remote AI model, diagnose, or recommend treatment, and unmatched terms are not guessed. Administrators maintain the comma/newline-separated consultation terms and recurring weekly workdays under `/admin/` > Appointments > Doctors. Add a **Doctor working days** row for each regular weekday (for example, three or six rows), and optionally add a dated **Doctor availability** override for a specific exception; an explicit off-duty override takes precedence over the weekly schedule. Running `python manage.py seed_data` in development creates clearly labeled demo doctors for every specialty, with sample symptoms and three- or six-day weekly schedules. The sample neurologist is scheduled six days per week. The application date/time zone is Asia/Kolkata. Submitting an appointment requires a separate consent checkbox that shares the entered symptoms and selected date with the chosen doctor and the consultation office/reception desk. Office staff receive an in-app queue notification, the assigned doctor receives an in-app notification when an account is linked, and the user can open and print their appointment letter. These are in-app deliveries; SMTP/email delivery is not configured. Staff or the linked doctor can accept or reject a request, and patients receive an in-app status notification. The administrator-only `/portal/` overview shows recent appointment, doctor, prescription, and staff admin activity.
Signed-in users can request a consultation at `/appointments/request/`. Doctor suggestions are matched locally against administrator-entered symptoms/concerns on each doctor profile and are limited to doctors marked active and on duty for the selected date. Matching allows simple singular/plural word forms and ignores common descriptive words; it does not send text to a remote AI model, diagnose, or recommend treatment, and unmatched terms are not guessed. Administrators maintain the comma/newline-separated consultation terms, optional doctor photos, and recurring weekly workdays under `/admin/` > Appointments > Doctors. Add a **Doctor working days** row for each regular weekday (for example, three or six rows), and optionally add a dated **Doctor availability** override for a specific exception; an explicit off-duty override takes precedence over the weekly schedule. Running `python manage.py seed_data` in development creates clearly labeled demo doctors for every specialty, with sample symptoms and three- or six-day weekly schedules. The sample neurologist is scheduled six days per week. The application date/time zone is Asia/Kolkata. Submitting an appointment requires a separate consent checkbox that shares the entered symptoms and selected date with the chosen doctor and the consultation office/reception desk. Office staff receive an in-app queue notification, the assigned doctor receives an in-app notification when an account is linked, and the user can open and print their appointment letter. These are in-app deliveries; SMTP/email delivery is not configured. Staff or the linked doctor can accept or reject a request, and patients receive an in-app status notification. For scheduled reminders, run `python manage.py send_appointment_reminders` periodically using the host scheduler (for example, Windows Task Scheduler); each upcoming appointment receives at most one in-app reminder. The administrator-only `/portal/` overview shows recent appointment, doctor, prescription, and staff admin activity.

Doctor weekly schedules include start/end hours, defaulting to 9:00 AM–5:00 PM. Administrators enter each weekday’s hours in 12-hour format with an explicit AM or PM (for example, `09:00 AM` and `05:00 PM`) in the **Doctor working days** inline on a doctor profile. Available-doctor listings show those hours, and staff must select an appointment time within that window. Date-specific **Doctor availability** rows use the same 12-hour AM/PM format and override weekly hours for that date.

### Managing verified medicine information

After creating an administrator account, open `/admin/` and add an Active ingredient entry for each normalized ingredient. Use a source-backed standard name; enter alternate names only when reviewed and supported by the cited source, then record the source and verification date. Add a Medicine and attach its ingredients using the inline ingredient rows, including strength and unit. Enter the medicine source and last-verified date. Enable **Safety data verified** only after a qualified reviewer checks the composition against the cited product source. The health assistant only displays catalog medicine details when the medicine and its ingredients have complete verification sources and dates. Do not use unverified sample/test catalog content for patient decisions.

The local health assistant at `/assistant/` answers a small set of general health questions, flags selected emergency symptom phrases, and can display source-backed details for medicine catalog entries that have been verified. It does not use a generative model, predict health outcomes, diagnose, or recommend medicines based on symptoms. Unrecognized questions are answered with an explicit note that verified information is unavailable.

Record uploads at `/prescriptions/` are labeled by type (prescription, lab report, discharge summary, diagnostic record, or other). Text-based PDFs are read directly; scanned PDFs (up to 20 pages) and supported images use local Tesseract OCR. The OCR keeps page labels, attempts grayscale and thresholded image passes, and selects the pass with the strongest average word-confidence score; this is only a technical heuristic, not verified accuracy. A local deterministic extractor lists possible catalog-matched medicine names, nearby dosage text, selected labeled lab values, dates, and text explicitly labeled as diagnosis/impression/assessment. If a reference range is printed on the same line as a supported lab value, it may compare the extracted value with that printed interval. The application does not determine clinical significance, diagnose disease, or select treatment. Review every OCR character, digit, unit, and date against the source; handwriting and poor-quality scans can still be misread.

The report list and document detail page provide source-linked, rule-based plain-language context for selected common lab tests. When a matched value is outside a reference interval printed on the report, the page may describe general associations for that test; this is educational information, not an AI-generated clinical interpretation, diagnosis, or explanation of an individual's result. Context is limited to known test labels, does not change stored uploads or extracted data, and links to MedlinePlus lab-test information. Unrecognized tests receive no general explanation. Structured test extraction includes only a supported subset of common lab names; all detected findings remain provisional until checked against the source document.

After every upload, the owner-only document page displays the original image (when the upload is an image) beside the complete local OCR text. PDFs show the extracted page text with a link to download the original. The original file is retained for comparison, and the full text remains separate from any patient corrections.

Uploaded documents are processed locally; document contents are not sent to an external AI service. The assistant is a bounded local information service, not a generative model. It answers supported general health questions and does not diagnose, recommend medicines, or interpret a patient's records as a clinical assessment.

The record screen supports an English/Telugu summary and Telugu+English image OCR when the Tesseract Telugu language data pack is installed. OCR runs locally; without the Telugu pack, image OCR falls back to English and labels that limitation. This is not a full Telugu translation of the application. The signed-in health profile at `/health-profile/` combines records, uploads, measurements, appointments, and activity into a timeline. Each document can be exported as a minimal FHIR R4-shaped JSON bundle for demonstration; OCR-derived observations remain preliminary and include a source-review warning. The demo ABHA-style identifier is fictional, not an ABHA ID, and there is no ABDM integration. The export is not certified for clinical exchange.

Administrators can manage pending/accepted/rejected appointments from Django Admin → Appointments → Appointment management. Admin acceptance requires an active doctor on duty at a time inside the doctor’s configured hours. A status change to accepted or rejected creates an in-app patient notification with a link to the appointment letter. Staff and assigned doctors can also decide requests through the in-app appointment desk. Administrators can send in-app notices to all active accounts or multiple selected users from Django Admin → Notifications → Notifications → Send notifications (or from `/portal/notifications/`). These notices are delivered only in the application, and optional links must be local site paths. In development, `python manage.py seed_data` adds clearly labeled sample notifications to the demo patient; the seed command refuses to run when `DEBUG=False`.

Each upload has a patient-only review page where the user can correct the recognized text, optionally choose an exact catalog entry, enter strength/instructions only as seen in the source, or mark a field unreadable. Raw OCR remains unchanged and is shown separately from patient-entered review data. A patient's confirmation is not professional verification. Upload, viewed, review, download, and export actions are logged without copying extracted health text into the audit metadata. The owner-scoped JSON endpoint is `/prescriptions/<document-id>/api.json`; it requires the user's authenticated session and is not cacheable.

Prescription uploads also have an owner-only **Open printable soft copy** view. It lays out the original extracted text, exact name-match candidates, dosage lines as read, and explicit quantity/strength mentions when recognized. Ingredient composition appears only for a fully source-verified catalog match and is labeled catalog information—not the prescribed dose. Use **Print / Save as PDF** in the browser to make a local copy. Missing fields are left blank/not recognized; this feature does not infer dose, duration, ingredient amounts, or what treatment to take. Viewing the soft copy is audit logged.

An experimental CRNN was trained locally on 14 single-line crops from illustrative records using draft transcriptions that have not been independently verified. Its weights are local under the ignored `artifacts/` folder and are not included with the application. A line-only predictor is available for experiments after installing `requirements-crnn.txt`; it does not detect text lines or replace the app's Tesseract full-page OCR. Initial predictions omitted or changed medicine names and strengths, so this model is not reliable and must not be used to read prescriptions or guide treatment. It has no independent validation set and makes no clinical reliability claim. Use only manually verified transcriptions and a sufficiently large, representative dataset for further training.

## Local development on Windows

Requirements: Python 3.12+, PostgreSQL, and Tesseract only for image OCR.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
# Set DB_PASSWORD in .env to the password for your local PostgreSQL user.
py manage.py migrate
py manage.py seed_data
py manage.py runserver
```

PostgreSQL is required for local development and production. Configure either `DATABASE_URL` or `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and `DB_HOST` in `.env`; SQLite is not used.

To import an existing `db.sqlite3` into a **new, migrated, empty PostgreSQL database**, first back up both databases and configure `.env` for the PostgreSQL target. Then run:

```powershell
py manage.py migrate
py manage.py migrate_sqlite_to_postgres --source db.sqlite3 --yes
```

The importer refuses to load into a PostgreSQL database that already contains application data. It copies database records only; copy the referenced files from `media` to the configured persistent media storage separately. Keep the SQLite database and its backup until the PostgreSQL deployment has been verified. Review and remove illustrative/demo records before importing into a live environment.

Open `http://127.0.0.1:8000/`. The development-only sample account created by `seed_data` is Devashish (username `demo_patient`, password `demo12345`). The command adds clearly labeled sample measurements, upcoming appointments, recent activity, and medical records, as well as unverified medicine placeholders. All health values and records are illustrative only; placeholders are not suitable for medical decisions. It is idempotent and does not overwrite existing medicine entries. Never seed sample data in a live environment; the command refuses when `DEBUG=False`.

To add a separate illustrative health report to an existing patient's account without changing their password or overwriting readings already recorded on those dates, run `py manage.py seed_patient_report --username devashish`. The command only runs when `DEBUG=True`; it adds explicitly labeled sample measurements and a fictional lab report. Replace or delete all sample data before using the account with real health information.

### Run the WSGI application on Windows

To serve the project through its WSGI entry point instead of Django's development server, run:

```powershell
waitress-serve --listen=127.0.0.1:8000 config.wsgi:application
```

Or use the included launcher:

```powershell
.\run_wsgi.ps1
```

This uses Waitress, a Windows-compatible WSGI server. It does not configure production environment variables or replace TLS termination, PostgreSQL, persistent private file storage, or deployment security settings.

### Deploy to Render

This is a Django project; its WSGI application is `config.wsgi:application` (not `app:app`). The included [render.yaml](./render.yaml) defines the correct Gunicorn command, binds to Render's assigned port, collects static files, provisions a PostgreSQL database, and runs database migrations at startup. To use it, create/update the Render service from the repository's Blueprint.

The Blueprint passes Render's database connection URL as `DATABASE_URL`; Django requires PostgreSQL and fails startup if its connection settings are missing. Render is detected from its environment, which disables Django debug pages. Also set `ALLOWED_HOSTS` to the service hostname and `CSRF_TRUSTED_ORIGINS` to its HTTPS origin (for example, `https://your-service.onrender.com`). Render generates `SECRET_KEY`; keep it private. Uploaded media is not persistent on a standard Render web-service filesystem, so configure persistent private storage before relying on prescription uploads in production.

For image and scanned-PDF OCR, install Tesseract separately on Windows and add its installation directory to `PATH`. Install the Telugu trained data file (`tel.traineddata`) alongside the English pack to enable Telugu+English OCR. The Render Blueprint installs Tesseract English and Telugu language packs during the build.

## Production deployment baseline

Deploy on a supported Linux host or container with PostgreSQL, TLS termination, persistent private document storage, and a process manager. Use Waitress on Windows or Gunicorn on Linux for WSGI serving; neither removes the need to configure the production settings below.

Set deployment variables in the hosting platform's secret/environment configuration (do not commit `.env`):

- `DEBUG=False`
- `SECRET_KEY` to a newly generated, unique random value of at least 50 characters (`py -c "import secrets; print(secrets.token_urlsafe(64))"` can generate one).
- `ALLOWED_HOSTS` to exact hostnames, comma-separated, with no wildcard.
- `CSRF_TRUSTED_ORIGINS` to HTTPS origins if requests are made across origins.
- `DATABASE_URL` or `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`; the default production SSL mode is `require`. Choose a stricter provider-supported SSL mode when available.
- `SECURE_SSL_REDIRECT=True` and `SECURE_HSTS_SECONDS=31536000` only after HTTPS is verified end-to-end. Set `SECURE_HSTS_INCLUDE_SUBDOMAINS=True` only if every subdomain is HTTPS-ready. HSTS preload is opt-in and should only be enabled after reviewing the browser preload requirements. If a trusted reverse proxy terminates TLS, set `TRUST_X_FORWARDED_PROTO=True` only when that proxy overwrites the forwarded-proto header and prevents client spoofing.

On the release/deploy step, run:

```text
python manage.py check --deploy
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

Start the web process with:

```text
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 60
```

Configure the platform to monitor `/healthz/`; it returns HTTP 200 when the database is reachable and HTTP 503 otherwise. Use a persistent private volume or private object storage for uploaded documents. Do not serve the `media` directory as a public static path. The document download route checks the signed-in user's ownership and returns an attachment with `nosniff` and `no-store` headers.

Before handling real patient data, an operator still needs to configure encrypted and tested backups, retention/deletion processes, private storage and access policies, malware scanning, monitoring/alerting, incident response, rate limiting, and a formal privacy/security/legal review appropriate to the deployment jurisdiction. Static reference content and safety rules also require clinical review; the sample catalog is demonstration data and not a complete drug database.
