# Product Requirements Document

## 1. Product overview

**Product:** MediMate AI — AI-Powered Personal Health Copilot prototype  
**Document date:** October 13, 2026  
**Status:** Prototype requirements and current-state assessment

MediMate AI is a web application for patients to organize health information, upload and review medical documents, track selected wellness measurements, and manage appointments and notifications. The current implementation provides local OCR, deterministic extraction, and limited rule-based explanations. Despite the product name and challenge framing, it is not a generative-AI clinical copilot.

## 2. Problem statement

Patients may have prescriptions, laboratory reports, discharge summaries, diagnostic records, personal notes, wellness readings, and appointments in separate places. They need a private, understandable way to collect and review these materials and find them again.

## 3. Goals

1. Accept common medical record files and preserve the original for comparison.
2. Extract a limited set of readable facts into reviewable fields.
3. Explain supported common laboratory tests in cautious, plain language without diagnosing.
4. Present records, measurements, appointments, and related activity in an owner-scoped health profile and timeline.
5. Make uncertainty, data ownership, consent, and system limitations apparent.
6. Demonstrate a path toward structured health-data exchange without claiming ABDM certification or integration.

## 4. Non-goals and safety boundaries

- Diagnosing disease, predicting an individual's health, or interpreting a record as a clinician.
- Recommending medicines, dose, or treatment from uploaded symptoms or OCR.
- Replacing a clinician, pharmacist, emergency service, or validated laboratory system.
- Guaranteeing OCR accuracy, handwriting recognition, or completeness of extraction.
- Claiming ABHA identity verification, ABDM connectivity, certified FHIR interoperability, or clinical-device status.
- Using external AI to process document content in the current local-only flow.

## 5. Users and roles

### Patient

- Registers and signs in to a personal account.
- Uploads documents, reviews extracted text, corrects selected recognized medicine fields, views measurements and timeline, and requests appointments.
- Can access only records owned by that account through patient-facing views.

### Staff / linked doctor

- Handles appointment requests through the appointment desk where authorized.
- Reviews appointment details and accepts or rejects requests according to application permissions.

### Administrator

- Manages users, doctors, schedules, medicines, catalog sources, notifications, appointment decisions, and administrative activity through Django Admin and the admin portal.
- May have access to uploaded records for operational purposes; production deployments must define and disclose such access.

## 6. Product scope

### 6.1 Medical-record upload and OCR

**Supported document categories:** prescription, lab report, discharge summary, diagnostic record, and other medical record.  
**Supported formats in the current upload flow:** text files, PDF, PNG, JPG/JPEG, BMP, and TIFF subject to upload validation.

Requirements:

- Associate every upload with the authenticated owner.
- Preserve the original file and extracted text separately.
- Read embedded text from PDFs; use local Tesseract OCR for supported images and scanned PDF pages.
- Process at most 20 PDF pages for OCR and disclose page/OCR limitations.
- Permit English and optional Telugu+English OCR when the Telugu language pack is installed; disclose English-only fallback.
- Extract possible catalog-matched medicine names, dosage/strength text, selected lab test values, printed same-line reference intervals, recognizable dates, and text explicitly labeled diagnosis/impression/assessment.
- Keep detected fields visibly provisional and support patient review/correction separately from raw OCR.

### 6.2 Plain-language report context

Requirements:

- Explain what selected common lab tests measure.
- When the same-line numeric value and printed interval can be parsed, describe whether the value is below, within, or above that printed interval.
- For a limited supported test library, provide general associations for out-of-range results, with a source link and clear educational disclaimer.
- Do not infer diagnosis, urgency, cause, or treatment.
- Do not silently interpret unsupported tests or values with missing/untrusted units/ranges.
- Maintain a clear distinction between rule-based content and AI-generated content. The current implementation is rule-based and does not generate a patient-specific medical interpretation.

### 6.3 Unified health profile

Requirements:

- Show a single chronological timeline for the signed-in user's health measurements, appointments, personal records, uploads, and notification activity.
- Link timeline entries to owner-scoped detail views.
- Display report review state and a short, bounded summary of detected fields without exposing raw documents to unrelated users.
- Provide a way to reach upload, tracking, appointments, and individual records.

### 6.4 Adjacent prototype features

- Medicine catalog with source/verification metadata and a bounded informational assistant.
- Appointment request, doctor matching against administrator-maintained symptom/concern terms, doctor work schedules, staff/doctor/admin decisions, in-app notifications, and reminder support.
- Personal medical notes and wellness measurements.
- In-app notification list and administrator composition.
- Minimal FHIR-shaped document export for demonstration.

