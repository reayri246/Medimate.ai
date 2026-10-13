# MediMate AI — Project Documentation

This folder contains the product requirements, technical design, architecture and workflow diagrams, an implementation explanation, and a presentation deck for the current MediMate AI prototype.

## Files

- [Product Requirements Document](./PRD.md) — problem, users, scope, requirements, success criteria, and risks.
- [Technical Requirements Document](./TRD.md) — implementation architecture, data, interfaces, security, deployment, and operational requirements.
- [Architecture diagram](./architecture.svg) — current system components and data boundaries.
- [Workflow](./WORKFLOW.md) — upload-to-timeline walkthrough, exceptions, and review steps.
- [Workflow diagram](./workflow.svg) — visual medical-record processing path.
- [Project explanation](./PROJECT_EXPLANATION.md) — plain-language walkthrough of modules, user journeys, limitations, and demo guidance.
- [Presentation deck](./MediMate_AI_Project_Overview.pptx) — concise prototype overview for a project review or demo.

## Accuracy note

These materials describe the repository as inspected on **October 13, 2026**. The application is a prototype. Its medical-document processing is local OCR plus deterministic, pattern-based extraction; its lab explanations are rule-based educational context, not generative AI or clinical interpretation. The fictional ABHA-style identifier and FHIR-shaped export are demonstrations only. Update these documents if the implementation changes, and obtain clinical, privacy, and legal review before production use.
