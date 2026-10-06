# Tafiti School — Next.js Migration Status

## Completed in this foundation pass

- Restored a runnable Next.js source scaffold (`package.json`, TypeScript, ESLint, Tailwind/PostCSS config).
- Replaced the generic dashboard with a role-aware professional application shell.
- Added grouped sidebar navigation generated from authenticated role capabilities.
- Added responsive mobile navigation and persistent desktop workspace navigation.
- Added Ctrl/Cmd+K module finder.
- Added notification drawer and reusable toast notification system.
- Added reusable loading, error and empty states.
- Added searchable, paginated data-table presentation.
- Added consistent status badges and dashboard metric cards.
- Added school identity/current academic period context to the UI.
- Added role alias normalization for historical labels such as `Head master`, `Headteacher` and `DOS`.
- Added server-side module authorization for the Next.js workspace APIs.
- Connected the redesigned workspace to the established `app` domain models instead of the experimental `backend.Student`, `backend.GradeMatrix` and `backend.FeeLedger` models.
- Added parent-safe data scoping through `ParentAccess`.
- Added read APIs for students, admissions, staff, classes, subjects, results, attendance, timetable, fees, finance, library, communication, reports catalogue, settings and audit.
- Added read APIs for parent children/results/attendance/finance/library/timetable.
- Added authenticated parent workspace screens for linked children, verified academic results, attendance history, finance statements and receipts, assigned-teacher messaging, school calendar, notifications, profile editing and verified-results PDF downloads. Parent menu modules are limited to family, academic, attendance, finance, communication and calendar workflows, and child data is filtered by the corresponding verified `ParentAccess` permission.
- Added attendance session creation and roster capture, draft saving, submit-and-lock, and administrator reopening through the Next.js workspace, using the existing Django attendance services and audit log.
- Added role-specific dashboard KPIs for school leadership, bursar, admissions, library and teachers, with attendance and fee-collection trends sourced from submitted attendance and recorded payments.
- Removed committed database/email secrets from the working copy and moved configuration to environment variables.

## Deliberately not removed yet

The experimental API models in `backend/models.py` are still present. They should only be removed after production data is checked and a controlled migration confirms nothing depends on their tables.

## Next migration work

The Next.js workspace now has core CRUD and selected specialist workflows, but the existing Django templates remain the fallback until remaining write and reporting workflows reach parity:

1. Student create/edit/detail, documents and bulk registration.
2. Staff create/edit/detail, account provisioning and role assignment.
3. Academic year/term/class/stream/subject allocation administration.
4. Admissions status transitions and enrolment service flow.
5. Attendance correction history, reporting and export workflows.
6. Assessment setup, mark entry, verification queue, corrections and report preparation.
7. Timetable editing, conflict validation, classroom setup and print views.
8. Fee item setup, class billing, bulk billing, payments, credits, carry-forward and receipts.
9. Budget/expenditure/vendor/approval/bank reconciliation workflows.
10. Library catalogue/copy CRUD, issue/return/renew/lost/fine resolution.
11. Announcements/events/messages CRUD and conversation workflows.
12. Parent access activation/deactivation/password reset and messaging.
13. School settings/sections/departments/signatures editing.
14. Complex printable/PDF/CSV reports and exports.
15. Secondary-school-specific routes and reports.
16. Final parity review against every legacy URL/template before Django templates are retired.

## Important findings to address

- `Term.is_current` and `AcademicYear.is_current` are simple booleans; the database can potentially contain more than one current row. A uniqueness/consistency rule should be added.
- Historical role labels are inconsistent. The API now normalizes them for the frontend, but the stored role catalogue should eventually be cleaned with a data migration.
- `TermResult.calculate_term_result()` and `AnnualResult.calculate_annual_result()` reference attributes that do not exist on those models (`self.term`, `self.academic_year`, and `student.class_level`). These methods need correction before relying on them in the new frontend.
- Complex report logic should remain in Django services/selectors instead of being reimplemented in React.
- The original project contained hard-coded database and SMTP credentials. Those values should be rotated because they may already exist in repository history.

## Local run

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

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

The default local API is `http://127.0.0.1:8000/api` and Next.js runs on `http://localhost:3000`.