## 7. Functional requirements

| ID | Requirement | Current implementation |
|---|---|---|
| FR-01 | Sign-in required for patient records and uploads | Implemented with Django authentication and owner filters |
| FR-02 | Upload categorized document and preserve original | Implemented |
| FR-03 | Extract local text from embedded PDF text, scanned PDF, or supported image | Implemented with pypdf, PyMuPDF, Pillow, and Tesseract; OCR capped at 20 PDF pages |
| FR-04 | Extract medicines, dosage text, selected lab values, date strings, and labeled diagnosis text | Partial, deterministic patterns/catalog matching |
| FR-05 | Let patients review/correct extracted medicine fields separately from OCR | Implemented for medicine review; does not constitute clinician verification |
| FR-06 | Provide general sourced context for selected lab results | Implemented as bounded local rules, not generative AI |
| FR-07 | Show original document beside extracted content when supported | Implemented for images; PDFs provide download for source comparison |
| FR-08 | Aggregate health activity in one profile timeline | Implemented; current source view limits each category and overall visible history |
| FR-09 | Keep uploaded reports private and prevent cross-account access | Implemented in patient-facing views; production storage and deployment controls still required |
| FR-10 | Export structured data in a standards-shaped bundle | Minimal FHIR-shaped demo export; not validated/certified exchange |
| FR-11 | Provide real ABDM/ABHA connection | Not implemented |
| FR-12 | Generate clinically validated AI report explanations | Not implemented |

## 8. Non-functional requirements

- **Privacy:** Owner-scoped retrieval; private/no-store responses for sensitive document endpoints; audit access events without placing extracted health text in audit metadata.
- **Safety:** Disclaimers, source verification, no medicine/dose recommendations, explicit uncertainty, no clinical claims.
- **Security:** Django authentication and CSRF protections, password validators, safe upload validation, secure production settings, HTTPS, PostgreSQL, private persistent media storage.
- **Accessibility:** Semantic headings, labels, readable contrast, keyboard-accessible controls, responsive layouts.
- **Reliability:** Clear errors for unavailable OCR or unsupported files; retain original file when extraction is incomplete.
- **Performance:** Synchronous upload processing currently; file size limits and page/time bounds reduce exposure, but large concurrent workloads require performance testing and likely background jobs.
- **Localization:** English UI with selected English/Telugu summary text and optional Telugu OCR; not a fully localized interface.

## 9. Success measures

Prototype readiness:

- Upload → extraction → review → timeline flow completes using representative sample documents.
- Every extracted datum can be compared to original source text/image.
- Owner-isolation tests pass for document endpoints.
- OCR/extraction field accuracy is measured against a manually labeled, representative evaluation set before any clinical reliability claim.
- No model output or template implies diagnosis or treatment recommendation.
- Demo clearly distinguishes prototype functionality from roadmap and certified integrations.

No current validated OCR/clinical accuracy percentage is claimed.

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| OCR misreads handwritten names, values, units, or dates | Show original and raw OCR; require user review; label provisional |
| Regex extraction misses values or associates wrong ranges | Limit recognized labels; retain source text; test against manually annotated data |
| Generic test context is mistaken for personal diagnosis | Use cautious language, citations, and clinician referral; never infer diagnosis |
| Uploaded medical data exposed through deployment/storage configuration | Private persistent storage, least privilege, TLS, owner access checks, backups and retention policy |
| Prototype FHIR/ABHA claims are overstated | Mark export as FHIR-shaped demonstration and demo ID as fictional |
| External service changes local-processing privacy boundary | Keep external processing disabled unless explicit informed consent and privacy review are introduced |

## 11. Acceptance criteria for challenge demonstration

1. A sample prescription and sample lab report can be uploaded and opened by their owner.
2. Original source and extracted text are available for comparison.
3. Supported names, dose text, lab values, diagnoses explicitly labeled in source, and dates appear as provisional extracted fields.
4. A recognized lab test has cautious plain-language context; unsupported test names do not receive invented meaning.
5. User can review fields and see patient-review state without confusing it for clinician approval.
6. Health profile combines upload, measurement, appointment, note, and activity entries.
7. Unauthorized user cannot access another patient's document.
8. Demo presentation discloses limitations and missing production integrations.
