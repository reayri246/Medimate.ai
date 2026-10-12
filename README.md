# MediMate AI

MediMate AI is a Django application for organizing health records, tracking measurements and appointments, browsing medicine reference content, and running deterministic safety guidance. MediGuard is rule-based software, not a trained or clinically validated model, and this project is not a medical device or replacement for a licensed professional.

The local symptom guide asks about age, symptoms, duration, severity, and symptom trend. It applies deterministic rules in the Django app; symptom entries are not sent to an AI service or stored by the guide. It cannot diagnose disease or rule out emergencies, and it does not use symptoms to recommend medicines. The medicine-comparison workflow compares only ingredient compositions explicitly verified by an administrator against cited sources. It identifies possible duplicate active ingredients, but it does not establish that a combination is safe; verified interaction data is not currently configured. For treatment or prevention specific to you, consult a qualified clinician or pharmacist. Emergency guidance and reference content require clinical review before real-world use.

### Managing verified medicine information

After creating an administrator account, open `/admin/` and add an Active ingredient entry for each normalized ingredient. Use a source-backed standard name; enter alternate names only when reviewed and supported by the cited source, then record the source and verification date. Add a Medicine and attach its ingredients using the inline ingredient rows, including strength and unit. Enter the medicine source and last-verified date. Enable **Safety data verified** only after a qualified reviewer checks the composition against the cited product source. Only medicines whose own record and every ingredient have verification sources and dates appear in comparisons. Do not use unverified sample/test catalog content for patient decisions.

The comparison page is `/medicines/compare/`. It detects overlapping verified ingredient names or administrator-entered, source-backed aliases. The project does not currently include a verified drug-interaction dataset; for every selected pair it explicitly reports that interaction information could not be verified. Never interpret an absence of duplicate ingredients as a safe combination.

The local health assistant at `/assistant/` answers a small set of general health questions, flags selected emergency symptom phrases, and can display source-backed details for medicine catalog entries that have been verified. It does not use a generative model, predict health outcomes, diagnose, or recommend medicines based on symptoms. Unrecognized questions are answered with an explicit note that verified information is unavailable.

Record uploads at `/prescriptions/` are labeled by type (prescription, lab report, discharge summary, diagnostic record, or other) and can extract text from TXT files, text-based PDFs, and images when Tesseract OCR is installed. A local, deterministic extractor lists possible catalog-matched medicine names, nearby dosage text, selected labeled lab values, dates, and text explicitly labeled as diagnosis/impression/assessment. If a reference range is printed on the same line as a supported lab value, it may compare the extracted value with that printed interval; it does not determine clinical significance, infer diagnoses, or recommend treatment. Review all results against the source. Handwriting and poor-quality scans can be misread; scanned PDFs do not currently have an OCR/rendering pipeline.

The record screen supports an English/Telugu summary and Telugu+English image OCR when the Tesseract Telugu language data pack is installed. OCR runs locally; without the Telugu pack, image OCR falls back to English and labels that limitation. This is not a full Telugu translation of the application. The signed-in health profile at `/health-profile/` combines records, uploads, measurements, appointments, and activity into a timeline. Each document can be exported as a minimal FHIR R4-shaped JSON bundle for demonstration; OCR-derived observations remain preliminary and include a source-review warning. The demo ABHA-style identifier is fictional, not an ABHA ID, and there is no ABDM integration. The export is not certified for clinical exchange.

Each upload has a patient-only review page where the user can correct the recognized text, optionally choose an exact catalog entry, enter strength/instructions only as seen in the source, or mark a field unreadable. Raw OCR remains unchanged and is shown separately from patient-entered review data. A patient's confirmation is not professional verification. Upload, viewed, review, download, and export actions are logged without copying extracted health text into the audit metadata. The owner-scoped JSON endpoint is `/prescriptions/<document-id>/api.json`; it requires the user's authenticated session and is not cacheable.

Prescription uploads also have an owner-only **Open printable soft copy** view. It lays out the original extracted text, exact name-match candidates, dosage lines as read, and explicit quantity/strength mentions when recognized. Ingredient composition appears only for a fully source-verified catalog match and is labeled catalog information—not the prescribed dose. Use **Print / Save as PDF** in the browser to make a local copy. Missing fields are left blank/not recognized; this feature does not infer dose, duration, ingredient amounts, or what treatment to take. Viewing the soft copy is audit logged.

The current OCR/recognition path is a local rules/catalog-match prototype, not a fine-tuned handwritten-prescription model. It does not emit validated recognition confidence and does not perform fuzzy substitutions. No prescription training dataset or pretrained handwriting model is bundled, and no clinical reliability claim is made. Do not treat candidates as a confirmed prescription.

## Local development on Windows

Requirements: Python 3.12+, PostgreSQL only if you choose to use it locally, and Tesseract only for image OCR.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
py manage.py migrate
py manage.py seed_data
py manage.py runserver
```

Open `http://127.0.0.1:8000/`. The development-only sample account created by `seed_data` is Devashish (username `demo_patient`, password `demo12345`). The command adds clearly labeled sample measurements, upcoming appointments, recent activity, and medical records, as well as unverified medicine placeholders. All health values and records are illustrative only; placeholders are not usable in medicine safety comparisons. It is idempotent and does not overwrite existing medicine entries. Never seed sample data in a live environment; the command refuses when `DEBUG=False`.

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

For image OCR, install Tesseract separately on Windows and add its installation directory to `PATH`. Install the Telugu trained data file (`tel.traineddata`) alongside the English pack to enable Telugu+English OCR. Text PDFs are extracted with pypdf; scanned PDFs require an OCR/rendering pipeline that is not currently included.

## Production deployment baseline

Deploy on a supported Linux host or container with PostgreSQL, TLS termination, persistent private document storage, and a process manager. Use Waitress on Windows or Gunicorn on Linux for WSGI serving; neither removes the need to configure the production settings below.

Set deployment variables in the hosting platform's secret/environment configuration (do not commit `.env`):

- `DEBUG=False`
- `SECRET_KEY` to a newly generated, unique random value of at least 50 characters (`py -c "import secrets; print(secrets.token_urlsafe(64))"` can generate one).
- `ALLOWED_HOSTS` to exact hostnames, comma-separated, with no wildcard.
- `CSRF_TRUSTED_ORIGINS` to HTTPS origins if requests are made across origins.
- `USE_POSTGRES=True` and `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`; the default production SSL mode is `require`. Choose a stricter provider-supported SSL mode when available.
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
