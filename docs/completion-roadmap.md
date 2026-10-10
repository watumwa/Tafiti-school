# Tafiti School Management System — Completion Roadmap

Updated: 10 October 2026

This roadmap is intentionally sequential. We do not move to the next phase until the current phase is functionally verified on the production deployment.

## Phase 1 — Production stability, media and security

Status: IN PROGRESS

Goal: eliminate infrastructure-level failures before expanding workflows.

Scope:
- Reliable Vercel Blob storage for student photos, staff photos and uploaded documents.
- Increase media field capacity so full Blob URLs cannot overflow legacy database columns.
- Confirm production Blob and database environment configuration.
- Ensure uploads use multipart requests end-to-end through Next.js and Django.
- Human-readable API errors for failed saves/uploads.
- Verify secure first-login credentials for staff and parents.
- Production smoke test: create/edit student, create/edit staff, upload/replace images, reopen records and verify images persist.

Already completed in code:
- Public Vercel Blob storage backend and generated compact object paths.
- Blob environment variable documented.
- Parent temporary credentials use cryptographically generated passwords rather than a shared default password.
- Expanded student/staff media paths to support Blob URLs.

Definition of done:
- Staff photo upload/save works in production.
- Student photo upload/save works in production.
- Existing photos continue to render.
- Uploaded files survive redeployments.
- No generic HTTP 500 during normal student/staff edits.

## Phase 2 — Student, staff and admissions lifecycle

Goal: make identity and enrolment workflows complete and reduce repeated navigation.

Scope:
- Unified Student Profile: overview, guardians, admission history, class/stream, attendance, results, fees, documents, promotion/transfer history and account status.
- Unified Staff Profile: identity, employment, roles, account, teaching assignments, documents, attendance/leave and status history.
- Admissions pipeline: application -> review -> decision -> enrolment -> student creation -> parent access -> initial billing.
- Student transfer, archive/reactivation and status history.
- Staff account creation, role assignment, retirement/reactivation and first-login flow.

Definition of done:
- A registrar/admin can complete a student's full lifecycle without falling back to a legacy page.
- Staff lifecycle actions work without direct Django Admin use.

## Phase 3 — Academic setup, attendance and timetable

Goal: complete day-to-day academic operations.

Scope:
- Academic year/term activation and history.
- Classes, streams, subjects, class teachers and subject allocations.
- Attendance creation, marking, correction history, submit/lock/reopen, reports and export.
- Visual timetable grid, teacher/class views, conflict detection, draft/publish and printing.

Definition of done:
- Teachers and academic managers can run a normal school day entirely in the workspace.

## Phase 4 — Assessments, results and report cards

Goal: complete the academic reporting chain.

Scope:
- Assessment setup and weighting.
- Teacher mark entry and bulk import.
- Submission, script verification, correction, approval and locking.
- Publishing to parents.
- Report card generation, remarks, signatures, class/subject performance reports and bulk PDF/Excel output.

Definition of done:
- Assessment creation through published report card works end-to-end with correct permissions and audit history.

## Phase 5 — Fees, finance and reconciliation

Goal: make financial operations auditable and accounting-safe.

Scope:
- Bill generation and fee structures.
- Payments, receipts and receipt reprints.
- Reversals/voids instead of destructive deletes.
- Discounts, bursaries, waivers, credits, overpayments, carry-forward and refunds.
- Bank/mobile-money reconciliation.
- Daily collections, cashier closing, debtor aging, statements and finance reports.
- Budget/expenditure/vendor approval workflows.

Definition of done:
- Every financial movement is traceable, reversible where appropriate and represented in reports.

## Phase 6 — Library, communication and reporting hub

Goal: complete supporting school operations and consolidate reporting.

Scope:
- Library catalogue, copies, issue/return/renewal, overdue/lost/damaged processing and member history.
- Scheduled overdue notifications/fine processing where appropriate.
- Internal announcements and messaging.
- External SMS/email provider integration with templates, consent, delivery receipts, retries and cost controls.
- Dedicated Reports hub for academics, attendance, finance, admissions, library and staff.

Definition of done:
- Operational reports are discoverable from one reporting area and communication delivery is traceable.

## Phase 7 — HR/payroll, QA and legacy retirement

Goal: finish secondary workflows and prepare a clean production release.

Scope:
- HR employment records, attendance/leave and payroll workflows.
- Full role-by-role permission test: Admin, Head Teacher, Director of Studies, Teacher, Class Teacher, Bursar, Admissions Officer, Librarian and Parent.
- Mobile/responsive checks.
- Production build, Django system checks and regression tests.
- Remove or disable obsolete legacy/template routes only after parity is verified.
- Update operational documentation and deployment checklist.

Definition of done:
- Every supported role can complete its approved workflows without legacy fallbacks or unexplained 500 errors.

## Working rule

No new feature phase starts while the current phase has unresolved production-blocking errors. Reliability and workflow completion take priority over adding more menu items.
