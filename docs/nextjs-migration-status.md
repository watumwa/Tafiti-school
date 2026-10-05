# Tafiti School Management System — Next.js Migration Status

Date: 5 October 2026

## Objective

Replace the legacy Django-template user interface with a professional, responsive Next.js application while retaining Django as the source of truth for authentication, permissions, business rules, calculations, workflows, audit history and database data.

The migration is intentionally incremental. A legacy template is not considered migrated merely because a page exists in Next.js: the corresponding permissions, data scoping, actions, validations, calculations, error handling, printing/export behaviour and audit effects must also work.

## Phase 1 completed: application foundation

### Backend / API

- Added a role-aware workspace API on top of the mature `app` models.
- Added `/api/workspace/bootstrap/` for authenticated user, school, academic period, navigation and notification context.
- Added `/api/workspace/dashboard/` for role-aware summary metrics and attention items.
- Added `/api/workspace/resources/<resource>/` for searchable/paginated read views.
- Workspace resources currently include students, staff, admissions, parent access, classes/streams, subjects, results, attendance, timetable, fees, finance, library, communication, audit and settings.
- Parent data is explicitly scoped through `ParentAccess`; academic, finance and attendance visibility honours the corresponding parent permissions.
- Teacher/class-teacher views are scoped to teaching/class allocations where applicable.
- Login role context is now validated on the server rather than being a cosmetic frontend selector.
- Historical role names are normalised at the API/UI boundary (`Head master`, `Headteacher`, `DOS`, etc.).
- Existing legacy endpoints have been left intact so the migration remains reversible.

### Next.js frontend

- Restored a complete Next.js project definition (`package.json`, TypeScript, PostCSS/Tailwind configuration and environment example).
- Rebuilt the authenticated application shell with a dark-blue professional navigation system.
- Navigation is generated from server-authorised role capabilities rather than hard-coded client assumptions.
- Added responsive desktop/mobile navigation.
- Added breadcrumb/top-bar context and current academic period display.
- Added Ctrl/Cmd+K module search/command palette.
- Added a notification drawer.
- Added reusable toast notifications for success, warning, information and errors.
- Added a reusable data-table/resource pattern with server-side search, pagination, loading, empty and retry states, refresh and CSV export.
- Added role-aware dashboard summaries, attention items and quick links.
- Added Next.js server-side proxy routes so browser clients do not need direct access to Django JWTs.
- Authentication cookies remain HTTP-only.

### Security/configuration cleanup completed

- Removed hard-coded database and email passwords from source settings.
- Production no longer falls back to an insecure hard-coded Django secret key.
- Development defaults to SQLite unless configured otherwise.
- Added `backend/.env.example` and `frontend/.env.example`.
- Made timezone and development tunnel URL configurable; default timezone is `Africa/Kampala`.
- Corrected the malformed development URL default.

## Deliberately NOT removed yet

The experimental `backend.Student`, `backend.GradeMatrix` and `backend.FeeLedger` models still exist. The redesigned workspace no longer uses them as its source of truth, but deleting the tables immediately would introduce unnecessary migration/database risk. They should be retired only after the Next.js workflows have reached verified parity and any data in those tables has been reconciled.

## Important incomplete / risky areas found during the audit

### Critical: parent temporary password

`app/services/parent_portal.py` currently sets the literal temporary password `123`, and the legacy parent-activation view displays that password. This should be replaced with a unique, expiring, one-time credential or secure password-setup link. It has not been changed in Phase 1 because doing so without the complete delivery/reset workflow would break parent onboarding.

### Write workflows are not yet migrated

Phase 1 establishes read/navigation parity and the design foundation. The following legacy actions still need full Next.js migration and API endpoints before the old templates can be retired:

- Student create/edit/transfer/archive/reactivate, guardian/document/photo workflows.
- Staff create/edit/account creation/role assignment/status actions.
- Admission application review, decision, enrolment and applicant communication.
- Parent account activation/deactivation/permission management/password setup.
- Academic year/term/class/stream/subject/allocation management.
- Result entry, bulk entry/import, submission, verification sampling, correction, approval, publishing, locking/unlocking and report generation.
- Attendance session creation, marking, submission, locking/unlocking, correction and reporting.
- Timetable creation/editing/conflict handling/publishing/printing.
- Billing, bill generation, payment posting, receipt generation, reversals, credits, carry-forward, adjustments and finance reports.
- Budget, budget-item, expense/expenditure, vendor, approval and reconciliation workflows.
- Library book/copy management, issue/return/renewal, fine processing and member history.
- Announcement/event/message composition, targeting, delivery/read state and communication management.
- School settings editing and configuration workflows.
- Audit/report filters, printable reports, PDFs and specialised exports.
- HR/payroll workflows represented in the Django domain/migration history.
- File uploads, previews and document-management interactions across modules.

