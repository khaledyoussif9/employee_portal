---
name: project-master
description: Master guardrails and architecture context for the EETC Delta employee self-service portal. Read before modifying this repository.
---

# Employee Portal — Project Master

## Purpose
This repository implements an Arabic RTL employee self-service portal for the Egyptian Electricity Transmission Company (EETC), Delta Region. It includes a Flask/SQL Server web backend and a Flutter client.

## Core architecture
- Backend: Python Flask.
- Database: Microsoft SQL Server through pyodbc.
- Web UI: employee_portal.html, Arabic RTL.
- Mobile/client app: Flutter under `flutter/`.
- Authentication: JWT with employee and HR/admin authorization flows.
- PDF generation: ReportLab with Arabic text handling.

## Mandatory workflow
1. Understand the requested change before editing.
2. Inspect the relevant implementation and database assumptions.
3. Load the most relevant specialized skill when available.
4. Make the smallest coherent change that satisfies the request.
5. Preserve existing behavior outside the requested scope.
6. Validate API/UI/database contracts affected by the change.
7. Report exactly what changed and any migration/configuration step required.

## Guardrails
- Never invent payroll, entitlement, pension, employee-status, or disbursement rules. Use documented project rules or ask for clarification.
- Never silently rename database tables/columns or change their semantics.
- Never commit passwords, JWT secrets, database credentials, SMTP credentials, tokens, production employee data, or `.env` values.
- Do not weaken authentication, authorization, validation, or audit controls to make a feature work.
- Admin-only functionality must remain protected server-side; hiding a UI control is not authorization.
- Do not change established Arabic copy, branding, layout, colors, logo placement, footer/ticker behavior, or RTL behavior unless the requested task requires it.
- Do not remove working endpoints/features as a shortcut for fixing another feature.
- Prefer backward-compatible API changes when the Flutter and web clients share the backend.
- Treat payroll calculations and analytics as financial logic: verify filters, date periods, signs, null handling, duplicates, employee counts, and totals.

## Repository map
- `app.py`: Flask application/API and primary business logic.
- `db.py`: SQL Server connection layer.
- `employee_portal.html`: main web interface.
- `pdf_generator.py`: PDF generation.
- `database/`: database-related scripts/assets.
- `flutter/`: Flutter client.
- `assets/`: web assets.

## Change discipline
For substantial changes, separate concerns where practical: database query/business logic, API contract, UI rendering, and client integration. Avoid broad refactors during bug fixes unless explicitly requested.

Before declaring a change complete, check for syntax/runtime errors, authorization regressions, SQL parameterization, empty-result behavior, Arabic/RTL rendering, and compatibility with both web and Flutter consumers where applicable.