Until each workflow is migrated and tested, the corresponding legacy Django page should remain available as a fallback.

## Recommended migration order from here

1. Students + admissions + parent access (core identity/data foundation).
2. Academic setup: years, terms, classes, streams, subjects and allocations.
3. Attendance and timetable.
4. Results/assessment/verification/report cards.
5. Fees/payments/credits/receipts.
6. Finance/budget/expenditure/reconciliation.
7. Library and communications.
8. Settings, audit, reports and printable outputs.
9. HR/payroll and remaining secondary workflows.
10. Full role-by-role parity test, then remove legacy template routes and experimental duplicate API models.

## Definition of done for each migrated module

A module is only complete when all of the following pass:

- Correct users can see the module; unauthorised users receive server-side denial.
- List/search/filter/pagination behave correctly.
- Create/edit/action workflows preserve legacy validations and calculations.
- Destructive/financial actions require appropriate confirmation and permissions.
- Success, validation, conflict and server errors have human-readable feedback.
- Loading, empty and retry states are present.
- Mobile/responsive layout is usable.
- Parent/teacher/bursar/administrative data scoping is verified.
- Audit effects are retained where the legacy workflow records them.
- Print/export/report behaviour is preserved where applicable.
- Legacy and Next.js output is compared against the same database data.

## Local development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

The development configuration defaults to SQLite. Update `.env` if the existing MySQL/hosted database should be used instead.

### Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`.

## Validation performed in this environment

- Modified Python source files pass Python syntax compilation.
- Hard-coded credentials identified in the settings source were removed.
- Frontend TypeScript/TSX source passes parser-level syntax validation.
- A full `npm install` / Next.js production build could not be completed in the current execution environment because the package registry was unreachable.
- A full Django `manage.py check` could not be completed because the required Python packages could not be downloaded in the current execution environment.

Therefore the first local run should execute `python manage.py check`, `npm run typecheck` and `npm run build` once dependencies are available, before production deployment.

## Phase 2 checkpoint — CRUD actions + soft-clay UI

The workspace now includes a permission-aware action layer instead of read-only tables.

### Development database

- `core.settings.development` uses SQLite at `backend/db.sqlite3`.
- `manage.py` defaults to `core.settings.development`.
- `common.py` now also defaults to SQLite so local development does not silently fall back to MySQL.
- Production continues to override the database in `core.settings.production` from `DATABASE_URL` / production DB environment variables.

### Workspace actions now available

- All migrated resource tables expose a **View** action.
- **Students:** Add, Edit, View, Deactivate/Reactivate. Student deletion is intentionally soft so results, bills, attendance, documents and audit history survive.
- **Staff:** Add, Edit, View, Retire/Reactivate. New staff photo upload is supported through multipart form proxying.
- **Admissions:** New application, Edit, View. Destructive delete remains disabled until the admissions lifecycle is migrated with withdrawal/rejection semantics.
- **Academic classes:** Add, Edit, View, Delete when there are no linked dependencies.
- **Subjects:** Add, Edit, View, Delete when there are no linked dependencies.
- **School settings:** View and Edit, including logo replacement.
- Other modules currently expose View while their workflow-specific actions are migrated (results verification, attendance locking, fee/payment posting, library circulation, finance approvals, communication workflows, parent access).

All write operations are checked again by Django. Hiding a button in Next.js is not treated as authorization.

### Visual system

The workspace now uses a **hybrid soft-clay design** rather than full claymorphism:

- Dark navy structural navigation remains flat/high-contrast.
- Cards, dialogs, buttons, row actions and pagination use restrained clay-style highlights/shadows.
- Dense data tables remain comparatively flat and readable.
- Destructive actions remain visually explicit and use confirmation dialogs.

This avoids the common claymorphism problem where every element appears raised and operational software becomes visually noisy.

## Student & staff photo integration update

- The workspace API now returns `Student.photo` and `Staff.staff_photo` for the real Django records.
- Student and staff tables render circular profile avatars with initials fallback when a file is missing.
- Record detail dialogs show a larger profile image.
- Django `ImageField` inputs are now identified separately from generic file fields.
- Add/Edit forms show the current image and an immediate preview when a replacement is selected.
- Next.js includes an authenticated `/api/media/...` proxy so Django `/media/...` files resolve correctly when the frontend and backend run on different ports/domains.
- Existing media files remain in Django's configured `MEDIA_ROOT`; do not delete `backend/media/` when moving an existing installation. The supplied original archive did not contain actual student/staff image files, so any existing deployment media directory must be retained separately when moving environments.
